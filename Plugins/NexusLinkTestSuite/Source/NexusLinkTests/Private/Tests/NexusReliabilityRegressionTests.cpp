// Copyright byteyang. All Rights Reserved.

#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "NexusLinkBuildConfig.h"
#include "NexusReliabilityTestTypes.h"

int32 FNexusReliabilityTestRow::DestructionCount = 0;

#if WITH_EDITOR && NEXUSLINK_WITH_SERVER
#include "Server/NexusMcpDispatcher.h"
#include "NexusLinkSettings.h"
#include "NexusMultiSectionCapability.h"
#include "NexusMcpSchemaBuilder.h"
#include "NexusMcpTool.h"
#include "NexusMcpToolRegistry.h"
#include "NexusCapabilityRegistry.h"
#include "NexusEditorServices.h"
#include "Utils/NexusCapResultAdapter.h"
#include "Materials/Material.h"
#include "UObject/Package.h"
#include "UObject/StrongObjectPtr.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "GameFramework/Actor.h"
#include "Kismet2/KismetEditorUtilities.h"

static TSharedPtr<FJsonObject> ParseReliabilityResponse(const FString& Response)
{
	TSharedPtr<FJsonObject> Parsed;
	FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Response), Parsed);
	return Parsed;
}

/** UE 的 JSON 字段查找不区分大小写，协议契约必须检查实际存储/序列化的拼写。 */
static bool HasExactReliabilityField(const TSharedPtr<FJsonObject>& Object, const TCHAR* Name)
{
	for (const auto& Pair : Object->Values)
	{
		if (FString(*Pair.Key).Equals(Name, ESearchCase::CaseSensitive)) return true;
	}
	return false;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusProtocolContractTest,
	"NexusLink.Reliability.ProtocolContract",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusProtocolContractTest::RunTest(const FString& Parameters)
{
	FNexusMcpDispatcher Dispatcher([](const FString&) {});
	TSharedPtr<FJsonObject> Response;
	Dispatcher.Dispatch(TEXT(R"({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{}}})"),
		[&Response](const FString& Json) { Response = ParseReliabilityResponse(Json); });
	if (!TestTrue(TEXT("握手返回有效 JSON"), Response.IsValid())) return false;
	const TSharedPtr<FJsonObject> Init = Response->GetObjectField(TEXT("result"));
	TestTrue(TEXT("标准 capabilities"), HasExactReliabilityField(Init, TEXT("capabilities")));
	TestTrue(TEXT("标准 instructions"), HasExactReliabilityField(Init, TEXT("instructions")));
	if (Init->HasField(TEXT("capabilities")))
	{
		TestTrue(TEXT("标准 listChanged"), Init->GetObjectField(TEXT("capabilities"))
			->GetObjectField(TEXT("tools"))->GetBoolField(TEXT("listChanged")));
		TestTrue(TEXT("listChanged 的实际拼写"), HasExactReliabilityField(
			Init->GetObjectField(TEXT("capabilities"))->GetObjectField(TEXT("tools")), TEXT("listChanged")));
	}
	for (const ENexusToolsListMode Mode : { ENexusToolsListMode::SearchMode, ENexusToolsListMode::MultiTool })
	{
		TGuardValue<ENexusToolsListMode> ModeGuard(GetMutableDefault<UNexusLinkSettings>()->ToolsListMode, Mode);
		Dispatcher.DispatchDirect(TEXT(R"({"jsonrpc":"2.0","id":2,"method":"tools/list"})"),
			[&Response](const FString& Json) { Response = ParseReliabilityResponse(Json); });
		if (!TestTrue(TEXT("工具列表返回有效 JSON"), Response.IsValid())) return false;
		for (const auto& Tool : Response->GetObjectField(TEXT("result"))->GetArrayField(TEXT("tools")))
		{
			TestTrue(TEXT("每个工具提供标准 inputSchema"), HasExactReliabilityField(Tool->AsObject(), TEXT("inputSchema")));
			TestFalse(TEXT("不输出错误的 InputSchema"), HasExactReliabilityField(Tool->AsObject(), TEXT("InputSchema")));
			TestFalse(TEXT("不输出错误的 Annotations"), HasExactReliabilityField(Tool->AsObject(), TEXT("Annotations")));
			const TSharedPtr<FJsonObject>* Annotations = nullptr;
			if (Tool->AsObject()->TryGetObjectField(TEXT("annotations"), Annotations))
			{
				TestTrue(TEXT("标准 readOnlyHint"), HasExactReliabilityField(*Annotations, TEXT("readOnlyHint")));
			}
		}
	}
	Response = ParseReliabilityResponse(FNexusMcpDispatcher::MakeJsonRpcError(nullptr, -32602, TEXT("invalid")));
	const TSharedPtr<FJsonObject> Error = Response->GetObjectField(TEXT("error"));
	TestTrue(TEXT("错误 code 的实际拼写"), HasExactReliabilityField(Error, TEXT("code")));
	TestTrue(TEXT("错误 message 的实际拼写"), HasExactReliabilityField(Error, TEXT("message")));
	TestEqual(TEXT("标准错误 code"), Error->GetIntegerField(TEXT("code")), -32602);
	TestEqual(TEXT("标准错误 message"), Error->GetStringField(TEXT("message")), FString(TEXT("invalid")));
	Dispatcher.DispatchDirect(TEXT(R"({"jsonrpc":"2.0","id":3,"method":"status"})"),
		[&Response](const FString& Json) { Response = ParseReliabilityResponse(Json); });
	if (!TestTrue(TEXT("代理 status 方法可用"), Response.IsValid() && Response->HasField(TEXT("result")))) return false;
	const TSharedPtr<FJsonObject> Status = Response->GetObjectField(TEXT("result"));
	for (const TCHAR* Key : { TEXT("server"), TEXT("version"), TEXT("engineVersion"), TEXT("projectName"), TEXT("authRequired") })
	{
		TestTrue(FString::Printf(TEXT("代理 status 字段 %s 保持原拼写"), Key), HasExactReliabilityField(Status, Key));
	}
	Dispatcher.DispatchDirect(TEXT(R"({"jsonrpc":"2.0","id":4,"method":"nexus/instructions"})"),
		[&Response](const FString& Json) { Response = ParseReliabilityResponse(Json); });
	if (!TestTrue(TEXT("代理说明返回成功"), Response.IsValid() && Response->HasField(TEXT("result")))) return false;
	TestTrue(TEXT("代理 instructions 保持原拼写"), HasExactReliabilityField(Response->GetObjectField(TEXT("result")), TEXT("instructions")));
	Dispatcher.DispatchDirect(TEXT(R"({"jsonrpc":"2.0","id":5,"method":"nexus/proxy_config"})"),
		[&Response](const FString& Json) { Response = ParseReliabilityResponse(Json); });
	if (!TestTrue(TEXT("代理配置返回成功"), Response.IsValid() && Response->HasField(TEXT("result")))) return false;
	const TSharedPtr<FJsonObject> ProxyConfig = Response->GetObjectField(TEXT("result"));
	for (const TCHAR* Key : { TEXT("protocolVersion"), TEXT("minProxyVersion"), TEXT("initializePrefix"), TEXT("nexusLinkVersion") })
	{
		TestTrue(FString::Printf(TEXT("代理配置字段 %s 保持原拼写"), Key), HasExactReliabilityField(ProxyConfig, Key));
	}
	return true;
}

/** 不注册的流程桩：验证公共分发把声明的名称原样传给子类。 */
class FNexusReliabilitySectionsCapability final : public FNexusMultiSectionCapability
{
protected:
	virtual void BuildDefinition(FNexusCapabilityDefinition& Out) const override
	{
		Out.Name = TEXT("GetReliabilitySections");
		Out.InputSchema = BuildSchemaWithSections();
	}
	virtual TSharedPtr<FJsonObject> BuildCapabilitySchema() const override { return FNexusSchema::EmptyObject(); }
	virtual TArray<FString> GetSectionNames() const override { return { TEXT("CurrentMap"), TEXT("graphOverview") }; }
	virtual TArray<FString> GetDefaultSectionNames() const override { return { TEXT("CurrentMap") }; }
	virtual bool ShouldAutoUnloadIntrospected() const override { return false; }
	virtual void ExecuteSection(const FString& SectionName, const TSharedPtr<FJsonObject>&,
		void*, TSharedPtr<FJsonObject>& Detail, FString&) const override
	{
		Detail->SetBoolField(SectionName, true);
	}
};

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusSectionsContractTest,
	"NexusLink.Reliability.SectionsContract",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusSectionsContractTest::RunTest(const FString& Parameters)
{
	FNexusReliabilitySectionsCapability Capability;
	for (const FString& Section : { FString(TEXT("All")), FString(TEXT("CurrentMap")), FString(TEXT("graphOverview")) })
	{
		TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
		Args->SetArrayField(TEXT("Sections"), { MakeShared<FJsonValueString>(Section) });
		const FCapabilityResult Result = Capability.Run(Args);
		if (!TestEqual(TEXT("返回一条结果"), Result.Entries.Num(), 1)) continue;
		const TSharedPtr<FJsonObject> Entry = Result.Entries[0]->AsObject();
		TestFalse(TEXT("合法枚举没有 SectionErrors"), Entry->HasField(TEXT("SectionErrors")));
		TestTrue(TEXT("执行目标 section"), Entry->HasField(Section == TEXT("All") ? TEXT("CurrentMap") : Section));
		if (Section == TEXT("All")) TestTrue(TEXT("All 包含第二个 section"), Entry->HasField(TEXT("graphOverview")));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusResultErrorsContractTest,
	"NexusLink.Reliability.ResultErrors",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusResultErrorsContractTest::RunTest(const FString& Parameters)
{
	for (const TCHAR* Key : { TEXT("Error"), TEXT("CompileError"), TEXT("SaveError"), TEXT("FinalizeError") })
	{
		FCapabilityResult Result;
		Result.TopFields = MakeShared<FJsonObject>();
		Result.TopFields->SetStringField(Key, TEXT("failed"));
		TestTrue(TEXT("收尾错误被聚合"), Result.HasErrors());
		TestTrue(TEXT("MultiTool 同样标记失败"), FNexusCapResultAdapter::Convert(Result, TEXT("Test")).bIsError);
	}
	FCapabilityResult Result;
	TSharedPtr<FJsonObject> Entry = MakeShared<FJsonObject>();
	Entry->SetStringField(TEXT("Error"), TEXT("row missing"));
	Result.Entries.Add(MakeShared<FJsonValueObject>(Entry));
	TestTrue(TEXT("业务条目失败"), Result.HasErrors());
	Entry->RemoveField(TEXT("Error"));
	Entry->SetArrayField(TEXT("SectionErrors"), { MakeShared<FJsonValueObject>(MakeShared<FJsonObject>()) });
	TestTrue(TEXT("section 失败"), Result.HasErrors());
	Entry->RemoveField(TEXT("SectionErrors"));
	TSharedPtr<FJsonObject> Data = MakeShared<FJsonObject>();
	Data->SetStringField(TEXT("Error"), TEXT("业务属性值"));
	Entry->SetObjectField(TEXT("Properties"), Data);
	Entry->SetBoolField(TEXT("bHasCompilerErrors"), true);
	TestFalse(TEXT("读取到错误状态或同名业务属性不等于读取失败"), Result.HasErrors());
	return true;
}

struct FNexusReliabilityTableScope
{
	TStrongObjectPtr<UDataTable> Table;
	FString Path;

	FNexusReliabilityTableScope()
	{
		const FString PackageName = TEXT("/Game/_NexusTest/DT_Reliability_") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
		UPackage* Package = CreatePackage(*PackageName);
		Table.Reset(NewObject<UDataTable>(Package, TEXT("TestTable"), RF_Public));
		Table->RowStruct = FNexusReliabilityTestRow::StaticStruct();
		Path = Table->GetPathName();
	}

	~FNexusReliabilityTableScope() { Table->GetOutermost()->SetDirtyFlag(false); }
};

static TSharedPtr<FJsonObject> ReliabilityRowArgs(const FString& Path, const TCHAR* Action, const TCHAR* RowName)
{
	TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("AssetPath"), Path);
	TSharedPtr<FJsonObject> Operation = MakeShared<FJsonObject>();
	Operation->SetStringField(TEXT("Action"), Action);
	Operation->SetStringField(TEXT("RowName"), RowName);
	Args->SetArrayField(TEXT("Operations"), { MakeShared<FJsonValueObject>(Operation) });
	return Args;
}

static FNexusMcpToolResult ReliabilityBatch(const TArray<TSharedPtr<FJsonObject>>& Arguments,
	const TCHAR* Capability = TEXT("ManageAssetDataTable"))
{
	TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
	TArray<TSharedPtr<FJsonValue>> Calls;
	for (const auto& Inner : Arguments)
	{
		TSharedPtr<FJsonObject> Call = MakeShared<FJsonObject>();
		Call->SetStringField(TEXT("Capability"), Capability);
		Call->SetObjectField(TEXT("Arguments"), Inner);
		Calls.Add(MakeShared<FJsonValueObject>(Call));
	}
	Args->SetArrayField(TEXT("Calls"), Calls);
	Args->SetBoolField(TEXT("bKeepLoaded"), true);
	return FNexusMcpToolRegistry::Get().CreateTool(TEXT("CallCapability"))->Execute(Args);
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusDataTableFieldsLifetimeTest,
	"NexusLink.Reliability.DataTableFieldsAndLifetime",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusDataTableFieldsLifetimeTest::RunTest(const FString& Parameters)
{
	FNexusReliabilityTableScope Scope;
	const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("ManageAssetDataTable"));
	if (!TestNotNull(TEXT("DataTable 能力已注册"), Record)) return false;
	// 隔离 Undo 序列化对行析构计数的影响。
	TGuardValue<decltype(FNexusEditorServices::BeginTransaction)> TransactionGuard(
		FNexusEditorServices::BeginTransaction, [](const FString&) { return TUniquePtr<INexusTransactionHandle>(); });
	TSharedPtr<FJsonObject> Args = ReliabilityRowArgs(Scope.Path, TEXT("Add"), TEXT("Good"));
	TSharedPtr<FJsonObject> Fields = MakeShared<FJsonObject>();
	Fields->SetStringField(TEXT("Label"), TEXT("retained string"));
	Fields->SetNumberField(TEXT("Count"), 42);
	Fields->SetBoolField(TEXT("bEnabled"), true);
	Fields->SetStringField(TEXT("Values"), TEXT("(1,2,3)"));
	const TSharedPtr<FJsonObject> Operation = Args->GetArrayField(TEXT("Operations"))[0]->AsObject();
	Operation->SetObjectField(TEXT("Fields"), Fields);
	const int32 Before = FNexusReliabilityTestRow::DestructionCount;
	TestFalse(TEXT("非空 Fields 可写入"), Record->Instance->Run(Args).HasErrors());
	const FNexusReliabilityTestRow* Row = Scope.Table->FindRow<FNexusReliabilityTestRow>(TEXT("Good"), TEXT("test"));
	if (TestNotNull(TEXT("已新增行"), Row))
	{
		TestEqual(TEXT("字符串成员复制后仍有效"), Row->Label, FString(TEXT("retained string")));
		TestEqual(TEXT("数值"), Row->Count, 42);
		TestTrue(TEXT("布尔"), Row->bEnabled);
		TestEqual(TEXT("容器"), Row->Values.Num(), 3);
	}
	TestTrue(TEXT("成功路径析构临时行"), FNexusReliabilityTestRow::DestructionCount > Before);
	Operation->SetStringField(TEXT("RowName"), TEXT("Bad"));
	Fields->SetStringField(TEXT("Count"), TEXT("invalid_integer"));
	const int32 BeforeFailure = FNexusReliabilityTestRow::DestructionCount;
	TestTrue(TEXT("导入失败被报告"), Record->Instance->Run(Args).HasErrors());
	TestNull(TEXT("导入失败不新增行"), Scope.Table->FindRowUnchecked(TEXT("Bad")));
	TestTrue(TEXT("失败路径也析构临时行"), FNexusReliabilityTestRow::DestructionCount > BeforeFailure);
	Fields->Values.Reset();
	Fields->SetField(TEXT("Count"), MakeShared<FJsonValueNull>());
	Operation->SetStringField(TEXT("RowName"), TEXT("Default"));
	TestFalse(TEXT("null 保留初始化默认值"), Record->Instance->Run(Args).HasErrors());
	Row = Scope.Table->FindRow<FNexusReliabilityTestRow>(TEXT("Default"), TEXT("test"));
	if (TestNotNull(TEXT("默认值行"), Row)) TestEqual(TEXT("默认值未被空串覆盖"), Row->Count, 7);
	Fields->SetStringField(TEXT("UnknownField"), TEXT("value"));
	Operation->SetStringField(TEXT("RowName"), TEXT("Unknown"));
	TestTrue(TEXT("未知字段明确失败"), Record->Instance->Run(Args).HasErrors());
	TestNull(TEXT("未知字段不产生残缺行"), Scope.Table->FindRowUnchecked(TEXT("Unknown")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusBatchFinalizationTest,
	"NexusLink.Reliability.BatchFinalization",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusBatchFinalizationTest::RunTest(const FString& Parameters)
{
	FNexusReliabilityTableScope Scope;
	int32 SaveCount = 0;
	bool bFailSave = false;
	bool bSavedTooEarly = false;
	TGuardValue<decltype(FNexusEditorServices::ApplyManageFinalize)> FinalizeGuard(
		FNexusEditorServices::ApplyManageFinalize,
		[&](const FString&, bool, bool bSave, TSharedPtr<FJsonObject>& Top)
		{
			if (!bSave) return;
			++SaveCount;
			bSavedTooEarly |= Scope.Table->GetRowMap().Num() < 2;
			if (bFailSave) Top->SetStringField(TEXT("SaveError"), TEXT("simulated save failure"));
			else Top->SetBoolField(TEXT("bSaved"), true);
		});
	TSharedPtr<FJsonObject> Add = ReliabilityRowArgs(Scope.Path, TEXT("Add"), TEXT("First"));
	Add->SetBoolField(TEXT("bSaveToDisk"), true);
	const TSharedPtr<FJsonObject> Fail = ReliabilityRowArgs(Scope.Path, TEXT("Remove"), TEXT("Missing"));
	FNexusMcpToolResult Result = ReliabilityBatch({ Add, Fail });
	TestTrue(TEXT("业务条目错误使整批失败"), Result.bIsError);
	TestEqual(TEXT("失败计数"), Result.StructuredContent->GetIntegerField(TEXT("FailureCount")), 1);
	TestEqual(TEXT("失败批不保存"), SaveCount, 0);
	TestTrue(TEXT("内存事务已回滚"), Result.StructuredContent->GetBoolField(TEXT("bRolledBack")));
	TestNull(TEXT("第一条已成功写入的行也被还原"), Scope.Table->FindRowUnchecked(TEXT("First")));
	TSharedPtr<FJsonObject> Second = ReliabilityRowArgs(Scope.Path, TEXT("Add"), TEXT("Second"));
	Second->SetBoolField(TEXT("bSaveToDisk"), true);
	Result = ReliabilityBatch({ Add, Second });
	TestFalse(TEXT("合法批成功"), Result.bIsError);
	TestEqual(TEXT("按请求保存"), SaveCount, 2);
	TestFalse(TEXT("所有内存操作完成前不保存"), bSavedTooEarly);
	Scope.Table->EmptyTable();
	bFailSave = true;
	Result = ReliabilityBatch({ Add, Second });
	TestTrue(TEXT("保存失败上报"), Result.bIsError);
	TestEqual(TEXT("保存失败纳入批量失败计数"), Result.StructuredContent->GetIntegerField(TEXT("FailureCount")), 2);
	TestFalse(TEXT("不谎报磁盘回滚"), Result.StructuredContent->GetBoolField(TEXT("bRolledBack")));
	TestTrue(TEXT("说明磁盘非原子性"), Result.StructuredContent->GetStringField(TEXT("UndoNote")).Contains(TEXT("not atomic")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRedundantReadsTest,
	"NexusLink.Reliability.RedundantReads",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusRedundantReadsTest::RunTest(const FString& Parameters)
{
	const FString PackageName = TEXT("/Game/_NexusTest/M_Reliability_") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
	UPackage* Package = CreatePackage(*PackageName);
	TStrongObjectPtr<UMaterial> Material(NewObject<UMaterial>(Package, TEXT("TestMaterial"), RF_Public));
	TGuardValue<int32> WindowGuard(GetMutableDefault<UNexusLinkSettings>()->RedundantCallWindowSec, 30);
	TSharedPtr<FJsonObject> Inner = MakeShared<FJsonObject>();
	Inner->SetStringField(TEXT("AssetPath"), Material->GetPathName());
	Inner->SetArrayField(TEXT("Sections"), { MakeShared<FJsonValueString>(TEXT("All")) });
	TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("Capability"), TEXT("GetAssetMaterial"));
	Args->SetObjectField(TEXT("Arguments"), Inner);
	Args->SetBoolField(TEXT("bKeepLoaded"), true);
	const auto FirstCaller = FNexusMcpToolRegistry::Get().CreateTool(TEXT("CallCapability"));
	const auto SecondCaller = FNexusMcpToolRegistry::Get().CreateTool(TEXT("CallCapability"));
	TestFalse(TEXT("首次 All 成功"), FirstCaller->Execute(Args).bIsError);
	Inner->SetArrayField(TEXT("Sections"), { MakeShared<FJsonValueString>(TEXT("Params")) });
	const FNexusMcpToolResult Result = SecondCaller->Execute(Args);
	TestFalse(TEXT("另一调用方不被阻断"), Result.bIsError);
	TestTrue(TEXT("提示外仍返回最新参数数据"), Result.StructuredContent->HasField(TEXT("Parameters")));
	TestFalse(TEXT("不再要求复用未知的响应"), Result.OutputText.Contains(TEXT("Skipped:")));
	Package->SetDirtyFlag(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusBatchCompileFailureTest,
	"NexusLink.Reliability.BatchCompileFailure",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusBatchCompileFailureTest::RunTest(const FString& Parameters)
{
	const FString PackageName = TEXT("/Game/_NexusTest/BP_Reliability_") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
	UPackage* Package = CreatePackage(*PackageName);
	TStrongObjectPtr<UBlueprint> Blueprint(FKismetEditorUtilities::CreateBlueprint(AActor::StaticClass(), Package,
		TEXT("TestBlueprint"), BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass()));
	if (!TestNotNull(TEXT("测试蓝图"), Blueprint.Get())) return false;
	int32 CompileCount = 0;
	int32 SaveCount = 0;
	TGuardValue<decltype(FNexusEditorServices::ApplyManageFinalize)> FinalizeGuard(
		FNexusEditorServices::ApplyManageFinalize,
		[&](const FString&, bool bCompile, bool bSave, TSharedPtr<FJsonObject>& Top)
		{
			if (bCompile && ++CompileCount == 2) Top->SetStringField(TEXT("CompileError"), TEXT("simulated compiler failure"));
			if (bSave) ++SaveCount;
		});
	TArray<TSharedPtr<FJsonObject>> Arguments;
	for (const TCHAR* Name : { TEXT("First"), TEXT("Second") })
	{
		TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
		Args->SetStringField(TEXT("AssetPath"), Blueprint->GetPathName());
		Args->SetBoolField(TEXT("bCompile"), true);
		Args->SetBoolField(TEXT("bSaveToDisk"), true);
		TSharedPtr<FJsonObject> Operation = MakeShared<FJsonObject>();
		Operation->SetStringField(TEXT("Action"), TEXT("AddVariable"));
		Operation->SetStringField(TEXT("VariableName"), Name);
		Operation->SetStringField(TEXT("VariableType"), TEXT("float"));
		Args->SetArrayField(TEXT("Operations"), { MakeShared<FJsonValueObject>(Operation) });
		Arguments.Add(Args);
	}
	const FNexusMcpToolResult Result = ReliabilityBatch(Arguments, TEXT("ManageAssetBlueprint"));
	TestTrue(TEXT("编译错误使批量失败"), Result.bIsError);
	TestEqual(TEXT("编译失败不执行任何自动保存"), SaveCount, 0);
	TestEqual(TEXT("已通过编译的前项也不提前保存"), CompileCount, 2);
	TestTrue(TEXT("编译失败触发事务回滚"), Result.StructuredContent->GetBoolField(TEXT("bRolledBack")));
	TestEqual(TEXT("变量修改已还原"), Blueprint->NewVariables.Num(), 0);
	Package->SetDirtyFlag(false);
	return true;
}
#endif
