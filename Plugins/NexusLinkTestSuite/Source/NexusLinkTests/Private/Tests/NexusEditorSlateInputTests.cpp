// Copyright byteyang. All Rights Reserved.
#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#if WITH_EDITOR
#include "NexusCapabilityRegistry.h"
#include "NexusEditorOperation.h"
#include "Framework/Application/SlateApplication.h"
#include "Widgets/SWindow.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Dom/JsonValue.h"
#include "Misc/App.h"
#include "Misc/Guid.h"

class FNexusSlateInputProbe final : public IAutomationLatentCommand
{
	FAutomationTestBase* Test;
	TSharedPtr<SWindow> Window;
	TSharedPtr<SEditableTextBox> Input;
	TSharedPtr<FNexusEditorOperation> Pending;
	FString Ref, WindowRef, Seed = FGuid::NewGuid().ToString(), Owner = FGuid::NewGuid().ToString();
	int32 Phase = 0, CommitsBeforeEnter = 0;
	TSharedRef<int32> Commits = MakeShared<int32>(0);
	double Deadline = FPlatformTime::Seconds() + 40, ReadyAt = 0;

	TSharedPtr<FNexusEditorOperation> Call(const TCHAR* Name, const TSharedPtr<FJsonObject>& Args)
	{
		const auto* Record = FNexusCapabilityRegistry::Get().FindRecordByName(Name);
		if (!Record) return nullptr;
		const auto Result = Record->Instance->Run(Args);
		if (Result.Entries.Num() != 1 || Result.Entries[0]->Type != EJson::Object) return nullptr;
		FString Id; Result.Entries[0]->AsObject()->TryGetStringField(TEXT("OperationId"), Id);
		return FNexusEditorOperations::Find(Id);
	}
public:
	explicit FNexusSlateInputProbe(FAutomationTestBase* InTest) : Test(InTest) {}
	~FNexusSlateInputProbe() { if (Window.IsValid() && FSlateApplication::IsInitialized()) Window->RequestDestroyWindow(); }
	bool Update() override
	{
		TGuardValue<FString> Scope(FNexusEditorOperations::RequestOwner(), Owner);
		if (FPlatformTime::Seconds() > Deadline) { Test->AddError(TEXT("Slate input probe timed out")); return true; }
		if (Phase == 0)
		{
			Window = SNew(SWindow).Title(FText::FromString(TEXT("Nexus Slate Input Probe ") + Owner)).ClientSize(FVector2D(420, 120))
				[SAssignNew(Input, SEditableTextBox).Text(FText::FromString(Seed))
				.OnTextCommitted_Lambda([Counter = Commits](const FText&, ETextCommit::Type) { ++Counter.Get(); })];
			FSlateApplication::Get().AddWindow(Window.ToSharedRef());
			ReadyAt = FPlatformTime::Seconds() + 0.5; Phase = 1; return false;
		}
		if (FPlatformTime::Seconds() < ReadyAt) return false;
		if (Pending.IsValid() && Pending->IsRunning()) return false;
		if (Pending.IsValid())
		{
            if (Phase == 11) {
                const TArray<TSharedPtr<FJsonValue>>* Windows = nullptr;
                if (Pending->Result.IsValid() && Pending->Result->TryGetArrayField(TEXT("Windows"), Windows))
                    for (const auto& Entry : *Windows) if (Entry->AsObject()->GetStringField(TEXT("Title")) == TEXT("Nexus Slate Input Probe ") + Owner) WindowRef = Entry->AsObject()->GetStringField(TEXT("Ref"));
                if (WindowRef.IsEmpty()) { Test->AddError(TEXT("Probe window not enumerated")); return true; }
            }
            else if (Phase == 2)
			{
				if (Pending->State != TEXT("Completed") || !Pending->Result.IsValid()) { Test->AddError(TEXT("Snapshot failed")); return true; }
				const TArray<TSharedPtr<FJsonValue>>* Nodes = nullptr;
				if (Pending->Result->TryGetArrayField(TEXT("Nodes"), Nodes))
					for (const auto& Node : *Nodes) { auto Object = Node->AsObject(); if (Object->GetStringField(TEXT("Text")) == Seed) Object->TryGetStringField(TEXT("Ref"), Ref); }
				FString Snapshot;
				if (Ref.IsEmpty() && Pending->Result->TryGetStringField(TEXT("Snapshot"), Snapshot))
				{
					const int32 Label = Snapshot.Find(Seed);
                    if (Label != INDEX_NONE) {
                        const int32 RowStart = Snapshot.Find(TEXT("\n"), ESearchCase::CaseSensitive, ESearchDir::FromEnd, Label);
                        const int32 RowEnd = Snapshot.Find(TEXT("\n"), ESearchCase::CaseSensitive, ESearchDir::FromStart, Label);
                        const FString Row = Snapshot.Mid(RowStart == INDEX_NONE ? 0 : RowStart + 1, (RowEnd == INDEX_NONE ? Snapshot.Len() : RowEnd) - (RowStart == INDEX_NONE ? 0 : RowStart + 1));
                        const int32 Start = Row.Find(TEXT("[ref=")); const int32 End = Row.Find(TEXT("]"), ESearchCase::CaseSensitive, ESearchDir::FromStart, Start);
                        if (Start != INDEX_NONE && End > Start) Ref = Row.Mid(Start + 5, End - Start - 5);
                    }
				}
				if (Ref.IsEmpty()) { Test->AddError(TEXT("Probe textbox ref not present in snapshot")); return true; }
			}
			else if (Phase < 6 && Pending->State != TEXT("Completed")) { Test->AddError(Pending->Message); return true; }
			else if (Phase >= 6 && Pending->State != TEXT("Failed")) { Test->AddError(TEXT("Disabled or detached ref unexpectedly accepted")); return true; }
			Pending.Reset();
		}
		auto Args = MakeShared<FJsonObject>();
		if (Phase == 1) { Args->SetStringField(TEXT("Action"), TEXT("Windows")); Pending = Call(TEXT("GetEditorSlate"), Args); Phase = 11; }
        else if (Phase == 11) { Args->SetStringField(TEXT("Action"), TEXT("Snapshot")); Args->SetStringField(TEXT("Ref"), WindowRef); Args->SetNumberField(TEXT("MaxDepth"), 10); Pending = Call(TEXT("GetEditorSlate"), Args); Phase = 2; }
		else if (Phase == 2) { Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("Action"), TEXT("Type")); Args->SetStringField(TEXT("Text"), TEXT("中文")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 3; }
		else if (Phase == 3) { Test->TestTrue(TEXT("Chinese text delivered"), Input->GetText().ToString().Contains(TEXT("中文"))); Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("Action"), TEXT("Click")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 4; }
		else if (Phase == 4) { CommitsBeforeEnter = Commits.Get(); Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("Action"), TEXT("PressKey")); Args->SetStringField(TEXT("Key"), TEXT("Enter")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 5; }
		else if (Phase == 5) { Test->TestTrue(TEXT("Enter committed text"), Commits.Get() > CommitsBeforeEnter); Input->SetEnabled(false); Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("Action"), TEXT("Click")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 6; }
		else if (Phase == 6) { Input->SetEnabled(true); Window->HideWindow(); ReadyAt = FPlatformTime::Seconds() + 0.3; Phase = 7; return false; }
        else if (Phase == 7) { Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("Action"), TEXT("Click")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 8; }
        else if (Phase == 8) { Window->RequestDestroyWindow(); ReadyAt = FPlatformTime::Seconds() + 0.3; Phase = 9; return false; }
        else if (Phase == 9) { Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("Action"), TEXT("Type")); Args->SetStringField(TEXT("Text"), TEXT("stale")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 10; }
		else return true;
		if (!Pending.IsValid()) { Test->AddError(TEXT("Operation did not start; run GUI fixture with dangerous capabilities explicitly enabled")); return true; }
		return false;
	}
};

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusEditorSlateInputTest, "NexusLink.EditorOperations.SlateInput", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusEditorSlateInputTest::RunTest(const FString& Parameters)
{
	if (!FSlateApplication::IsInitialized() || !FApp::CanEverRender()) { AddInfo(TEXT("GUI-only probe; run with an editor viewport")); return true; }
	FAutomationTestFramework::Get().EnqueueLatentCommand(MakeShared<FNexusSlateInputProbe>(this));
	return true;
}
#endif
