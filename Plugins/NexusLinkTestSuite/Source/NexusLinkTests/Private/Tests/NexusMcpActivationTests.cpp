// Copyright byteyang. All Rights Reserved.

#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#include "CoreGlobals.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "NexusMcpActivation.h"
#include "NexusLinkSettings.h"

// PRIVATE_GIsRunningCommandlet（CoreGlobals.h 声明）供 IsRunningCommandlet() 读取，
// 测试里临时置位以模拟非编辑器角色（cook/commandlet 进程），验证结束后还原，不影响其他测试。

/** 测试前后把控制台覆盖复位到「未设置」，避免用例间互相污染。文件级 static，不用匿名命名空间（CapabilitySpec §8.3）。 */
static void ResetConsoleOverrides()
{
	FNexusMcpActivation::ClearConsoleOverrides();
	FNexusMcpActivation::SetConsoleEnable(TOptional<bool>());
}

// ────────────────────────────────────────────────────────────────────────────
// 1. 优先级 + 三态压制：控制台 > Preferences；off 稳定压制，不受 Preferences 改动影响
// ────────────────────────────────────────────────────────────────────────────

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FNexusMcpActivationPriorityTest,
	"NexusLink.Mcp.Activation.ConsolePriorityAndTriState",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusMcpActivationPriorityTest::RunTest(const FString& Parameters)
{
	UNexusLinkSettings* Settings = UNexusLinkSettings::Get();
	const bool bOrigEnable = Settings->bEnableMcpServer;
	const bool bOrigLan    = Settings->bAllowLanBind;
	ResetConsoleOverrides();

	// 环境命令行若已带 -EnableNexusMcp，Preferences 分支的来源断言不成立，仅跳过该项精确断言
	const bool bCliAlreadyEnables = FParse::Param(FCommandLine::Get(), TEXT("EnableNexusMcp"));

	ENexusMcpSource Source = ENexusMcpSource::None;
	FString Reason;

	// Preferences 勾选、控制台未覆盖 → 请求为真
	Settings->bEnableMcpServer = true;
	TestTrue(TEXT("Preferences 勾选时请求为真"), FNexusMcpActivation::IsRequested(Source, Reason));
	if (!bCliAlreadyEnables)
	{
		TestTrue(TEXT("来源=Preferences"), Source == ENexusMcpSource::Preferences);
	}

	// 控制台会话覆盖为 off：即使 Preferences 仍勾选，也应压制为假（控制台 > Preferences）
	FNexusMcpActivation::SetConsoleEnable(false);
	TestFalse(TEXT("控制台 off 压制 Preferences 勾选"), FNexusMcpActivation::IsRequested(Source, Reason));
	TestTrue(TEXT("off 时来源不应为已请求来源"), Source == ENexusMcpSource::None);
	TestTrue(TEXT("未启动原因非空"), !Reason.IsEmpty());

	// 模拟「用户之后又切换了一个不相关的 Preferences 项」：控制台覆盖仍应稳定压制
	Settings->bAllowLanBind = !Settings->bAllowLanBind;
	TestFalse(TEXT("不相关的 Preferences 改动不应唤醒被控制台关闭的服务"),
		FNexusMcpActivation::IsRequested(Source, Reason));

	// 控制台会话覆盖为 on：即使 Preferences 未勾选，也应请求为真（控制台 > Preferences）
	Settings->bEnableMcpServer = false;
	FNexusMcpActivation::SetConsoleEnable(true);
	TestTrue(TEXT("控制台 on 越过未勾选的 Preferences"), FNexusMcpActivation::IsRequested(Source, Reason));
	TestTrue(TEXT("来源=Console"), Source == ENexusMcpSource::Console);

	// 清空覆盖后回到 Preferences/CommandLine 判定
	ResetConsoleOverrides();
	Settings->bEnableMcpServer = bOrigEnable;
	Settings->bAllowLanBind    = bOrigLan;

	return true;
}

// ────────────────────────────────────────────────────────────────────────────
// 2. 监听配置优先级：端口/LAN 与启停同序，控制台覆盖 > Preferences > 默认值
// ────────────────────────────────────────────────────────────────────────────

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FNexusMcpActivationListenConfigTest,
	"NexusLink.Mcp.Activation.ListenConfigPriority",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusMcpActivationListenConfigTest::RunTest(const FString& Parameters)
{
	UNexusLinkSettings* Settings = UNexusLinkSettings::Get();
	const bool bOrigLan = Settings->bAllowLanBind;
	ResetConsoleOverrides();

	const bool bCliMcpPort = FParse::Param(FCommandLine::Get(), TEXT("NexusMcpPort="));
	const bool bCliLan     = FParse::Param(FCommandLine::Get(), TEXT("NexusAllowLan"));

	// 默认：Preferences 未勾局域网、无控制台覆盖 → loopback
	Settings->bAllowLanBind = false;
	if (!bCliLan)
	{
		TestFalse(TEXT("默认不绑局域网"), FNexusMcpActivation::ResolveListenConfig().bLan);
	}

	// Preferences 勾选局域网绑定 → 生效（仅可信角色，测试进程本身是编辑器）
	Settings->bAllowLanBind = true;
	TestTrue(TEXT("Preferences 勾选局域网绑定生效"), FNexusMcpActivation::ResolveListenConfig().bLan);

	// 控制台覆盖为强制关闭 → 压制 Preferences（控制台 > Preferences）
	FNexusMcpActivation::SetConsoleListenOverride(0, 0, 0);
	TestFalse(TEXT("控制台强制关闭局域网压制 Preferences 勾选"), FNexusMcpActivation::ResolveListenConfig().bLan);

	// 控制台覆盖端口：未指定的一侧维持默认，指定的一侧生效
	FNexusMcpActivation::ClearConsoleOverrides();
	if (!bCliMcpPort)
	{
		FNexusMcpActivation::SetConsoleListenOverride(51234, 0, -1);
		const FNexusMcpListenConfig Config = FNexusMcpActivation::ResolveListenConfig();
		TestEqual(TEXT("控制台端口覆盖生效"), Config.McpPort, 51234);
		TestEqual(TEXT("未覆盖的 WS 端口维持默认"), Config.WsPort, 55000);
	}

	ResetConsoleOverrides();
	Settings->bAllowLanBind = bOrigLan;

	return true;
}

// ────────────────────────────────────────────────────────────────────────────
// 3. 角色门控：非编辑器角色（-game/-server 子进程、cook/commandlet）不读 Preferences
// ────────────────────────────────────────────────────────────────────────────

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FNexusMcpActivationRoleGatingTest,
	"NexusLink.Mcp.Activation.RoleGating",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusMcpActivationRoleGatingTest::RunTest(const FString& Parameters)
{
	UNexusLinkSettings* Settings = UNexusLinkSettings::Get();
	const bool bOrigEnable = Settings->bEnableMcpServer;
	const bool bOrigCommandlet = PRIVATE_GIsRunningCommandlet;
	ResetConsoleOverrides();

	const bool bCliAlreadyEnables = FParse::Param(FCommandLine::Get(), TEXT("EnableNexusMcp"));

	Settings->bEnableMcpServer = true;

#if WITH_EDITORONLY_DATA
	// GIsEditor 仅在带编辑器专属数据的目标（Editor）里是可写的 extern bool；
	// Game/Server 目标里它是 `#define GIsEditor false` 的编译期常量，不能赋值——
	// 恰好符合测试意图：那些目标本就恒为「非编辑器角色」，见下方 #else 分支。
	const bool bOrigGIsEditor = GIsEditor;

	// 完整编辑器进程（非 commandlet）→ 可信，Preferences 生效
	GIsEditor = true;
	PRIVATE_GIsRunningCommandlet = false;
	TestTrue(TEXT("编辑器非 commandlet 可信 Preferences"), FNexusMcpActivation::IsPreferencesTrusted());

	// commandlet 进程（如 cook）→ 不可信，忽略 Preferences
	PRIVATE_GIsRunningCommandlet = true;
	TestFalse(TEXT("commandlet 不可信 Preferences"), FNexusMcpActivation::IsPreferencesTrusted());
	if (!bCliAlreadyEnables)
	{
		ENexusMcpSource Source;
		FString Reason;
		TestFalse(TEXT("commandlet 忽略 Preferences 勾选，无启动参数则不请求"),
			FNexusMcpActivation::IsRequested(Source, Reason));
		TestTrue(TEXT("原因提示角色不可信"), !Reason.IsEmpty());
	}

	// 编辑器二进制以 -game / -server 启动的子进程：GIsEditor=false → 不可信
	PRIVATE_GIsRunningCommandlet = false;
	GIsEditor = false;
	TestFalse(TEXT("-game/-server 子进程不可信 Preferences"), FNexusMcpActivation::IsPreferencesTrusted());

	GIsEditor = bOrigGIsEditor;
#else
	// Game/Server 目标：GIsEditor 恒为 false，等价于本就一直处于「-game/-server 子进程」角色
	PRIVATE_GIsRunningCommandlet = false;
	TestFalse(TEXT("Game/Server 目标恒不可信 Preferences"), FNexusMcpActivation::IsPreferencesTrusted());
	if (!bCliAlreadyEnables)
	{
		ENexusMcpSource Source;
		FString Reason;
		TestFalse(TEXT("忽略 Preferences 勾选，无启动参数则不请求"),
			FNexusMcpActivation::IsRequested(Source, Reason));
		TestTrue(TEXT("原因提示角色不可信"), !Reason.IsEmpty());
	}
#endif

	PRIVATE_GIsRunningCommandlet = bOrigCommandlet;
	ResetConsoleOverrides();
	Settings->bEnableMcpServer = bOrigEnable;

	return true;
}
