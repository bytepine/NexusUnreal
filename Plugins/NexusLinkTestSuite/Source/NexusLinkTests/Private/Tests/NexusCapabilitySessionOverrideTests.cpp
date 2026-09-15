// Copyright byteyang. All Rights Reserved.

#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#include "NexusCapability.h"
#include "NexusCapabilityRegistry.h"
#include "NexusLinkSettings.h"
#include "NexusMcpTool.h"

/**
 * 测试前后把 Settings 会话态复位到「无覆盖」，避免用例间互相污染。文件级 static，
 * 不用匿名命名空间（CapabilitySpec §8.3）。
 */
static void ResetSessionCapabilityState(UNexusLinkSettings* Settings)
{
	Settings->ClearSessionCapabilityOverrides();
}

/** 取注册表中第一个非 dangerous 的 cap 名，供普通启停用例使用；未注册任何 cap 时返回空串。 */
static FString FindFirstNonDangerousCapabilityName()
{
	for (const FCapRecord& Record : FNexusCapabilityRegistry::Get().GetAllRecords())
	{
		if (!Record.Def.HasTag(FNexusMcpTags::Dangerous))
		{
			return Record.Def.Name;
		}
	}
	return FString();
}

// ────────────────────────────────────────────────────────────────────────────
// 1. 会话级禁用压制持久启用：游戏内面板关掉一个 cap，不写 DisabledCapabilities
// ────────────────────────────────────────────────────────────────────────────

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FNexusCapabilitySessionDisableTest,
	"NexusLink.Mcp.Capability.SessionDisableOverridesPersistentEnable",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusCapabilitySessionDisableTest::RunTest(const FString& Parameters)
{
	UNexusLinkSettings* Settings = UNexusLinkSettings::Get();
	const FString CapName = FindFirstNonDangerousCapabilityName();
	if (CapName.IsEmpty())
	{
		AddInfo(TEXT("未注册任何非 dangerous cap，跳过"));
		return true;
	}

	const bool bOrigDisabled = Settings->DisabledCapabilities.Contains(CapName);
	ResetSessionCapabilityState(Settings);
	Settings->DisabledCapabilities.Remove(CapName);

	TestTrue(TEXT("持久启用时会话前应为启用"), Settings->IsCapabilityEnabled(CapName));

	Settings->SetSessionCapabilityEnabled(CapName, false);
	TestFalse(TEXT("会话级禁用后立即不可用"), Settings->IsCapabilityEnabled(CapName));
	TestFalse(TEXT("会话级禁用不写持久 DisabledCapabilities"), Settings->DisabledCapabilities.Contains(CapName));
	TestTrue(TEXT("会话级禁用记录在 SessionDisabledCapabilities"), Settings->SessionDisabledCapabilities.Contains(CapName));

	ResetSessionCapabilityState(Settings);
	TestTrue(TEXT("清空会话覆盖后恢复持久启用状态"), Settings->IsCapabilityEnabled(CapName));

	if (bOrigDisabled)
	{
		Settings->DisabledCapabilities.Add(CapName);
	}

	return true;
}

// ────────────────────────────────────────────────────────────────────────────
// 2. 会话级启用抬起持久禁用：不写 DisabledCapabilities，只在本进程会话内生效
// ────────────────────────────────────────────────────────────────────────────

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FNexusCapabilitySessionEnableTest,
	"NexusLink.Mcp.Capability.SessionEnableLiftsPersistentDisable",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusCapabilitySessionEnableTest::RunTest(const FString& Parameters)
{
	UNexusLinkSettings* Settings = UNexusLinkSettings::Get();
	const FString CapName = FindFirstNonDangerousCapabilityName();
	if (CapName.IsEmpty())
	{
		AddInfo(TEXT("未注册任何非 dangerous cap，跳过"));
		return true;
	}

	const bool bOrigDisabled = Settings->DisabledCapabilities.Contains(CapName);
	ResetSessionCapabilityState(Settings);
	Settings->DisabledCapabilities.Add(CapName);

	TestFalse(TEXT("持久禁用时会话前应为禁用"), Settings->IsCapabilityEnabled(CapName));

	Settings->SetSessionCapabilityEnabled(CapName, true);
	TestTrue(TEXT("会话级启用后立即可用"), Settings->IsCapabilityEnabled(CapName));
	TestTrue(TEXT("会话级启用不清持久 DisabledCapabilities"), Settings->DisabledCapabilities.Contains(CapName));
	TestTrue(TEXT("会话级启用记录在 SessionEnabledCapabilities"), Settings->SessionEnabledCapabilities.Contains(CapName));

	ResetSessionCapabilityState(Settings);
	TestFalse(TEXT("清空会话覆盖后恢复持久禁用状态"), Settings->IsCapabilityEnabled(CapName));

	if (!bOrigDisabled)
	{
		Settings->DisabledCapabilities.Remove(CapName);
	}

	return true;
}

// ────────────────────────────────────────────────────────────────────────────
// 3. 危险 cap：DangerousCapAccess=Disabled 时仍可单条会话强制启用，不影响其他危险 cap
// ────────────────────────────────────────────────────────────────────────────

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FNexusCapabilitySessionDangerousTest,
	"NexusLink.Mcp.Capability.SessionEnableSingleDangerousCap",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusCapabilitySessionDangerousTest::RunTest(const FString& Parameters)
{
	UNexusLinkSettings* Settings = UNexusLinkSettings::Get();
	const TArray<FString> DangerousNames = UNexusLinkSettings::CollectDangerousCapabilityNames();
	if (DangerousNames.Num() == 0)
	{
		AddInfo(TEXT("未注册任何 dangerous cap，跳过"));
		return true;
	}

	const ENexusDangerousCapAccess OrigAccess = Settings->DangerousCapAccess;
	ResetSessionCapabilityState(Settings);
	Settings->DangerousCapAccess = ENexusDangerousCapAccess::Disabled;

	const FString& Target = DangerousNames[0];
	TestFalse(TEXT("全部禁用模式下危险 cap 默认不可用"), Settings->IsCapabilityEnabled(Target));

	Settings->SetSessionCapabilityEnabled(Target, true);
	TestTrue(TEXT("单条会话强制启用后可用"), Settings->IsCapabilityEnabled(Target));

	if (DangerousNames.Num() > 1)
	{
		TestFalse(TEXT("未强制启用的其他危险 cap 仍不可用"), Settings->IsCapabilityEnabled(DangerousNames[1]));
	}

	ResetSessionCapabilityState(Settings);
	TestFalse(TEXT("清空会话覆盖后恢复全部禁用"), Settings->IsCapabilityEnabled(Target));

	Settings->DangerousCapAccess = OrigAccess;

	return true;
}
