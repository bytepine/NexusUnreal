// Copyright byteyang. All Rights Reserved.
#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#if WITH_EDITOR
#include "NexusCapabilityRegistry.h"
#include "NexusEditorOperation.h"
#include "Framework/Application/SlateApplication.h"
#include "Widgets/SWindow.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Input/SComboBox.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"
#include "Dom/JsonValue.h"
#include "Misc/App.h"
#include "Misc/Guid.h"

class FNexusSlateInputProbe final : public IAutomationLatentCommand
{
	FAutomationTestBase* Test;
	TSharedPtr<SWindow> Window;
	TSharedPtr<SEditableTextBox> Input;
	TSharedPtr<SCheckBox> Check;
	TSharedRef<TArray<TSharedPtr<FString>>> Choices = MakeShared<TArray<TSharedPtr<FString>>>();
	TSharedRef<FString> Choice = MakeShared<FString>();
	TSharedRef<int32> UnrelatedClicks = MakeShared<int32>(0);
	struct FDragState { bool bDown = false, bUp = false; int32 Moves = 0; };
	TSharedRef<FDragState> Drag = MakeShared<FDragState>();
	TSharedPtr<FNexusEditorOperation> Pending;
	FString Ref, WindowRef, Seed = FGuid::NewGuid().ToString(), Owner = FGuid::NewGuid().ToString();
	FString CheckRef, ComboRef, SourceRef, DestinationRef;
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
			Choices->Add(MakeShared<FString>(Seed + TEXT("-one"))); Choices->Add(MakeShared<FString>(Seed + TEXT("-two")));
			auto DragBox = [&](const FString& Label)
			{
				return SNew(SBorder).Padding(8)
					.OnMouseButtonDown_Lambda([State = Drag](const FGeometry&, const FPointerEvent&) { State->bDown = true; return FReply::Handled(); })
					.OnMouseMove_Lambda([State = Drag](const FGeometry&, const FPointerEvent& Event) { if (Event.IsMouseButtonDown(EKeys::LeftMouseButton)) ++State->Moves; return FReply::Handled(); })
					.OnMouseButtonUp_Lambda([State = Drag](const FGeometry&, const FPointerEvent&) { State->bUp = true; return FReply::Handled(); })
					[SNew(STextBlock).Text(FText::FromString(Label))];
			};
			Window = SNew(SWindow).Title(FText::FromString(TEXT("Nexus Slate Input Probe ") + Owner)).ClientSize(FVector2D(420, 260))
				[SNew(SVerticalBox)
				+ SVerticalBox::Slot().AutoHeight()[SAssignNew(Input, SEditableTextBox).Text(FText::FromString(Seed)).OnTextCommitted_Lambda([Counter = Commits](const FText&, ETextCommit::Type) { ++Counter.Get(); })]
				+ SVerticalBox::Slot().AutoHeight()[SAssignNew(Check, SCheckBox)[SNew(STextBlock).Text(FText::FromString(Seed + TEXT("-check")))]]
				+ SVerticalBox::Slot().AutoHeight()[SNew(SComboBox<TSharedPtr<FString>>).OptionsSource(&Choices.Get()).InitiallySelectedItem((*Choices)[0])
					.OnGenerateWidget_Lambda([](TSharedPtr<FString> Item) { return SNew(STextBlock).Text(FText::FromString(*Item)); })
					.OnSelectionChanged_Lambda([Selected = Choice, Keep = Choices](TSharedPtr<FString> Item, ESelectInfo::Type) { if (Item.IsValid() && Keep->Contains(Item)) Selected.Get() = *Item; })
					[SNew(STextBlock).Text(FText::FromString(Seed + TEXT("-combo")))]]
				+ SVerticalBox::Slot().AutoHeight()[DragBox(Seed + TEXT("-source"))]
				+ SVerticalBox::Slot().AutoHeight()[DragBox(Seed + TEXT("-destination"))]
				+ SVerticalBox::Slot().AutoHeight()[SNew(SButton).OnClicked_Lambda([Count = UnrelatedClicks]() { ++Count.Get(); return FReply::Handled(); })[SNew(STextBlock).Text(FText::FromString(Seed + TEXT("-not-option")))]]
				+ SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Visibility(EVisibility::Collapsed).Text(FText::FromString(Seed + TEXT("-hidden")))]];
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
					for (const auto& Node : *Nodes)
					{
						auto Object = Node->AsObject(); const FString Text = Object->GetStringField(TEXT("Text")), Type = Object->GetStringField(TEXT("Type"));
						if (Text == Seed) Object->TryGetStringField(TEXT("Ref"), Ref);
						if (Type == TEXT("SCheckBox")) Object->TryGetStringField(TEXT("Ref"), CheckRef);
						if (Type.StartsWith(TEXT("SComboBox"))) Object->TryGetStringField(TEXT("Ref"), ComboRef);
						if (Text == Seed + TEXT("-source")) Object->TryGetStringField(TEXT("Ref"), SourceRef);
						if (Text == Seed + TEXT("-destination")) Object->TryGetStringField(TEXT("Ref"), DestinationRef);
					}
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
				if (!Snapshot.IsEmpty())
				{
					auto FindRef = [&](const FString& Marker)
					{
						const int32 At = Snapshot.Find(Marker), Start = At == INDEX_NONE ? INDEX_NONE : Snapshot.Find(TEXT("[ref="), ESearchCase::CaseSensitive, ESearchDir::FromStart, At);
						const int32 End = Start == INDEX_NONE ? INDEX_NONE : Snapshot.Find(TEXT("]"), ESearchCase::CaseSensitive, ESearchDir::FromStart, Start);
						return End > Start && Start != INDEX_NONE ? Snapshot.Mid(Start + 5, End - Start - 5) : FString();
					};
					CheckRef = FindRef(TEXT("checkbox")); ComboRef = FindRef(TEXT("combobox")); SourceRef = FindRef(Seed + TEXT("-source")); DestinationRef = FindRef(Seed + TEXT("-destination"));
				}
				if (Ref.IsEmpty() || CheckRef.IsEmpty() || ComboRef.IsEmpty() || SourceRef.IsEmpty() || DestinationRef.IsEmpty()) { Test->AddError(TEXT("Probe controls were not discovered")); return true; }
			}
			else if ((Phase < 6 || (Phase >= 50 && Phase <= 54) || (Phase >= 57 && Phase <= 62)) && Pending->State != TEXT("Completed")) { Test->AddError(Pending->Message); return true; }
			else if (((Phase >= 6 && Phase < 50) || (Phase >= 55 && Phase <= 56) || Phase == 63) && Pending->State != TEXT("Failed")) { Test->AddError(TEXT("Invalid input unexpectedly accepted")); return true; }
			if (Phase == 53 && Pending->Result.IsValid()) Test->TestTrue(TEXT("WaitFor matched visible title"), Pending->Result->GetBoolField(TEXT("bConditionMet")));
			if (Phase == 54 && Pending->Result.IsValid()) Test->TestTrue(TEXT("WaitFor reports timeout without a fake match"), Pending->Result->GetBoolField(TEXT("bTimedOut")) && !Pending->Result->GetBoolField(TEXT("bConditionMet")));
			Pending.Reset();
		}
		auto Args = MakeShared<FJsonObject>();
		if (Phase == 1) { Args->SetStringField(TEXT("Action"), TEXT("Windows")); Pending = Call(TEXT("GetEditorSlate"), Args); Phase = 11; }
        else if (Phase == 11) { Args->SetStringField(TEXT("Action"), TEXT("Snapshot")); Args->SetStringField(TEXT("Ref"), WindowRef); Args->SetNumberField(TEXT("MaxDepth"), 10); Pending = Call(TEXT("GetEditorSlate"), Args); Phase = 2; }
		else if (Phase == 2) { Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("Action"), TEXT("Type")); Args->SetStringField(TEXT("Text"), TEXT("中文")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 3; }
		else if (Phase == 3) { Test->TestTrue(TEXT("Chinese text delivered"), Input->GetText().ToString().Contains(TEXT("中文"))); Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("Action"), TEXT("Click")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 4; }
		else if (Phase == 4) { CommitsBeforeEnter = Commits.Get(); Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("Action"), TEXT("PressKey")); Args->SetStringField(TEXT("Key"), TEXT("Enter")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 5; }
		else if (Phase == 5) { Test->TestTrue(TEXT("Enter committed text"), Commits.Get() > CommitsBeforeEnter); Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("Action"), TEXT("Hover")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 50; }
		else if (Phase == 50) { Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("Action"), TEXT("Type")); Args->SetStringField(TEXT("Text"), TEXT("replacement")); Args->SetBoolField(TEXT("bReplace"), true); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 51; }
		else if (Phase == 51) {
			Test->TestEqual(TEXT("Type replaces existing content"), Input->GetText().ToString(), FString(TEXT("replacement")));
			auto Field = MakeShared<FJsonObject>(); Field->SetStringField(TEXT("Ref"), Ref); Field->SetStringField(TEXT("Value"), TEXT("filled")); Field->SetStringField(TEXT("FieldType"), TEXT("textbox"));
			Args->SetStringField(TEXT("Action"), TEXT("FillForm")); Args->SetStringField(TEXT("Ref"), WindowRef); Args->SetArrayField(TEXT("Fields"), {MakeShared<FJsonValueObject>(Field)});
			Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 52;
		}
		else if (Phase == 52) { Test->TestEqual(TEXT("FillForm replaces textbox"), Input->GetText().ToString(), FString(TEXT("filled"))); Args->SetStringField(TEXT("Action"), TEXT("WaitFor")); Args->SetStringField(TEXT("Text"), TEXT("Nexus Slate Input Probe ") + Owner); Args->SetNumberField(TEXT("TimeoutSeconds"), 1); Pending = Call(TEXT("GetEditorSlate"), Args); Phase = 53; }
		else if (Phase == 53) { Args->SetStringField(TEXT("Action"), TEXT("WaitFor")); Args->SetStringField(TEXT("Text"), Seed + TEXT("-hidden")); Args->SetNumberField(TEXT("TimeoutSeconds"), 0); Pending = Call(TEXT("GetEditorSlate"), Args); Phase = 54; }
		else if (Phase == 54) {
			auto Good = MakeShared<FJsonObject>(); Good->SetStringField(TEXT("Ref"), Ref); Good->SetStringField(TEXT("Value"), TEXT("must-not-change")); Good->SetStringField(TEXT("FieldType"), TEXT("textbox"));
			auto Bad = MakeShared<FJsonObject>(); Bad->SetStringField(TEXT("Ref"), TEXT("foreign")); Bad->SetStringField(TEXT("Value"), TEXT("invalid")); Bad->SetStringField(TEXT("FieldType"), TEXT("textbox"));
			Args->SetStringField(TEXT("Action"), TEXT("FillForm")); Args->SetStringField(TEXT("Ref"), WindowRef); Args->SetArrayField(TEXT("Fields"), {MakeShared<FJsonValueObject>(Good), MakeShared<FJsonValueObject>(Bad)});
			Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 55;
		}
		else if (Phase == 55) { Test->TestEqual(TEXT("All form refs preflight before mutation"), Input->GetText().ToString(), FString(TEXT("filled"))); Args->SetStringField(TEXT("Action"), TEXT("Drag")); Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("EndRef"), TEXT("foreign")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 56; }
		else if (Phase == 56) { Args->SetStringField(TEXT("Ref"), CheckRef); Args->SetStringField(TEXT("Action"), TEXT("SetChecked")); Args->SetStringField(TEXT("Value"), TEXT("true")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 57; }
		else if (Phase == 57) { Test->TestTrue(TEXT("Checkbox checked"), Check->IsChecked()); Args->SetStringField(TEXT("Ref"), CheckRef); Args->SetStringField(TEXT("Action"), TEXT("SetChecked")); Args->SetStringField(TEXT("Value"), TEXT("false")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 58; }
		else if (Phase == 58) { Test->TestFalse(TEXT("Checkbox unchecked"), Check->IsChecked()); Args->SetStringField(TEXT("Ref"), ComboRef); Args->SetStringField(TEXT("Action"), TEXT("SelectOption")); Args->SetStringField(TEXT("Value"), Seed + TEXT("-not-option")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 63; }
		else if (Phase == 63) { Test->TestEqual(TEXT("Missing option never clicks an unrelated matching label"), UnrelatedClicks.Get(), 0); Args->SetStringField(TEXT("Ref"), ComboRef); Args->SetStringField(TEXT("Action"), TEXT("SelectOption")); Args->SetStringField(TEXT("Value"), *(*Choices)[1]); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 59; }
		else if (Phase == 59) {
			Test->TestEqual(TEXT("Combo selected exact option"), Choice.Get(), *(*Choices)[1]);
			TArray<TSharedPtr<FJsonValue>> Fields;
			auto Field = [&](const FString& Target, const FString& Value, const FString& Type) { auto Item = MakeShared<FJsonObject>(); Item->SetStringField(TEXT("Ref"), Target); Item->SetStringField(TEXT("Value"), Value); Item->SetStringField(TEXT("FieldType"), Type); Fields.Add(MakeShared<FJsonValueObject>(Item)); };
			Field(CheckRef, TEXT("true"), TEXT("checkbox")); Field(ComboRef, *(*Choices)[0], TEXT("combobox")); Field(Ref, TEXT("form-value"), TEXT("textbox"));
			Args->SetStringField(TEXT("Ref"), WindowRef); Args->SetStringField(TEXT("Action"), TEXT("FillForm")); Args->SetArrayField(TEXT("Fields"), Fields); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 60;
		}
		else if (Phase == 60) { Test->TestTrue(TEXT("Form checkbox applied"), Check->IsChecked()); Test->TestEqual(TEXT("Form combo applied"), Choice.Get(), *(*Choices)[0]); Test->TestEqual(TEXT("Form textbox applied"), Input->GetText().ToString(), FString(TEXT("form-value"))); Args->SetStringField(TEXT("Action"), TEXT("Drag")); Args->SetStringField(TEXT("Ref"), SourceRef); Args->SetStringField(TEXT("EndRef"), DestinationRef); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 61; }
		else if (Phase == 61) { Test->TestTrue(TEXT("Drag emitted down, held movement and target up"), Drag->bDown && Drag->Moves > 0 && Drag->bUp); Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("Action"), TEXT("Type")); Args->SetStringField(TEXT("Text"), TEXT("")); Args->SetBoolField(TEXT("bReplace"), true); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 62; }
		else if (Phase == 62) { Test->TestTrue(TEXT("Empty replacement clears textbox"), Input->GetText().IsEmpty()); Input->SetEnabled(false); Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("Action"), TEXT("Click")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 6; }
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
