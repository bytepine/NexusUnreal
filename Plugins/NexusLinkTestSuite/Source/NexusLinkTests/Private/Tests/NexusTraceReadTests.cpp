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

	const FString TracePath = FPaths::ConvertRelativePathToFull(
		FPaths::Combine(FPaths::ProfilingDir(), TEXT("NexusLinkTraceReadTest.utrace")));
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
	TestTrue(TEXT("trace file exists"), IFileManager::Get().FileExists(*TracePath));

	TSharedPtr<FJsonObject> SummaryArgs = MakeShared<FJsonObject>();
	SummaryArgs->SetStringField(TEXT("TracePath"), TracePath);
	TArray<TSharedPtr<FJsonValue>> SummarySections;
	SummarySections.Add(MakeShared<FJsonValueString>(TEXT("Summary")));
	SummaryArgs->SetArrayField(TEXT("Sections"), SummarySections);

	bool bComplete = false;
	for (int32 Attempt = 0; Attempt < 100 && !bComplete; ++Attempt)
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
	return true;
}

#endif
