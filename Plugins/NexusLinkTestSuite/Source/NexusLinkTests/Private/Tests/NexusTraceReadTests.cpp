// Copyright byteyang. All Rights Reserved.

#include "CoreMinimal.h"
#include "Utils/NexusVersionCompat.h"

#if NX_UE_HAS_TRACE_READ && WITH_EDITOR

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "HAL/FileManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/Paths.h"
#include "NexusCapability.h"
#include "NexusCapabilityRegistry.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
#include "ProfilingDebugging/MiscTrace.h"
#include "ProfilingDebugging/TraceAuxiliary.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Utils/NexusEditorTraceUtils.h"
#include "Utils/NexusTraceStatistics.h"
#include <limits>
#include "Capabilities/Trace/NexusTraceSession.h"
#if !NX_UE_HAS_TRACE_STORE_DIRECTORY
#include "Trace/StoreService.h"
#endif

static FNexusCapability* FindTraceCapability(const TCHAR* CapName)
{
	const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(CapName);
	return Record ? &Record->Instance.Get() : nullptr;
}

static const FJsonObject* FirstEntry(const FCapabilityResult& Result)
{
	if (Result.Entries.Num() != 1)
	{
		return nullptr;
	}
	const TSharedPtr<FJsonObject>* Object = nullptr;
	if (!Result.Entries[0]->TryGetObject(Object) || Object == nullptr)
	{
		return nullptr;
	}
	return Object->Get();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FNexusTraceMissingFileTest,
	"NexusLink.Trace.GetTrace.MissingFile",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusTraceMissingFileTest::RunTest(const FString& Parameters)
{
	FNexusCapability* Capability = FindTraceCapability(TEXT("GetTrace"));
	TestNotNull(TEXT("GetTrace registered"), Capability);
	if (Capability == nullptr)
	{
		return false;
	}

	const FString MissingPath = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Profiling"),
		FString::Printf(TEXT("NexusLinkMissing_%s.utrace"), *FGuid::NewGuid().ToString(EGuidFormats::Digits)));

	TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("TracePath"), MissingPath);
	const FCapabilityResult Result = Capability->Run(Args);
	TestTrue(TEXT("missing file is not fatal"), Result.FatalError.IsEmpty());
	const FJsonObject* Entry = FirstEntry(Result);
	TestNotNull(TEXT("one entry"), Entry);
	if (Entry != nullptr)
	{
		FString Error;
		TestTrue(TEXT("entry has Error"), Entry->TryGetStringField(TEXT("Error"), Error) && Error.Contains(TEXT("not found")));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FNexusTraceReadbackTest,
	"NexusLink.Trace.GetTrace.Readback",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusTraceReadbackTest::RunTest(const FString& Parameters)
{
	FNexusCapability* Capability = FindTraceCapability(TEXT("GetTrace"));
	TestNotNull(TEXT("GetTrace registered"), Capability);
	if (Capability == nullptr)
	{
		return false;
	}

	FString TracePath = FPaths::ConvertRelativePathToFull(
		FPaths::Combine(FPaths::ProfilingDir(), TEXT("NexusLinkTraceReadTest.utrace")));
	const bool bHasFixture = FParse::Value(FCommandLine::Get(), TEXT("NexusTraceTestPath="), TracePath);
#if NX_UE_HAS_TRACE_AUXILIARY_START
	if (!bHasFixture)
	{
		IFileManager::Get().Delete(*TracePath);

		// 已有会话会让 Start 直接返回 false。测试只在编辑器里跑，先停掉再录一段很短的文件。
		FTraceAuxiliary::Stop();
		const bool bStarted = FTraceAuxiliary::Start(
			FTraceAuxiliary::EConnectionType::File, *TracePath, TEXT("cpu,frame,bookmark"));
		if (!TestTrue(TEXT("Trace.File started"), bStarted))
		{
			return false;
		}

		{
			TRACE_CPUPROFILER_EVENT_SCOPE_STR("NexusLinkTraceProbe");
			TRACE_BOOKMARK(TEXT("NexusLinkTraceProbe"));
			TRACE_BEGIN_FRAME(TraceFrameType_Game);
			FPlatformProcess::Sleep(0.01f);
			TRACE_END_FRAME(TraceFrameType_Game);
		}
		FTraceAuxiliary::Stop();
	}
#else
	// UE4 不支持进程内 Start/Stop；由带 -tracefile 参数的独立进程生成并关闭文件。
	if (!bHasFixture)
	{
		AddError(TEXT("UE4 readback requires -NexusTraceTestPath=<closed producer trace>"));
		return false;
	}
#endif
	TestTrue(TEXT("trace file exists"), IFileManager::Get().FileExists(*TracePath));

	TSharedPtr<FJsonObject> SummaryArgs = MakeShared<FJsonObject>();
	SummaryArgs->SetStringField(TEXT("TracePath"), TracePath);
	TArray<TSharedPtr<FJsonValue>> SummarySections;
	SummarySections.Add(MakeShared<FJsonValueString>(TEXT("Summary")));
	SummaryArgs->SetArrayField(TEXT("Sections"), SummarySections);

	bool bComplete = false;
	for (int32 Attempt = 0; Attempt < 600 && !bComplete; ++Attempt)
	{
		const FCapabilityResult Result = Capability->Run(SummaryArgs);
		const FJsonObject* Entry = FirstEntry(Result);
		if (Entry != nullptr)
		{
			Entry->TryGetBoolField(TEXT("bAnalysisComplete"), bComplete);
		}
		if (!bComplete)
		{
			FPlatformProcess::Sleep(0.05f);
		}
	}
	if (!TestTrue(TEXT("analysis finished"), bComplete))
	{
		return false;
	}

	TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("TracePath"), TracePath);
	TArray<TSharedPtr<FJsonValue>> Sections;
	Sections.Add(MakeShared<FJsonValueString>(TEXT("Summary")));
	Sections.Add(MakeShared<FJsonValueString>(TEXT("Frames")));
	Sections.Add(MakeShared<FJsonValueString>(TEXT("Timers")));
	Sections.Add(MakeShared<FJsonValueString>(TEXT("Bookmarks")));
	Args->SetArrayField(TEXT("Sections"), Sections);

	const FCapabilityResult Result = Capability->Run(Args);
	TestTrue(TEXT("readback is not fatal"), Result.FatalError.IsEmpty());
	const FJsonObject* Entry = FirstEntry(Result);
	if (!TestNotNull(TEXT("readback entry"), Entry))
	{
		return false;
	}
	TestFalse(TEXT("no section errors"), Entry->HasField(TEXT("SectionErrors")));

	double FrameCount = 0.0;
	TestTrue(TEXT("has frames"), Entry->TryGetNumberField(TEXT("FrameCount"), FrameCount) && FrameCount >= 1.0);

	const TCHAR* NumericFields[] = { TEXT("AverageSeconds"), TEXT("MedianSeconds"), TEXT("P95Seconds"), TEXT("MaxSeconds"), TEXT("StartTime"), TEXT("EndTime"), TEXT("TotalTimerCount") };
	for (const TCHAR* Field : NumericFields)
	{
		double Value = 0.0;
		TestTrue(Field, Entry->TryGetNumberField(Field, Value) && FMath::IsFinite(Value));
	}

	const TArray<TSharedPtr<FJsonValue>>* Timers = nullptr;
	TestTrue(TEXT("has timers"), Entry->TryGetArrayField(TEXT("Timers"), Timers) && Timers != nullptr && Timers->Num() > 0);

	const TArray<TSharedPtr<FJsonValue>>* Bookmarks = nullptr;
	bool bFoundBookmark = false;
	if (Entry->TryGetArrayField(TEXT("Bookmarks"), Bookmarks) && Bookmarks != nullptr)
	{
		for (const TSharedPtr<FJsonValue>& Value : *Bookmarks)
		{
			const TSharedPtr<FJsonObject>* Bookmark = nullptr;
			FString Text;
			if (Value.IsValid() && Value->TryGetObject(Bookmark) && Bookmark != nullptr
				&& (*Bookmark)->TryGetStringField(TEXT("Text"), Text) && Text.Contains(TEXT("NexusLinkTraceProbe")))
			{
				bFoundBookmark = true;
				break;
			}
		}
	}
	TestTrue(TEXT("bookmark text"), bFoundBookmark);
	// 未指定 Sections 时仍默认 Summary + Frames；重复读取必须命中同一份分析。
	TSharedPtr<FJsonObject> DefaultArgs = MakeShared<FJsonObject>();
	DefaultArgs->SetStringField(TEXT("TracePath"), TracePath);
	DefaultArgs->SetNumberField(TEXT("TraceId"), -1); // 显式路径优先。
	const FJsonObject* DefaultEntry = nullptr;
	const FCapabilityResult DefaultResult = Capability->Run(DefaultArgs);
	DefaultEntry = FirstEntry(DefaultResult);
	TestTrue(TEXT("default sections"), DefaultEntry && DefaultEntry->HasField(TEXT("GameFrameCount"))
		&& DefaultEntry->HasField(TEXT("FrameCount")) && !DefaultEntry->HasField(TEXT("Timers")));
	Args->SetNumberField(TEXT("StartTime"), 0.0);
	Args->SetNumberField(TEXT("EndTime"), 1.0e6);
	const FCapabilityResult WindowResult = Capability->Run(Args);
	const FJsonObject* WindowEntry = FirstEntry(WindowResult);
	TestTrue(TEXT("explicit window"), WindowEntry && !WindowEntry->HasField(TEXT("SectionErrors")));
	Args->SetNumberField(TEXT("TimerLimit"), 1);
	const FCapabilityResult LimitedResult = Capability->Run(Args);
	const FJsonObject* Limited = FirstEntry(LimitedResult);
	TestTrue(TEXT("timer truncation explicitly reported"), Limited && Limited->HasField(TEXT("bTimersTruncated"))
		&& Limited->GetNumberField(TEXT("TotalTimerCount")) >= Limited->GetArrayField(TEXT("Timers")).Num());
	Args->SetNumberField(TEXT("EndTime"), 0.0);
	const FCapabilityResult InvalidWindowResult = Capability->Run(Args);
	const FJsonObject* InvalidWindowEntry = FirstEntry(InvalidWindowResult);
	TestTrue(TEXT("invalid window"), InvalidWindowEntry && InvalidWindowEntry->HasField(TEXT("SectionErrors")));

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusTraceStatisticsTest, "NexusLink.Trace.Statistics.WindowAndMedian",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusTraceStatisticsTest::RunTest(const FString& Parameters)
{
	TestTrue(TEXT("Complete contained frame"), FNexusTraceStatistics::AcceptFrame(1, 2, true, 1, 2));
	TestFalse(TEXT("Partial left frame excluded"), FNexusTraceStatistics::AcceptFrame(.5, 1.5, true, 1, 2));
	TestFalse(TEXT("Partial right frame excluded"), FNexusTraceStatistics::AcceptFrame(1.5, 2.5, true, 1, 2));
	TestFalse(TEXT("Unfinished frame excluded"), FNexusTraceStatistics::AcceptFrame(1, std::numeric_limits<double>::infinity(), false, 0, 0));
	FJsonObject Stats;
	FNexusTraceStatistics::Write({1, 2, 3, 100}, Stats);
	TestEqual(TEXT("Even median"), Stats.GetNumberField(TEXT("MedianSeconds")), 2.5);
	TestEqual(TEXT("Mean"), Stats.GetNumberField(TEXT("AverageSeconds")), 26.5);
	TestEqual(TEXT("P95 nearest rank"), Stats.GetNumberField(TEXT("P95Seconds")), 100.0);
	FNexusTraceStatistics::Write({1, 3, 9}, Stats);
	TestEqual(TEXT("Odd median"), Stats.GetNumberField(TEXT("MedianSeconds")), 3.0);
	return true;
}

// 独立进程带 -trace=cpu,frame,bookmark -tracefile=<path> 运行本用例，退出后文件才关闭。
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusTraceRecordProbeTest, "NexusLink.Trace.RecordProbe",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusTraceRecordProbeTest::RunTest(const FString& Parameters)
{
	TRACE_CPUPROFILER_EVENT_SCOPE_STR("NexusLinkTraceProbe");
	TRACE_BOOKMARK(TEXT("NexusLinkTraceProbe"));
	TRACE_BEGIN_FRAME(TraceFrameType_Game);
	FPlatformProcess::Sleep(0.01f);
	TRACE_END_FRAME(TraceFrameType_Game);
	return true;
}

class FNexusTraceTestStream final : public FNexusTraceInputStream
{
public:
	explicit FNexusTraceTestStream(uint32 InSize) : Remaining(InSize) {}
	virtual int32 Read(void* Data, uint32 Size) override
	{
		const uint32 Count = FMath::Min(Size, Remaining);
		FMemory::Memzero(Data, Count);
		Remaining -= Count;
		return static_cast<int32>(Count);
	}
private:
	uint32 Remaining;
};

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusTraceStreamBoundsTest, "NexusLink.Trace.Stream.Bounds",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusTraceStreamBoundsTest::RunTest(const FString& Parameters)
{
	const auto ReadError = MakeShared<FThreadSafeCounter, ESPMode::ThreadSafe>();
	TUniquePtr<FNexusTraceInputStream> Source(new FNexusTraceTestStream(8));
	FNexusTraceSnapshotStream Snapshot(MoveTemp(Source), 3, ReadError);
	uint8 Buffer[16];
	TestEqual(TEXT("snapshot caps oversized read"), Snapshot.Read(Buffer, sizeof(Buffer)), 3);
	TestEqual(TEXT("snapshot EOF ignores later bytes"), Snapshot.Read(Buffer, sizeof(Buffer)), 0);
	TestEqual(TEXT("complete snapshot has no error"), ReadError->GetValue(), 0);
	TUniquePtr<FNexusTraceInputStream> ShortSource(new FNexusTraceTestStream(2));
	FNexusTraceSnapshotStream ShortSnapshot(MoveTemp(ShortSource), 3, ReadError);
	TestEqual(TEXT("partial read"), ShortSnapshot.Read(Buffer, sizeof(Buffer)), 2);
	TestEqual(TEXT("premature EOF"), ShortSnapshot.Read(Buffer, sizeof(Buffer)), -1);
	TestEqual(TEXT("premature EOF recorded"), ReadError->GetValue(), 1);
	return true;
}

#if !NX_UE_HAS_TRACE_STORE_DIRECTORY
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusTraceLegacyStoreTest, "NexusLink.Trace.Store.Legacy",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusTraceLegacyStoreTest::RunTest(const FString& Parameters)
{
	FString Fixture;
	if (!FParse::Value(FCommandLine::Get(), TEXT("NexusTraceTestPath="), Fixture))
	{
		AddError(TEXT("Store test requires -NexusTraceTestPath=<closed producer trace>"));
		return false;
	}
	const FString Directory = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("TraceStoreTest"),
		FGuid::NewGuid().ToString(EGuidFormats::Digits));
	IFileManager::Get().MakeDirectory(*Directory, true);
	const FString StoredPath = Directory / TEXT("probe.utrace");
	if (!TestEqual(TEXT("copy fixture"), IFileManager::Get().Copy(*StoredPath, *Fixture), static_cast<uint32>(COPY_OK))) return false;
	Trace::FStoreService::FDesc Desc{};
	Desc.StoreDir = *Directory;
	Desc.RecorderPort = -1;
	Desc.ThreadCount = 2;
	TUniquePtr<Trace::FStoreService> Service(Trace::FStoreService::Create(Desc));
	if (!TestNotNull(TEXT("isolated Store"), Service.Get())) return false;
	const uint32 Port = Service->GetPort();
	TUniquePtr<FNexusTraceStoreClient> Client = FNexusEditorTraceUtils::CreateStoreClient(TEXT("127.0.0.1"), Port);
	if (!TestNotNull(TEXT("Store client"), Client.Get())) return false;
	const FNexusTraceStoreClient::FTraceInfo* Info = Client->GetTraceInfo(0);
	if (!TestNotNull(TEXT("Store indexed trace"), Info)) return false;
	const uint32 TraceId = Info->GetId();
	TArray<TSharedPtr<FJsonValue>> Traces;
	FNexusTraceSessionCache::CollectRecentTraces(100, Traces, Port);
	bool bFound = false;
	for (const auto& Value : Traces)
	{
		const TSharedPtr<FJsonObject> Item = Value->AsObject();
		double ListedId = -1;
		if (Item->TryGetNumberField(TEXT("TraceId"), ListedId) && ListedId == TraceId)
		{
			bFound = true;
			TestTrue(TEXT("legacy Path empty"), Item->GetStringField(TEXT("Path")).IsEmpty());
			TestTrue(TEXT("timestamp is Unix seconds"), Item->GetNumberField(TEXT("Timestamp")) > 1500000000.0);
		}
	}
	TestTrue(TEXT("Store trace listed"), bFound);
	TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
	Args->SetNumberField(TEXT("TraceId"), TraceId);
	FString Path, Error;
	const auto Session = FNexusTraceSessionCache::Open(Args, Path, Error, Port);
	if (!TestNotNull(TEXT("Store stream session"), Session.Get())) return false;
	Session->Wait();
	TestTrue(TEXT("legacy TracePath empty"), Path.IsEmpty());
	const auto Reused = FNexusTraceSessionCache::Open(Args, Path, Error, Port);
	TestTrue(TEXT("Store session reused"), Session.Get() == Reused.Get());
	{
		FNexusTraceReadScope Scope(*Session);
		TestTrue(TEXT("Store has frames"), FNexusEditorTraceUtils::ReadFrames(*Session).GetFrameCount(TraceFrameType_Game) > 0);
		const FNexusTraceTimingProvider* Timing = FNexusEditorTraceUtils::ReadTiming(*Session);
		TestTrue(TEXT("Store has CPU data"), Timing && FNexusEditorTraceUtils::HasCpuTiming(*Timing));
		bool bFoundBookmark = false;
		FNexusEditorTraceUtils::ReadBookmarks(*Session).EnumerateBookmarks(0.0, 1.0e12, [&](const FNexusTraceBookmark& Bookmark)
		{
			if (Bookmark.Text && FString(Bookmark.Text).Contains(TEXT("NexusLinkTraceProbe"))) bFoundBookmark = true;
		});
		TestTrue(TEXT("Store bookmark"), bFoundBookmark);
	}
	Args->SetNumberField(TEXT("TraceId"), 0);
	TestFalse(TEXT("missing id fails"), FNexusTraceSessionCache::Open(Args, Path, Error, Port).IsValid());
	TestTrue(TEXT("missing id error"), Error.Contains(TEXT("not found")));
	Client.Reset();
	Service.Reset();
	IFileManager::Get().Delete(*StoredPath);
	IFileManager::Get().DeleteDirectory(*Directory);
	return true;
}
#endif

#endif
