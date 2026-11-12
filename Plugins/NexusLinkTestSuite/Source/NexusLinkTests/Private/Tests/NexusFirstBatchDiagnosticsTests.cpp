// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"
#include "NexusLinkBuildConfig.h"
#include "Utils/NexusVersionCompat.h"
#if WITH_EDITOR && NEXUSLINK_WITH_SERVER
#include "Server/NexusMcpDispatcher.h"
#include "NexusCapabilityRegistry.h"
#include "Utils/NexusArgs.h"
#include "Utils/NexusJsonUtils.h"
#include "WidgetBlueprint.h"
#include "Blueprint/WidgetBlueprintGeneratedClass.h"
#include "Blueprint/UserWidget.h"
#include "Blueprint/WidgetTree.h"
#include "Components/TextBlock.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"
#include "HAL/FileManager.h"
#include "UObject/StrongObjectPtr.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonReader.h"

static FCapabilityResult FirstBatchCall(const TCHAR* Name, const TSharedPtr<FJsonObject>& Args)
{
	const auto* Record = FNexusCapabilityRegistry::Get().FindRecordByName(Name);
	return Record ? Record->Instance->Run(Args) : FCapabilityResult::MakeFatal(TEXT("Capability not registered"));
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusBusyProtocolTest, "NexusLink.FirstBatch.BusyProtocol", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusBusyProtocolTest::RunTest(const FString& Parameters)
{
	FNexusMcpDispatcher Dispatcher([](const FString&) {});
	TSharedPtr<FJsonObject> Response;
	auto Receive = [&](const FString& Json) { FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json), Response); };
	{
		TGuardValue<bool> SlowGuard(GIsSlowTask, true);
		Dispatcher.DispatchDirect(TEXT(R"({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"MustNotExecute"}})"), Receive);
		if (!TestTrue(TEXT("忙碌响应有效"), Response.IsValid() && Response->HasField(TEXT("error")))) return false;
		const auto Error = Response->GetObjectField(TEXT("error"));
		TestEqual(TEXT("忙碌错误码"), static_cast<int32>(Error->GetNumberField(TEXT("code"))), -32002);
		const auto Data = Error->GetObjectField(TEXT("data"));
		TestEqual(TEXT("错误类别"), Data->GetStringField(TEXT("ErrorKind")), FString(TEXT("EditorBusy")));
		TestEqual(TEXT("慢任务原因"), Data->GetStringField(TEXT("Reason")), FString(TEXT("SlowTaskInProgress")));
		TestFalse(TEXT("请求未执行"), Data->GetBoolField(TEXT("bExecuted")));
		Dispatcher.Dispatch(TEXT(R"({"jsonrpc":"2.0","id":2,"method":"initialize","params":{}})"), Receive);
		TestTrue(TEXT("忙碌握手不改变状态"), Dispatcher.GetState() == ENexusMcpSessionState::WaitingForInitialize);
		Dispatcher.DispatchDirect(TEXT(R"({"jsonrpc":"2.0","id":3,"method":"ping"})"), Receive);
		TestTrue(TEXT("忙碌时 ping 仍可响应"), Response->HasField(TEXT("result")));
	}
	Dispatcher.DispatchDirect(TEXT(R"({"jsonrpc":"2.0","id":4,"method":"tools/list"})"), Receive);
	TestTrue(TEXT("退出慢任务后正常发现"), Response->HasField(TEXT("result")));
	auto Args = MakeShared<FJsonObject>(); Args->SetNumberField(TEXT("Number"), 1e100);
	TestEqual(TEXT("整数越界不会执行未定义转换"), FNexusArgs(Args).Int(TEXT("Number")), MIN_int32);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusWidgetProvenanceTest, "NexusLink.FirstBatch.WidgetProvenance", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusWidgetProvenanceTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UWidgetBlueprint> Blueprint(Cast<UWidgetBlueprint>(FKismetEditorUtilities::CreateBlueprint(
		UUserWidget::StaticClass(), GetTransientPackage(), MakeUniqueObjectName(GetTransientPackage(), UWidgetBlueprint::StaticClass()),
		BPTYPE_Normal, UWidgetBlueprint::StaticClass(), UWidgetBlueprintGeneratedClass::StaticClass())));
	if (!TestNotNull(TEXT("临时 Widget Blueprint"), Blueprint.Get())) return false;
	if (!Blueprint->WidgetTree) Blueprint->WidgetTree = NewObject<UWidgetTree>(Blueprint.Get());
	auto* Widget = Blueprint->WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("EvidenceText"));
	Blueprint->WidgetTree->RootWidget = Widget; Widget->SetRenderOpacity(0.25f);
	FDelegateEditorBinding Binding; Binding.ObjectName = Widget->GetName(); Binding.PropertyName = TEXT("RenderOpacityDelegate"); Binding.FunctionName = TEXT("UnconfirmedGetter");
	Blueprint->Bindings.Add(Binding);
	auto Args = MakeShared<FJsonObject>(); Args->SetStringField(TEXT("AssetPath"), Blueprint->GetPathName());
	Args->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("PropertyOverrides"))});
	Args->SetArrayField(TEXT("PropertyPaths"), {MakeShared<FJsonValueString>(TEXT("RenderOpacity"))});
	const auto Read = FirstBatchCall(TEXT("GetAssetUserWidget"), Args);
	if (!TestFalse(TEXT("来源查询成功"), Read.HasErrors()) || !Read.Entries.Num()) return false;
	const auto Records = Read.Entries[0]->AsObject()->GetArrayField(TEXT("PropertyOverrides"));
	if (!TestEqual(TEXT("一个控件属性"), Records.Num(), 1)) return false;
	const auto Record = Records[0]->AsObject();
	TestFalse(TEXT("不声明运行时赢家"), Record->GetBoolField(TEXT("bRuntimeWinnerCertain")));
	const FString Value = Record->GetObjectField(TEXT("LastStaticSource"))->GetObjectField(TEXT("Property"))->GetStringField(TEXT("Value"));
	TestTrue(TEXT("控件树覆盖值可回读"), FMath::IsNearlyEqual(FCString::Atof(*Value), 0.25f));
	bool bBindingFound = false;
	for (const auto& Source : Record->GetArrayField(TEXT("Sources")))
	{
		FString Kind;
		if (Source->AsObject()->TryGetStringField(TEXT("Kind"), Kind) && Kind == TEXT("LegacyBinding")) bBindingFound = true;
	}
	TestTrue(TEXT("Delegate 属性关联到其值属性"), bBindingFound);
	Args->SetNumberField(TEXT("Offset"), 1);
	const auto Page = FirstBatchCall(TEXT("GetAssetUserWidget"), Args);
	TestEqual(TEXT("分页不重复前页"), Page.Entries[0]->AsObject()->GetArrayField(TEXT("PropertyOverrides")).Num(), 0);
	return true;
}

#if NX_UE_HAS_CSV_PROFILER_UTILS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusProfilerCsvQueryTest, "NexusLink.FirstBatch.CsvQuery", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusProfilerCsvQueryTest::RunTest(const FString& Parameters)
{
	const FString Directory = FPaths::ConvertRelativePathToFull(FPaths::ProfilingDir()) / TEXT("NexusFirstBatch");
	IFileManager::Get().MakeDirectory(*Directory, true);
	const FString Path = Directory / (FGuid::NewGuid().ToString(EGuidFormats::Digits) + TEXT(".csv"));
	ON_SCOPE_EXIT { IFileManager::Get().Delete(*Path); };
	FFileHelper::SaveStringToFile(TEXT("FrameTime,GameThread,events\n10,1,Start\n20,2,Middle\n30,3,End\n"), *Path);
	auto Args = MakeShared<FJsonObject>(); Args->SetStringField(TEXT("Action"), TEXT("Stats")); Args->SetStringField(TEXT("CapturePath"), Path);
	Args->SetNumberField(TEXT("FrameStart"), 1); Args->SetNumberField(TEXT("FrameEnd"), 3); Args->SetStringField(TEXT("StatFilter"), TEXT("FrameTime"));
	auto Read = FirstBatchCall(TEXT("GetProfilerCsv"), Args);
	if (!TestFalse(TEXT("读取 CSV 区间"), Read.HasErrors()) || !Read.Entries.Num()) return false;
	const auto Stats = Read.Entries[0]->AsObject()->GetArrayField(TEXT("Stats"));
	if (!TestEqual(TEXT("按名称过滤"), Stats.Num(), 1)) return false;
	const auto Stat = Stats[0]->AsObject();
	TestEqual(TEXT("区间均值"), Stat->GetNumberField(TEXT("Mean")), 25.0);
	TestEqual(TEXT("区间总和"), Stat->GetNumberField(TEXT("Total")), 50.0);
	TestEqual(TEXT("区间样本数"), static_cast<int32>(Stat->GetNumberField(TEXT("SampleCount"))), 2);
	// 真实捕获将 EVENTS 放在第一列；流式捕获用尾部完整表头补足早期未出现的统计项。
	for (bool bHeaderAtEnd : {false, true})
	{
		const FString Csv = FString(bHeaderAtEnd ? TEXT("EVENTS,FrameTime\n,10\n") : TEXT("EVENTS,FrameTime,GameThread\n,10,1\n"))
			+ TEXT("\"Begin,phase \"\"A\"\";Tick\",20,2\n\"\",30,3\n")
			+ (bHeaderAtEnd ? TEXT("EVENTS,FrameTime,GameThread\n[HasHeaderRowAtEnd],1\n") : TEXT(""));
		FFileHelper::SaveStringToFile(Csv, *Path);
		Read = FirstBatchCall(TEXT("GetProfilerCsv"), Args);
		if (!TestFalse(TEXT("含空 EVENTS 的捕获可读"), Read.HasErrors()) || !Read.Entries.Num()) return false;
		const auto FrameStats = Read.Entries[0]->AsObject()->GetArrayField(TEXT("Stats"));
		if (!TestEqual(TEXT("统计列不偏移"), FrameStats.Num(), 1)) return false;
		TestEqual(TEXT("FrameTime 区间均值不受空事件影响"), FrameStats[0]->AsObject()->GetNumberField(TEXT("Mean")), 25.0);
		Args->SetStringField(TEXT("StatFilter"), TEXT("GameThread"));
		auto GameThread = FirstBatchCall(TEXT("GetProfilerCsv"), Args);
		if (!TestFalse(TEXT("末尾统计列可读"), GameThread.HasErrors()) || !GameThread.Entries.Num()) return false;
		TestEqual(TEXT("GameThread 未被事件列吞掉"), GameThread.Entries[0]->AsObject()->GetArrayField(TEXT("Stats"))[0]->AsObject()->GetNumberField(TEXT("Total")), 5.0);
		Args->SetStringField(TEXT("Action"), TEXT("Events")); Args->SetNumberField(TEXT("FrameStart"), 0);
		auto EventsRead = FirstBatchCall(TEXT("GetProfilerCsv"), Args);
		if (!TestFalse(TEXT("事件可读"), EventsRead.HasErrors()) || !EventsRead.Entries.Num()) return false;
		const auto Events = EventsRead.Entries[0]->AsObject()->GetArrayField(TEXT("Events"));
		if (!TestEqual(TEXT("空事件不生成记录"), Events.Num(), 2)) return false;
		TestEqual(TEXT("引号及逗号保留"), Events[0]->AsObject()->GetStringField(TEXT("Name")), FString(TEXT("Begin,phase \"A\"")));
		TestEqual(TEXT("事件帧号不偏移"), static_cast<int32>(Events[0]->AsObject()->GetNumberField(TEXT("Frame"))), 1);
		TestEqual(TEXT("分号分隔事件"), Events[1]->AsObject()->GetStringField(TEXT("Name")), FString(TEXT("Tick")));
		Args->SetStringField(TEXT("Action"), TEXT("Stats")); Args->SetStringField(TEXT("StatFilter"), TEXT("FrameTime")); Args->SetNumberField(TEXT("FrameStart"), 1);
	}
	Args->SetNumberField(TEXT("FrameEnd"), 99);
	TestTrue(TEXT("越界区间拒绝"), FirstBatchCall(TEXT("GetProfilerCsv"), Args).HasErrors());
	Args->SetNumberField(TEXT("FrameEnd"), 3);
	FFileHelper::SaveStringToFile(TEXT("FrameTime,GameThread\n1,2,3\n"), *Path);
	TestTrue(TEXT("坏 CSV 在原生解析前拒绝"), FirstBatchCall(TEXT("GetProfilerCsv"), Args).HasErrors());
	Args->SetStringField(TEXT("CapturePath"), FPaths::ProjectDir() / TEXT("../outside.csv"));
	TestTrue(TEXT("Saved 之外的路径拒绝"), FirstBatchCall(TEXT("GetProfilerCsv"), Args).HasErrors());
	return true;
}
#endif
#endif
