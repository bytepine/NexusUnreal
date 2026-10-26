// Copyright byteyang. All Rights Reserved.
#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"

#if WITH_EDITOR
#include "NexusReliabilityTestTypes.h"
#include "NexusCapabilityRegistry.h"
#include "NexusEditorServices.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/DataTable.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "GameFramework/Actor.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Editor.h"
#include "Editor/TransBuffer.h"
#include "UObject/StrongObjectPtr.h"
#include "WidgetBlueprint.h"
#include "Blueprint/WidgetBlueprintGeneratedClass.h"
#include "Blueprint/WidgetTree.h"
#include "Blueprint/UserWidget.h"
#include "Components/TextBlock.h"

static FCapabilityResult AssetEditCall(const TCHAR* Capability, const TSharedPtr<FJsonObject>& Args)
{
	const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(Capability);
	return Record ? Record->Instance->Run(Args) : FCapabilityResult::MakeFatal(TEXT("Capability missing"));
}

static TSharedPtr<FJsonObject> AssetEditArgs(UObject* Asset, const TCHAR* Capability, const TCHAR* Action, const TCHAR* Field, const TCHAR* Value)
{
	TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("AssetPath"), Asset->GetPathName());
	Args->SetStringField(TEXT("Capability"), Capability);
	TSharedPtr<FJsonObject> Operation = MakeShared<FJsonObject>();
	Operation->SetStringField(TEXT("Action"), Action);
	Operation->SetStringField(Cast<UDataTable>(Asset) ? TEXT("FieldName") : TEXT("PropertyPath"), Field);
	Operation->SetStringField(TEXT("Value"), Value);
	if (Cast<UDataTable>(Asset)) Operation->SetStringField(TEXT("RowName"), TEXT("Row"));
	if (Cast<UWidgetBlueprint>(Asset)) Operation->SetStringField(TEXT("WidgetName"), TEXT("Label"));
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Operation)});
	return Args;
}

static UPackage* AssetEditPackage()
{
	return CreatePackage(*(TEXT("/Game/_NexusTest/Edit_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusAssetScalarPreviewTest, "NexusLink.AssetEdit.ScalarPreview",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusAssetScalarPreviewTest::RunTest(const FString& Parameters)
{
	UPackage* Package = AssetEditPackage();
	TStrongObjectPtr<UDataTable> Table(NewObject<UDataTable>(Package, TEXT("Table"), RF_Public | RF_Transactional));
	Table->RowStruct = FNexusReliabilityTestRow::StaticStruct();
	Table->AddRow(TEXT("Row"), FNexusReliabilityTestRow());
	Package->SetDirtyFlag(false);
	const int32 UndoCount = GEditor->Trans->GetQueueLength();
	const TCHAR* ValidSamples[][2] = {
		{TEXT("Count"), TEXT("00012")}, {TEXT("bEnabled"), TEXT("true")}, {TEXT("Weight"), TEXT("2.5")},
		{TEXT("Label"), TEXT("hello")}, {TEXT("Key"), TEXT("MyName")}, {TEXT("Text"), TEXT("hello")}, {TEXT("Choice"), TEXT("Second")}};
	for (const auto& Sample : ValidSamples)
	{
		TSharedPtr<FJsonObject> Args = AssetEditArgs(Table.Get(), TEXT("ManageAssetDataTable"), TEXT("Set"), Sample[0], Sample[1]);
		const FCapabilityResult Preview = AssetEditCall(TEXT("GetAssetEditPreview"), Args);
		TestFalse(Sample[0], Preview.HasErrors());
	}
	TestFalse(TEXT("Preview keeps package clean"), Package->IsDirty());
	TestEqual(TEXT("Preview never records Undo"), GEditor->Trans->GetQueueLength(), UndoCount);
	TestEqual(TEXT("Preview never modifies row"), Table->FindRow<FNexusReliabilityTestRow>(TEXT("Row"), TEXT("Test"))->Count, 7);
	const TCHAR* InvalidSamples[][2] = {
		{TEXT("Count"), TEXT("2147483648")}, {TEXT("Count"), TEXT("7oops")}, {TEXT("Weight"), TEXT("nan")},
		{TEXT("bEnabled"), TEXT("not-bool")}, {TEXT("Values"), TEXT("(1,2)")}};
	for (const auto& Sample : InvalidSamples)
	{
		TestTrue(TEXT("Invalid values/types rejected"), AssetEditCall(TEXT("GetAssetEditPreview"),
			AssetEditArgs(Table.Get(), TEXT("ManageAssetDataTable"), TEXT("Set"), Sample[0], Sample[1])).HasErrors());
	}
	TestFalse(TEXT("Rejected previews keep package clean"), Package->IsDirty());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusAssetExpectedValueTest, "NexusLink.AssetEdit.ExpectedValueAndPartialSuccess",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusAssetExpectedValueTest::RunTest(const FString& Parameters)
{
	UPackage* Package = AssetEditPackage();
	TStrongObjectPtr<UDataTable> Table(NewObject<UDataTable>(Package, TEXT("Table"), RF_Public | RF_Transactional));
	Table->RowStruct = FNexusReliabilityTestRow::StaticStruct(); Table->AddRow(TEXT("Row"), FNexusReliabilityTestRow());
	TSharedPtr<FJsonObject> Args = AssetEditArgs(Table.Get(), TEXT("ManageAssetDataTable"), TEXT("Set"), TEXT("Count"), TEXT("12"));
	Args->RemoveField(TEXT("Capability")); Args->SetBoolField(TEXT("bVerify"), true); Args->SetBoolField(TEXT("bSaveToDisk"), true);
	TSharedPtr<FJsonObject> Operation = Args->GetArrayField(TEXT("Operations"))[0]->AsObject();
	Operation->SetStringField(TEXT("ExpectedValue"), TEXT("8"));
	int32 SaveCount = 0;
	TGuardValue<decltype(FNexusEditorServices::ApplyManageFinalize)> Guard(FNexusEditorServices::ApplyManageFinalize,
		[&](const FString&, bool, bool bSave, TSharedPtr<FJsonObject>& Top) { if (bSave) ++SaveCount; });
	Package->SetDirtyFlag(false);
	TestTrue(TEXT("Stale expected value rejected"), AssetEditCall(TEXT("ManageAssetDataTable"), Args).HasErrors());
	TestFalse(TEXT("Stale value does not dirty"), Package->IsDirty());
	Operation->SetStringField(TEXT("ExpectedValue"), TEXT("7"));
	FCapabilityResult Changed = AssetEditCall(TEXT("ManageAssetDataTable"), Args);
	if (!TestFalse(TEXT("Verified write succeeds"), Changed.HasErrors())) return false;
	TestTrue(TEXT("Readback verified"), Changed.Entries[0]->AsObject()->GetBoolField(TEXT("bVerified")));
	TestEqual(TEXT("Successful verification permits save"), SaveCount, 1);
	TestEqual(TEXT("New value"), Table->FindRow<FNexusReliabilityTestRow>(TEXT("Row"), TEXT("Test"))->Count, 12);
	// 单调用部分成功保留前项，但 bVerify 的任意失败阻止自动保存。
	Operation->SetStringField(TEXT("ExpectedValue"), TEXT("12")); Operation->SetStringField(TEXT("Value"), TEXT("13"));
	TSharedPtr<FJsonObject> Invalid = MakeShared<FJsonObject>(*Operation);
	Invalid->RemoveField(TEXT("ExpectedValue")); Invalid->SetStringField(TEXT("Value"), TEXT("invalid"));
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Operation), MakeShared<FJsonValueObject>(Invalid)});
	TestTrue(TEXT("Partial failure reported"), AssetEditCall(TEXT("ManageAssetDataTable"), Args).HasErrors());
	TestEqual(TEXT("Successful first operation retained"), Table->FindRow<FNexusReliabilityTestRow>(TEXT("Row"), TEXT("Test"))->Count, 13);
	TestEqual(TEXT("Partial verification failure never saves"), SaveCount, 1);
	Package->SetDirtyFlag(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusAssetBlueprintVerificationTest, "NexusLink.AssetEdit.BlueprintVerification",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusAssetBlueprintVerificationTest::RunTest(const FString& Parameters)
{
	UPackage* Package = AssetEditPackage();
	TStrongObjectPtr<UBlueprint> Blueprint(FKismetEditorUtilities::CreateBlueprint(AActor::StaticClass(), Package,
		TEXT("Blueprint"), BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass()));
	TSharedPtr<FJsonObject> Args = AssetEditArgs(Blueprint.Get(), TEXT("ManageAssetBlueprint"), TEXT("SetDefaults"), TEXT("bCanBeDamaged"), TEXT("false"));
	Package->SetDirtyFlag(false);
	const int32 UndoCount = GEditor->Trans->GetQueueLength();
	TestFalse(TEXT("Blueprint preview"), AssetEditCall(TEXT("GetAssetEditPreview"), Args).HasErrors());
	TestFalse(TEXT("Blueprint preview keeps clean"), Package->IsDirty());
	TestEqual(TEXT("Blueprint preview preserves Undo"), GEditor->Trans->GetQueueLength(), UndoCount);
	Args->RemoveField(TEXT("Capability")); Args->SetBoolField(TEXT("bVerify"), true); Args->SetBoolField(TEXT("bSaveToDisk"), true);
	int32 SaveCount = 0;
	TGuardValue<decltype(FNexusEditorServices::ApplyManageFinalize)> Guard(FNexusEditorServices::ApplyManageFinalize,
		[&](const FString&, bool, bool bSave, TSharedPtr<FJsonObject>&) { if (bSave) ++SaveCount; });
	TestFalse(TEXT("Compile and reread succeeds"), AssetEditCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestEqual(TEXT("Successful BP save"), SaveCount, 1);
	FDelegateHandle ReadbackHook = GEditor->OnBlueprintCompiled().AddLambda([&]()
		{ Cast<AActor>(Blueprint->GeneratedClass->GetDefaultObject())->SetCanBeDamaged(true); });
	TestTrue(TEXT("Readback mismatch fails"), AssetEditCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	GEditor->OnBlueprintCompiled().Remove(ReadbackHook);
	TestEqual(TEXT("Mismatch never saves"), SaveCount, 1);
	FDelegateHandle CompileHook = GEditor->OnBlueprintCompiled().AddLambda([&]() { Blueprint->Status = BS_Error; });
	TestTrue(TEXT("Compiler failure reported"), AssetEditCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	GEditor->OnBlueprintCompiled().Remove(CompileHook);
	TestEqual(TEXT("Compiler failure never saves"), SaveCount, 1);
	Package->SetDirtyFlag(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusAssetWidgetVerificationTest, "NexusLink.AssetEdit.WidgetVerification",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusAssetWidgetVerificationTest::RunTest(const FString& Parameters)
{
	UPackage* Package = AssetEditPackage();
	TStrongObjectPtr<UWidgetBlueprint> Blueprint(Cast<UWidgetBlueprint>(FKismetEditorUtilities::CreateBlueprint(UUserWidget::StaticClass(), Package,
		TEXT("Widget"), BPTYPE_Normal, UWidgetBlueprint::StaticClass(), UWidgetBlueprintGeneratedClass::StaticClass())));
	UTextBlock* Widget = Blueprint->WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Label"));
	Blueprint->WidgetTree->RootWidget = Widget;
	FKismetEditorUtilities::CompileBlueprint(Blueprint.Get());
	TSharedPtr<FJsonObject> Args = AssetEditArgs(Blueprint.Get(), TEXT("ManageAssetUserWidget"), TEXT("SetProperty"), TEXT("RenderOpacity"), TEXT("0.5"));
	Package->SetDirtyFlag(false);
	const int32 UndoCount = GEditor->Trans->GetQueueLength();
	TestFalse(TEXT("Widget preview"), AssetEditCall(TEXT("GetAssetEditPreview"), Args).HasErrors());
	TestFalse(TEXT("Widget preview keeps clean"), Package->IsDirty());
	TestEqual(TEXT("Widget preview preserves Undo"), GEditor->Trans->GetQueueLength(), UndoCount);
	TestEqual(TEXT("Widget preview preserves value"), Widget->GetRenderOpacity(), 1.f);
	Args->RemoveField(TEXT("Capability")); Args->SetBoolField(TEXT("bVerify"), true);
	TestFalse(TEXT("Widget compile/readback"), AssetEditCall(TEXT("ManageAssetUserWidget"), Args).HasErrors());
	TestEqual(TEXT("Widget value changed"), Widget->GetRenderOpacity(), .5f);
	GEditor->UndoTransaction();
	TestEqual(TEXT("Widget Undo restores previous value"), Widget->GetRenderOpacity(), 1.f);
	Package->SetDirtyFlag(false);
	return true;
}
#endif
