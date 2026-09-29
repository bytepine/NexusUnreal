// Copyright byteyang. All Rights Reserved.

#include "CoreMinimal.h"
#include "Log/NexusLogCapture.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FNexusLogWatchCollapseTest,
	"NexusLink.Log.Watch.CollapseFilterDrop",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusLogWatchCollapseTest::RunTest(const FString& Parameters)
{
	FNexusLogCapture& Cap = FNexusLogCapture::Get();
	Cap.DisarmWatch();

	const FString Token = FString::Printf(TEXT("NXWATCH_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits));

	FNexusLogWatchSpec Spec;
	Spec.TextIncludes.Add(Token);
	Spec.MinVerbosity = ELogVerbosity::All;
	Cap.ArmWatch(Spec);

	Cap.AppendEntry(TEXT("LogNexusWatch"), ELogVerbosity::Log, Token);
	Cap.AppendEntry(TEXT("LogNexusWatch"), ELogVerbosity::Log, Token);
	Cap.AppendEntry(TEXT("LogNexusWatch"), ELogVerbosity::Log, Token + TEXT("_other"));
	Cap.AppendEntry(TEXT("LogNexusWatch"), ELogVerbosity::Log, TEXT("unrelated"));

	int32 Dropped = -1;
	int32 ArmedAt = -1;
	TArray<FNexusLogEntry> Entries = Cap.CopyWatchEntries(Dropped, ArmedAt);
	TestEqual(TEXT("include filter keeps two distinct lines"), Entries.Num(), 2);
	if (Entries.Num() == 2)
	{
		TestEqual(TEXT("consecutive duplicates collapse"), Entries[0].Repeat, 2);
		TestEqual(TEXT("collapsed message"), Entries[0].Message, Token);
		TestEqual(TEXT("different message stays"), Entries[1].Message, Token + TEXT("_other"));
		TestEqual(TEXT("single line repeat"), Entries[1].Repeat, 1);
	}
	TestEqual(TEXT("no drop yet"), Dropped, 0);

	Spec.TextExcludes.Add(TEXT("SKIP"));
	Cap.ArmWatch(Spec);
	Cap.AppendEntry(TEXT("LogNexusWatch"), ELogVerbosity::Log, Token + TEXT(" SKIP"));
	Cap.AppendEntry(TEXT("LogNexusWatch"), ELogVerbosity::Log, Token + TEXT(" KEEP"));
	Entries = Cap.CopyWatchEntries(Dropped, ArmedAt);
	TestEqual(TEXT("exclude drops one line"), Entries.Num(), 1);
	if (Entries.Num() == 1)
	{
		TestTrue(TEXT("kept line"), Entries[0].Message.Contains(TEXT("KEEP")));
	}

	Spec.TextExcludes.Reset();
	Spec.Categories.Add(TEXT("LogNexusWatch"));
	Cap.ArmWatch(Spec);
	Cap.AppendEntry(TEXT("LogOther"), ELogVerbosity::Log, Token);
	Cap.AppendEntry(TEXT("LogNexusWatch"), ELogVerbosity::Log, Token);
	Entries = Cap.CopyWatchEntries(Dropped, ArmedAt);
	TestEqual(TEXT("category filter"), Entries.Num(), 1);
	if (Entries.Num() == 1)
	{
		TestEqual(TEXT("category kept"), Entries[0].Category, FString(TEXT("LogNexusWatch")));
	}

	Spec.Categories.Reset();
	Cap.ArmWatch(Spec);
	const int32 N = FNexusLogCapture::MaxWatchEntries + 1;
	for (int32 i = 0; i < N; ++i)
	{
		Cap.AppendEntry(TEXT("LogNexusWatch"), ELogVerbosity::Log,
			FString::Printf(TEXT("%s_%d"), *Token, i));
	}
	Entries = Cap.CopyWatchEntries(Dropped, ArmedAt);
	TestEqual(TEXT("watch caps at MaxWatchEntries"), Entries.Num(), FNexusLogCapture::MaxWatchEntries);
	TestEqual(TEXT("overflow counts a drop"), Dropped, 1);
	if (Entries.Num() > 0)
	{
		TestFalse(TEXT("oldest overwritten"), Entries[0].Message.EndsWith(TEXT("_0")));
		TestTrue(TEXT("newest kept"), Entries.Last().Message.EndsWith(FString::Printf(TEXT("_%d"), N - 1)));
	}

	Cap.DisarmWatch();
	TestFalse(TEXT("disarmed"), Cap.IsWatchArmed());
	return true;
}
