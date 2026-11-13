// Copyright byteyang. All Rights Reserved.
#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#if WITH_EDITOR
#include "NexusCapabilityRegistry.h"
#include "NexusEditorOperation.h"
#include "Framework/Application/SlateApplication.h"
#include "Widgets/SWindow.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SSearchBox.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Input/SComboBox.h"
#include "SSearchableComboBox.h"
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
	bool bSearchable;
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
	explicit FNexusSlateInputProbe(FAutomationTestBase* InTest, bool bInSearchable = false) : Test(InTest), bSearchable(bInSearchable) {}
	~FNexusSlateInputProbe() { if (Window.IsValid() && FSlateApplication::IsInitialized()) Window->RequestDestroyWindow(); }
	bool Update() override
	{
		TGuardValue<FString> Scope(FNexusEditorOperations::RequestOwner(), Owner);
		if (FPlatformTime::Seconds() > Deadline) { Test->AddError(TEXT("Slate input probe timed out")); return true; }
		if (Phase == 0)
		{
			Choices->Add(MakeShared<FString>(Seed + TEXT("-one"))); Choices->Add(MakeShared<FString>(Seed + TEXT("-two")));
			auto Generate=[](TSharedPtr<FString> Item) { return SNew(STextBlock).Text(FText::FromString(*Item)); };
			auto Select=[Selected=Choice,Keep=Choices](TSharedPtr<FString> Item,ESelectInfo::Type) { if (Item.IsValid() && Keep->Contains(Item)) Selected.Get()=*Item; };
			TSharedRef<SWidget> Combo=bSearchable
				? StaticCastSharedRef<SWidget>(SNew(SSearchableComboBox).OptionsSource(&Choices.Get()).InitiallySelectedItem((*Choices)[0]).OnGenerateWidget_Lambda(Generate).OnSelectionChanged_Lambda(Select)[SNew(STextBlock).Text(FText::FromString(Seed+TEXT("-combo")))])
				: StaticCastSharedRef<SWidget>(SNew(SComboBox<TSharedPtr<FString>>).OptionsSource(&Choices.Get()).InitiallySelectedItem((*Choices)[0]).OnGenerateWidget_Lambda(Generate).OnSelectionChanged_Lambda(Select)[SNew(STextBlock).Text(FText::FromString(Seed+TEXT("-combo")))]);
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
				+ SVerticalBox::Slot().AutoHeight()[SAssignNew(Input, SSearchBox).InitialText(FText::FromString(Seed)).OnTextCommitted_Lambda([Counter = Commits](const FText&, ETextCommit::Type) { ++Counter.Get(); })]
				+ SVerticalBox::Slot().AutoHeight()[SAssignNew(Check, SCheckBox)[SNew(STextBlock).Text(FText::FromString(Seed + TEXT("-check")))]]
				+ SVerticalBox::Slot().AutoHeight()[Combo]
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
						if (Text == Seed && Type == TEXT("SSearchBox")) Object->TryGetStringField(TEXT("Ref"), Ref);
						if (Type == TEXT("SCheckBox")) Object->TryGetStringField(TEXT("Ref"), CheckRef);
						if (Type.StartsWith(TEXT("SComboBox")) || Type==TEXT("SSearchableComboBox")) Object->TryGetStringField(TEXT("Ref"), ComboRef);
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
		else if (Phase == 2) {
			auto Filter = MakeShared<FJsonObject>(); Filter->SetStringField(TEXT("Action"), TEXT("Snapshot")); Filter->SetStringField(TEXT("Ref"), WindowRef);
			Filter->SetStringField(TEXT("TextFilter"), Seed); Filter->SetStringField(TEXT("TypeFilter"), TEXT("SSearchBox"));
			auto Filtered = Call(TEXT("GetEditorSlate"), Filter);
			if (!Filtered.IsValid() || !Filtered->Result.IsValid()) { Test->AddError(TEXT("Filtered search-box snapshot unavailable")); return true; }
			const auto& Nodes = Filtered->Result->GetArrayField(TEXT("Nodes"));
			if (!Test->TestEqual(TEXT("Filtered snapshot finds the search box"), Nodes.Num(), 1)) return true;
			Test->TestEqual(TEXT("Search box is the discovered input target"), Nodes[0]->AsObject()->GetStringField(TEXT("Ref")), Ref);
			Test->TestEqual(TEXT("Search box role is editable"), Nodes[0]->AsObject()->GetStringField(TEXT("Role")), FString(TEXT("TextBox")));
			Args->SetStringField(TEXT("Ref"), Ref); Args->SetStringField(TEXT("Action"), TEXT("Type")); Args->SetStringField(TEXT("Text"), TEXT("中文")); Pending = Call(TEXT("InteractEditorSlate"), Args); Phase = 3;
		}
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
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusEditorSearchableComboTest, "NexusLink.EditorOperations.SearchableCombo", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusEditorSearchableComboTest::RunTest(const FString& Parameters)
{
	if (!FSlateApplication::IsInitialized() || !FApp::CanEverRender()) { AddInfo(TEXT("GUI-only probe")); return true; }
	FAutomationTestFramework::Get().EnqueueLatentCommand(MakeShared<FNexusSlateInputProbe>(this,true)); return true;
}

struct FNexusSlatePointerState final
{
	int32 DownCount = 0, UpCount = 0, DoubleClickCount = 0, WheelCount = 0, HeldMoveCount = 0, CapturedMoveCount = 0, DragDetectedCount = 0;
	FKey LastButton;
	FVector2D DownPosition, UpPosition, DoubleClickPosition, WheelPosition;
	float WheelDelta = 0;
	bool bCtrl = false, bShift = false, bAlt = false, bCmd = false;
	bool bHideOnMove = false;
	bool bCaptureOnDown = false, bDetectDrag = false;
	void ReadModifiers(const FPointerEvent& Event)
	{
		bCtrl = Event.IsControlDown(); bShift = Event.IsShiftDown(); bAlt = Event.IsAltDown(); bCmd = Event.IsCommandDown();
	}
	int32 DispatchCount() const { return DownCount + UpCount + DoubleClickCount + WheelCount; }
};

class SNexusSlatePointerTarget final : public SBorder
{
	TSharedPtr<FNexusSlatePointerState> State;
	static FVector2D RelativePosition(const FGeometry& Geometry, const FPointerEvent& Event)
	{
		const FVector2D Local = Geometry.AbsoluteToLocal(Event.GetScreenSpacePosition()), Size = Geometry.GetLocalSize();
		return FVector2D(Local.X / Size.X, Local.Y / Size.Y);
	}
public:
	void Construct(const SBorder::FArguments& Arguments, TSharedRef<FNexusSlatePointerState> InState)
	{
		State = InState; SBorder::Construct(Arguments);
	}
	FReply OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event) override
	{
		++State->DownCount; State->LastButton = Event.GetEffectingButton(); State->DownPosition = RelativePosition(Geometry, Event); State->ReadModifiers(Event);
		if (State->bDetectDrag) return FReply::Handled().DetectDrag(SharedThis(this), Event.GetEffectingButton());
		if (State->bCaptureOnDown) return FReply::Handled().CaptureMouse(SharedThis(this));
		return FReply::Handled();
	}
	FReply OnMouseButtonUp(const FGeometry& Geometry, const FPointerEvent& Event) override
	{
		++State->UpCount; State->LastButton = Event.GetEffectingButton(); State->UpPosition = RelativePosition(Geometry, Event); State->ReadModifiers(Event);
		if (State->bCaptureOnDown) return FReply::Handled().ReleaseMouseCapture();
		return FReply::Handled();
	}
	FReply OnMouseButtonDoubleClick(const FGeometry& Geometry, const FPointerEvent& Event) override
	{
		++State->DoubleClickCount; State->LastButton = Event.GetEffectingButton(); State->DoubleClickPosition = RelativePosition(Geometry, Event); State->ReadModifiers(Event);
		return FReply::Handled();
	}
	FReply OnMouseMove(const FGeometry&, const FPointerEvent& Event) override
	{
		if (Event.IsMouseButtonDown(EKeys::LeftMouseButton) || Event.IsMouseButtonDown(EKeys::RightMouseButton) || Event.IsMouseButtonDown(EKeys::MiddleMouseButton))
		{
			++State->HeldMoveCount;
			if (HasMouseCapture()) ++State->CapturedMoveCount;
			State->ReadModifiers(Event);
		}
		if (State->bHideOnMove) SetVisibility(EVisibility::Collapsed);
		return FReply::Handled();
	}
	FReply OnDragDetected(const FGeometry&, const FPointerEvent& Event) override
	{
		++State->DragDetectedCount; State->ReadModifiers(Event);
		return FReply::Handled();
	}
	FReply OnMouseWheel(const FGeometry& Geometry, const FPointerEvent& Event) override
	{
		++State->WheelCount; State->WheelDelta = Event.GetWheelDelta(); State->WheelPosition = RelativePosition(Geometry, Event); State->ReadModifiers(Event);
		return FReply::Handled();
	}
};

class FNexusSlatePointerProbe final : public IAutomationLatentCommand
{
	FAutomationTestBase* Test;
	TSharedPtr<SWindow> Window;
	TSharedPtr<SNexusSlatePointerTarget> PointerTarget;
	TSharedRef<FNexusSlatePointerState> Pointer = MakeShared<FNexusSlatePointerState>();
	FString Owner = FGuid::NewGuid().ToString(), Ref, WindowRef;
	int32 Phase = 0;
	double ReadyAt = 0;
	TSharedPtr<FNexusEditorOperation> Call(const TCHAR* Name, const TSharedPtr<FJsonObject>& Arguments)
	{
		const auto* Record = FNexusCapabilityRegistry::Get().FindRecordByName(Name);
		if (!Record) { Test->AddError(FString::Printf(TEXT("Missing capability %s"), Name)); return nullptr; }
		const auto Result = Record->Instance->Run(Arguments);
		if (Result.Entries.Num() != 1 || Result.Entries[0]->Type != EJson::Object) { Test->AddError(Result.FatalError); return nullptr; }
		FString OperationId; Result.Entries[0]->AsObject()->TryGetStringField(TEXT("OperationId"), OperationId);
		const auto Operation = FNexusEditorOperations::Find(OperationId);
		if (!Operation.IsValid() || Operation->State != TEXT("Completed"))
		{
			Test->AddError(Operation.IsValid() ? Operation->Message : TEXT("Pointer operation did not complete synchronously")); return nullptr;
		}
		return Operation;
	}
	static TSharedRef<FJsonObject> Position(double X, double Y)
	{
		auto Value = MakeShared<FJsonObject>(); Value->SetNumberField(TEXT("X"), X); Value->SetNumberField(TEXT("Y"), Y); return Value;
	}
	TSharedRef<FJsonObject> Input(const TCHAR* Action)
	{
		auto Arguments = MakeShared<FJsonObject>(); Arguments->SetStringField(TEXT("Action"), Action); Arguments->SetStringField(TEXT("Ref"), Ref); return Arguments;
	}
	void CheckPosition(const TCHAR* Label, const FVector2D& Actual, double X, double Y)
	{
		Test->TestTrue(Label, Actual.Equals(FVector2D(X, Y), 0.01));
	}
	void Reject(const TSharedPtr<FJsonObject>& Arguments)
	{
		const auto* Record = FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("InteractEditorSlate"));
		if (!Record) { Test->AddError(TEXT("Missing InteractEditorSlate")); return; }
		const int32 Before = Pointer->DispatchCount();
		const auto Result = Record->Instance->Run(Arguments);
		Test->TestTrue(TEXT("Invalid pointer arguments are rejected"), Result.HasErrors());
		Test->TestEqual(TEXT("Invalid input dispatches no pointer events"), Pointer->DispatchCount(), Before);
	}
public:
	explicit FNexusSlatePointerProbe(FAutomationTestBase* InTest) : Test(InTest) {}
	~FNexusSlatePointerProbe() { if (Window.IsValid() && FSlateApplication::IsInitialized()) Window->RequestDestroyWindow(); }
	bool Update() override
	{
		TGuardValue<FString> Scope(FNexusEditorOperations::RequestOwner(), Owner);
		if (Phase == 0)
		{
			Window = SNew(SWindow).Title(FText::FromString(TEXT("Nexus Pointer Probe ") + Owner)).ClientSize(FVector2D(420, 280))
				[SAssignNew(PointerTarget, SNexusSlatePointerTarget, Pointer).Padding(0)[SNew(STextBlock).Text(FText::FromString(Owner))]];
			FSlateApplication::Get().AddWindow(Window.ToSharedRef()); ReadyAt = FPlatformTime::Seconds() + 0.5; ++Phase; return false;
		}
		if (FPlatformTime::Seconds() < ReadyAt) return false;
		if (Phase == 1)
		{
			auto Arguments = MakeShared<FJsonObject>(); Arguments->SetStringField(TEXT("Action"), TEXT("Windows"));
			const auto Windows = Call(TEXT("GetEditorSlate"), Arguments); if (!Windows.IsValid()) return true;
			for (const auto& Value : Windows->Result->GetArrayField(TEXT("Windows")))
				if (Value->AsObject()->GetStringField(TEXT("Title")) == TEXT("Nexus Pointer Probe ") + Owner) WindowRef = Value->AsObject()->GetStringField(TEXT("Ref"));
			if (!Test->TestFalse(TEXT("Pointer window is discoverable"), WindowRef.IsEmpty())) return true;
			Arguments->SetStringField(TEXT("Action"), TEXT("Snapshot")); Arguments->SetStringField(TEXT("Ref"), WindowRef);
			const auto Snapshot = Call(TEXT("GetEditorSlate"), Arguments); if (!Snapshot.IsValid()) return true;
			FString ParentRef;
			for (const auto& Value : Snapshot->Result->GetArrayField(TEXT("Nodes")))
			{
				const auto Node = Value->AsObject();
				if (Node->GetStringField(TEXT("Type")) != TEXT("SNexusSlatePointerTarget")) continue;
				Ref = Node->GetStringField(TEXT("Ref")); Node->TryGetStringField(TEXT("ParentRef"), ParentRef);
				const TSharedPtr<FJsonObject>* Size = nullptr;
				Test->TestTrue(TEXT("Snapshot reports laid-out local size"), Node->TryGetObjectField(TEXT("LocalSize"), Size) && (*Size)->GetNumberField(TEXT("X")) > 0 && (*Size)->GetNumberField(TEXT("Y")) > 0);
				for (const TCHAR* Action : {TEXT("DoubleClick"), TEXT("Scroll"), TEXT("Drag"), TEXT("PressKey")})
				{
					bool bFound = false; for (const auto& Candidate : Node->GetArrayField(TEXT("Actions"))) bFound |= Candidate->AsString() == Action;
					Test->TestTrue(FString::Printf(TEXT("Snapshot advertises %s"), Action), bFound);
				}
			}
			if (!Test->TestFalse(TEXT("Pointer target is discoverable"), Ref.IsEmpty())) return true;
			Test->TestFalse(TEXT("Snapshot reports the actual parent"), ParentRef.IsEmpty());
			Arguments->SetStringField(TEXT("TypeFilter"), TEXT("SNexusSlatePointerTarget"));
			const auto Filtered = Call(TEXT("GetEditorSlate"), Arguments); if (!Filtered.IsValid()) return true;
			const auto& Nodes = Filtered->Result->GetArrayField(TEXT("Nodes"));
			if (Test->TestEqual(TEXT("Filtered snapshot isolates the target"), Nodes.Num(), 1))
				Test->TestEqual(TEXT("Filtering preserves the actual parent reference"), Nodes[0]->AsObject()->GetStringField(TEXT("ParentRef")), ParentRef);
			if (!Call(TEXT("InteractEditorSlate"), Input(TEXT("Click"))).IsValid()) return true;
			Test->TestTrue(TEXT("Legacy click uses the left button"), Pointer->LastButton == EKeys::LeftMouseButton);
			CheckPosition(TEXT("Legacy click uses the target center"), Pointer->DownPosition, .5, .5);
		}
		else if (Phase == 2)
		{
			auto Arguments = Input(TEXT("Click")); Arguments->SetStringField(TEXT("Button"), TEXT("Right")); Arguments->SetObjectField(TEXT("Position"), Position(.2, .3));
			Arguments->SetArrayField(TEXT("Modifiers"), {MakeShared<FJsonValueString>(TEXT("Ctrl")), MakeShared<FJsonValueString>(TEXT("Shift"))});
			if (!Call(TEXT("InteractEditorSlate"), Arguments).IsValid()) return true;
			Test->TestTrue(TEXT("Right click carries Ctrl and Shift"), Pointer->LastButton == EKeys::RightMouseButton && Pointer->bCtrl && Pointer->bShift && !Pointer->bAlt && !Pointer->bCmd);
			CheckPosition(TEXT("Right click uses normalized local position"), Pointer->DownPosition, .2, .3);
		}
		else if (Phase == 3)
		{
			auto Arguments = Input(TEXT("DoubleClick")); Arguments->SetObjectField(TEXT("Position"), Position(.6, .65));
			Arguments->SetArrayField(TEXT("Modifiers"), {MakeShared<FJsonValueString>(TEXT("Alt")), MakeShared<FJsonValueString>(TEXT("Cmd"))});
			if (!Call(TEXT("InteractEditorSlate"), Arguments).IsValid()) return true;
			Test->TestEqual(TEXT("Double click delivers a double-click event"), Pointer->DoubleClickCount, 1);
			Test->TestTrue(TEXT("Double click defaults to left and preserves modifiers"), Pointer->LastButton == EKeys::LeftMouseButton && Pointer->bAlt && Pointer->bCmd && !Pointer->bCtrl && !Pointer->bShift);
			CheckPosition(TEXT("Double click uses local position"), Pointer->DoubleClickPosition, .6, .65);
		}
		else if (Phase == 4)
		{
			auto Arguments = Input(TEXT("Scroll")); Arguments->SetNumberField(TEXT("WheelDelta"), -2); Arguments->SetObjectField(TEXT("Position"), Position(.7, .4));
			Arguments->SetArrayField(TEXT("Modifiers"), {MakeShared<FJsonValueString>(TEXT("Shift"))});
			if (!Call(TEXT("InteractEditorSlate"), Arguments).IsValid()) return true;
			Test->TestEqual(TEXT("Scroll delivers one wheel event"), Pointer->WheelCount, 1);
			Test->TestEqual(TEXT("Scroll preserves signed wheel delta"), Pointer->WheelDelta, -2.f);
			Test->TestTrue(TEXT("Scroll preserves Shift"), Pointer->bShift && !Pointer->bCtrl && !Pointer->bAlt && !Pointer->bCmd);
			CheckPosition(TEXT("Scroll uses local position"), Pointer->WheelPosition, .7, .4);
		}
		else if (Phase == 5)
		{
			// 捕获鼠标的控件和引擎拖动检测都必须收到持键移动，不能只测普通冒泡事件。
			Pointer->bCaptureOnDown = true;
			for (const TCHAR* ButtonName : {TEXT("Left"), TEXT("Right"), TEXT("Middle")})
			{
				const int32 CapturedMovesBefore = Pointer->CapturedMoveCount, ReleasesBefore = Pointer->UpCount;
				const FKey ButtonKey = FString(ButtonName) == TEXT("Left") ? EKeys::LeftMouseButton : FString(ButtonName) == TEXT("Right") ? EKeys::RightMouseButton : EKeys::MiddleMouseButton;
				auto Arguments = Input(TEXT("Drag")); Arguments->SetStringField(TEXT("EndRef"), Ref); Arguments->SetStringField(TEXT("Button"), ButtonName);
				Arguments->SetObjectField(TEXT("Position"), Position(.15, .25)); Arguments->SetObjectField(TEXT("EndPosition"), Position(.85, .75));
				Arguments->SetArrayField(TEXT("Modifiers"), {MakeShared<FJsonValueString>(TEXT("Ctrl"))});
				if (!Call(TEXT("InteractEditorSlate"), Arguments).IsValid()) return true;
				Test->TestTrue(FString::Printf(TEXT("%s drag delivers held moves after mouse capture"), ButtonName), Pointer->CapturedMoveCount > CapturedMovesBefore);
				Test->TestTrue(TEXT("Captured drag preserves button and modifiers"), Pointer->LastButton == ButtonKey && Pointer->bCtrl && !Pointer->bShift && !Pointer->bAlt && !Pointer->bCmd);
				CheckPosition(TEXT("Captured drag starts at requested position"), Pointer->DownPosition, .15, .25);
				CheckPosition(TEXT("Captured drag ends at requested position"), Pointer->UpPosition, .85, .75);
				Test->TestEqual(TEXT("Captured drag emits mouse up"), Pointer->UpCount, ReleasesBefore + 1);
				Test->TestFalse(TEXT("Drag releases mouse capture"), PointerTarget->HasMouseCapture());
			}
			Pointer->bCaptureOnDown = false; Pointer->bDetectDrag = true;
			auto Arguments = Input(TEXT("Drag")); Arguments->SetStringField(TEXT("EndRef"), Ref);
			Arguments->SetObjectField(TEXT("Position"), Position(.15, .25)); Arguments->SetObjectField(TEXT("EndPosition"), Position(.85, .75));
			if (!Call(TEXT("InteractEditorSlate"), Arguments).IsValid()) return true;
			Test->TestEqual(TEXT("Drag triggers the engine drag detector"), Pointer->DragDetectedCount, 1);
			Test->TestFalse(TEXT("Detected drag leaves no mouse capture"), PointerTarget->HasMouseCapture());
			Pointer->bDetectDrag = false;
		}
		else
		{
			// 所有无效参数都必须在派发鼠标事件前失败。
			for (double X : {-.1, 1.1}) { auto Arguments = Input(TEXT("Click")); Arguments->SetObjectField(TEXT("Position"), Position(X, .5)); Reject(Arguments); }
			auto Arguments = Input(TEXT("Click")); auto MissingY = MakeShared<FJsonObject>(); MissingY->SetNumberField(TEXT("X"), .5); Arguments->SetObjectField(TEXT("Position"), MissingY); Reject(Arguments);
			Arguments = Input(TEXT("Drag")); Arguments->SetStringField(TEXT("EndRef"), Ref); Arguments->SetObjectField(TEXT("EndPosition"), Position(.5, 1.1)); Reject(Arguments);
			Reject(Input(TEXT("Scroll")));
			for (double Delta : {0., -21., 21.}) { Arguments = Input(TEXT("Scroll")); Arguments->SetNumberField(TEXT("WheelDelta"), Delta); Reject(Arguments); }
			Arguments = Input(TEXT("Click")); Arguments->SetStringField(TEXT("Button"), TEXT("Other")); Reject(Arguments);
			Arguments = Input(TEXT("Click")); Arguments->SetArrayField(TEXT("Modifiers"), {MakeShared<FJsonValueString>(TEXT("Meta"))}); Reject(Arguments);
			Arguments = Input(TEXT("Click")); Arguments->SetStringField(TEXT("Ref"), TEXT("foreign")); Reject(Arguments);
			// 初始悬停会同步改变控件树，不能继续向原坐标派发点击。
			const auto* Record = FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("InteractEditorSlate"));
			if (!Record) { Test->AddError(TEXT("Missing InteractEditorSlate")); return true; }
			const int32 DownBeforeHide = Pointer->DownCount;
			Pointer->bHideOnMove = true;
			const auto HiddenClick = Record->Instance->Run(Input(TEXT("Click")));
			if (Test->TestEqual(TEXT("Hidden-during-hover click returns an operation"), HiddenClick.Entries.Num(), 1))
				Test->TestEqual(TEXT("Hidden-during-hover click fails"), HiddenClick.Entries[0]->AsObject()->GetStringField(TEXT("State")), FString(TEXT("Failed")));
			Test->TestEqual(TEXT("Hidden-during-hover target receives no mouse down"), Pointer->DownCount, DownBeforeHide);
			return true;
		}
		++Phase; return false;
	}
};

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusEditorSlatePointerTest, "NexusLink.EditorOperations.SlatePointer", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusEditorSlatePointerTest::RunTest(const FString& Parameters)
{
	if (!FSlateApplication::IsInitialized() || !FApp::CanEverRender()) { AddInfo(TEXT("GUI-only pointer probe")); return true; }
	FAutomationTestFramework::Get().EnqueueLatentCommand(MakeShared<FNexusSlatePointerProbe>(this)); return true;
}
#endif
