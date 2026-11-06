// Copyright byteyang. All Rights Reserved.
#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"

#if WITH_EDITOR
#include "NexusReliabilityTestTypes.h"
#include "NexusCapabilityRegistry.h"
#include "NexusEditorServices.h"
#include "Utils/NexusVersionCompat.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/DataTable.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"
#include "Components/SkeletalMeshComponent.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Editor.h"
#include "Editor/TransBuffer.h"
#include "UObject/StrongObjectPtr.h"
#include "WidgetBlueprint.h"
#include "Blueprint/WidgetBlueprintGeneratedClass.h"
#include "Blueprint/WidgetTree.h"
#include "Blueprint/UserWidget.h"
#include "Components/TextBlock.h"
#include "Components/CanvasPanel.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_VariableGet.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "GraphEditAction.h"
#include "Misc/ScopeExit.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"

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
		{TEXT("Count"), TEXT("0")}, {TEXT("bEnabled"), TEXT("false")}, {TEXT("Weight"), TEXT("0")},
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
	const auto OriginalFinalize = FNexusEditorServices::ApplyManageFinalize;
	TGuardValue<decltype(FNexusEditorServices::ApplyManageFinalize)> Guard(FNexusEditorServices::ApplyManageFinalize,
		[&](const FString& Path, bool bCompile, bool bSave, TSharedPtr<FJsonObject>& Top)
		{ if (bCompile) OriginalFinalize(Path, true, false, Top); if (bSave) ++SaveCount; });
	int32 CompileCount = 0;
	FDelegateHandle CountHook = GEditor->OnBlueprintCompiled().AddLambda([&]() { ++CompileCount; });
	ON_SCOPE_EXIT { GEditor->OnBlueprintCompiled().Remove(CountHook); };
	TestFalse(TEXT("Memory verification without compile succeeds"), AssetEditCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestEqual(TEXT("bVerify respects default bCompile=false"), CompileCount, 0);
	TestEqual(TEXT("Successful BP save"), SaveCount, 1);
	Args->SetBoolField(TEXT("bCompile"), true);
	Args->SetBoolField(TEXT("bSaveToDisk"), false);
	const auto First = Args->GetArrayField(TEXT("Operations"))[0]->AsObject();
	TSharedPtr<FJsonObject> Second = MakeShared<FJsonObject>(*First);
	Second->SetStringField(TEXT("Value"), TEXT("true"));
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(First), MakeShared<FJsonValueObject>(Second)});
	TestFalse(TEXT("Two writes compile once"), AssetEditCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestEqual(TEXT("Exactly one requested compile"), CompileCount, 1);
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(First)});
	Args->SetBoolField(TEXT("bSaveToDisk"), true);
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusAssetOwnedComponentPreviewTest, "NexusLink.AssetEdit.OwnedComponentPreview",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusAssetOwnedComponentPreviewTest::RunTest(const FString& Parameters)
{
	UPackage* Package = AssetEditPackage();
	TStrongObjectPtr<UBlueprint> Blueprint(FKismetEditorUtilities::CreateBlueprint(ACharacter::StaticClass(), Package,
		TEXT("Character"), BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass()));
	ACharacter* Defaults = Cast<ACharacter>(Blueprint->GeneratedClass->GetDefaultObject());
	const FVector Before = Defaults->GetMesh()->GetRelativeLocation();
	TSharedPtr<FJsonObject> Args = AssetEditArgs(Blueprint.Get(), TEXT("ManageAssetBlueprint"), TEXT("SetDefaults"), TEXT("Mesh.RelativeLocation.Z"), TEXT("123"));
	Package->SetDirtyFlag(false);
	TestFalse(TEXT("Owned native component scalar preview"), AssetEditCall(TEXT("GetAssetEditPreview"), Args).HasErrors());
	TestFalse(TEXT("Preview does not dirty package"), Package->IsDirty());
	TestTrue(TEXT("Preview does not change component"), Defaults->GetMesh()->GetRelativeLocation().Equals(Before));
	Args->RemoveField(TEXT("Capability")); Args->SetBoolField(TEXT("bVerify"), true);
	TestFalse(TEXT("Owned component scalar write and readback"), AssetEditCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestTrue(TEXT("Component scalar written"), FMath::IsNearlyEqual(static_cast<double>(Defaults->GetMesh()->GetRelativeLocation().Z), 123.0));
	const auto ExternalArgs = AssetEditArgs(Blueprint.Get(), TEXT("ManageAssetBlueprint"), TEXT("SetDefaults"), TEXT("Owner.bCanBeDamaged"), TEXT("false"));
	TestTrue(TEXT("Null subobject preview rejected"), AssetEditCall(TEXT("GetAssetEditPreview"), ExternalArgs).HasErrors());
	FObjectPropertyBase* OwnerProperty = FindFProperty<FObjectPropertyBase>(AActor::StaticClass(), TEXT("Owner"));
	if (TestNotNull(TEXT("Owner reference property"), OwnerProperty))
	{
		OwnerProperty->SetObjectPropertyValue_InContainer(Defaults, AActor::StaticClass()->GetDefaultObject());
		TestTrue(TEXT("External subobject preview rejected"), AssetEditCall(TEXT("GetAssetEditPreview"), ExternalArgs).HasErrors());
		OwnerProperty->SetObjectPropertyValue_InContainer(Defaults, nullptr);
	}
	Package->SetDirtyFlag(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusAssetAutomatedExportTest, "NexusLink.AssetEdit.AutomatedExport",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusAssetAutomatedExportTest::RunTest(const FString& Parameters)
{
	UPackage* Package = AssetEditPackage();
	TStrongObjectPtr<UDataTable> Table(NewObject<UDataTable>(Package, TEXT("Table"), RF_Public | RF_Transactional));
	Table->RowStruct = FNexusReliabilityTestRow::StaticStruct();
	Table->AddRow(TEXT("Row"), FNexusReliabilityTestRow());
	const FString File = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("FeedbackExport.t3d"));
	ON_SCOPE_EXIT { IFileManager::Get().Delete(*File); Package->SetDirtyFlag(false); };
	auto Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("AssetPath"), Table->GetPathName());
	Args->SetStringField(TEXT("OutputPath"), File);
	const FCapabilityResult Result = AssetEditCall(TEXT("ExportAsset"), Args);
	if (!TestFalse(TEXT("Automated typed text export"), Result.HasErrors())) return false;
	TestTrue(TEXT("Automated mode returned"), Result.Entries[0]->AsObject()->GetBoolField(TEXT("bAutomated")));
	FString Text;
	TestTrue(TEXT("Export file exists"), FFileHelper::LoadFileToString(Text, *File));
	TestTrue(TEXT("Correct exporter content"), Text.Contains(TEXT("Begin Object")) && Text.Contains(TEXT("DataTable")));
	Args->SetStringField(TEXT("OutputPath"), File + TEXT(".unsupported"));
	TestTrue(TEXT("Unsupported extension rejected"), AssetEditCall(TEXT("ExportAsset"), Args).HasErrors());
	TestFalse(TEXT("Unsupported export does not create a file"), IFileManager::Get().FileExists(*(File + TEXT(".unsupported"))));
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

static TSharedPtr<FJsonObject> AssetStructureArgs(UObject* Asset, const TCHAR* Capability, const TSharedPtr<FJsonObject>& Operation)
{
	TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("AssetPath"), Asset->GetPathName());
	Args->SetStringField(TEXT("Capability"), Capability);
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Operation)});
	return Args;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusAssetInterfaceStructurePreviewTest, "NexusLink.AssetEdit.InterfaceStructurePreview",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusAssetInterfaceStructurePreviewTest::RunTest(const FString& Parameters)
{
	UPackage* Package = AssetEditPackage();
	TStrongObjectPtr<UBlueprint> Blueprint(FKismetEditorUtilities::CreateBlueprint(AActor::StaticClass(), Package,
		TEXT("Blueprint"), BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass()));
#if NX_UE_HAS_BP_INTERFACE_ASSET_PATH
	FBlueprintEditorUtils::ImplementNewInterface(Blueprint.Get(), UNexusPreviewTestInterface::StaticClass()->GetClassPathName());
#else
	FBlueprintEditorUtils::ImplementNewInterface(Blueprint.Get(), UNexusPreviewTestInterface::StaticClass()->GetFName());
#endif
	if (!TestEqual(TEXT("生成接口描述"), Blueprint->ImplementedInterfaces.Num(), 1)) return false;
	if (!TestEqual(TEXT("带返回值的接口生成实现图"), Blueprint->ImplementedInterfaces[0].Graphs.Num(), 1)) return false;
	UEdGraph* InterfaceGraph = Blueprint->ImplementedInterfaces[0].Graphs[0];
	if (!TestTrue(TEXT("接口图有实现节点"), InterfaceGraph->Nodes.Num() > 0)) return false;
	UEdGraphNode* InterfaceNode = InterfaceGraph->Nodes[0];
	const int32 InterfaceNodeCount = InterfaceGraph->Nodes.Num();
	UEdGraph* EventGraph = FBlueprintEditorUtils::CreateNewGraph(Blueprint.Get(), TEXT("PreviewEventGraph"), UEdGraph::StaticClass(), UEdGraphSchema_K2::StaticClass());
	Blueprint->UbergraphPages.Add(EventGraph);
	UEdGraphNode* EventNode = NewObject<UEdGraphNode>(EventGraph);
	EventNode->CreateNewGuid();
	EventGraph->AddNode(EventNode);
	TSharedPtr<FJsonObject> Operation = MakeShared<FJsonObject>();
	Operation->SetStringField(TEXT("Action"), TEXT("RemoveNode"));
	Operation->SetStringField(TEXT("GraphName"), EventGraph->GetName());
	Operation->SetStringField(TEXT("NodeId"), EventNode->NodeGuid.ToString());
	TSharedPtr<FJsonObject> Args = AssetStructureArgs(Blueprint.Get(), TEXT("ManageAssetBlueprint"), Operation);
	Package->SetDirtyFlag(false);
	const FCapabilityResult Preview = AssetEditCall(TEXT("GetAssetEditPreview"), Args);
	if (!TestFalse(TEXT("接口图不妨碍结构预览"), Preview.HasErrors())) return false;
	TestEqual(TEXT("预览只移除指定节点"), Preview.TopFields->GetArrayField(TEXT("Removed")).Num(), 1);
	TestEqual(TEXT("预览保留原事件图"), EventGraph->Nodes.Num(), 1);
	TestEqual(TEXT("预览保留原接口图"), InterfaceGraph->Nodes.Num(), InterfaceNodeCount);
	TestFalse(TEXT("预览不标脏"), Package->IsDirty());
	// 接口图本身也必须能在副本中定位。
	Operation->SetStringField(TEXT("GraphName"), InterfaceGraph->GetName());
	Operation->SetStringField(TEXT("NodeId"), InterfaceNode->NodeGuid.ToString());
	TestFalse(TEXT("可预览接口图节点"), AssetEditCall(TEXT("GetAssetEditPreview"), Args).HasErrors());
	Operation->SetStringField(TEXT("GraphName"), EventGraph->GetName());
	Operation->SetStringField(TEXT("NodeId"), EventNode->NodeGuid.ToString());
	Args->RemoveField(TEXT("Capability"));
	Args->SetBoolField(TEXT("bVerifyStructure"), true);
	const FCapabilityResult Changed = AssetEditCall(TEXT("ManageAssetBlueprint"), Args);
	if (!TestFalse(TEXT("接口图不造成错误的结构不一致"), Changed.HasErrors())) return false;
	TestTrue(TEXT("实际变更通过结构回读"), Changed.Entries[0]->AsObject()->GetBoolField(TEXT("bStructureVerified")));
	TestEqual(TEXT("实际接口图保持不变"), InterfaceGraph->Nodes.Num(), InterfaceNodeCount);
	Package->SetDirtyFlag(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusAssetUnicodeStructureHashTest, "NexusLink.AssetEdit.UnicodeStructureHash",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusAssetUnicodeStructureHashTest::RunTest(const FString& Parameters)
{
	UPackage* Package = AssetEditPackage();
	TStrongObjectPtr<UWidgetBlueprint> Blueprint(Cast<UWidgetBlueprint>(FKismetEditorUtilities::CreateBlueprint(UUserWidget::StaticClass(), Package,
		TEXT("Widget"), BPTYPE_Normal, UWidgetBlueprint::StaticClass(), UWidgetBlueprintGeneratedClass::StaticClass())));
	UWidgetTree* Tree = Blueprint->WidgetTree;
	UCanvasPanel* Root = Tree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("Root"));
	Tree->RootWidget = Root;
	UCanvasPanel* Left = Tree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("左框"));
	UCanvasPanel* Right = Tree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("右框"));
	Root->AddChild(Left);
	Root->AddChild(Right);
	UTextBlock* Label = Tree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Label"));
	Left->AddChild(Label);
	TSharedPtr<FJsonObject> Operation = MakeShared<FJsonObject>();
	Operation->SetStringField(TEXT("Action"), TEXT("Move"));
	Operation->SetStringField(TEXT("WidgetName"), TEXT("Label"));
	Operation->SetStringField(TEXT("ParentWidget"), Left->GetName());
	TSharedPtr<FJsonObject> Args = AssetStructureArgs(Blueprint.Get(), TEXT("ManageAssetUserWidget"), Operation);
	const FCapabilityResult Before = AssetEditCall(TEXT("GetAssetEditPreview"), Args);
	if (!TestFalse(TEXT("中文父面板预览"), Before.HasErrors())) return false;
	const FString ExpectedHash = Before.TopFields->GetStringField(TEXT("StructureHash"));
	Right->AddChild(Label);
	const FCapabilityResult After = AssetEditCall(TEXT("GetAssetEditPreview"), Args);
	if (!TestFalse(TEXT("移动后仍可预览"), After.HasErrors())) return false;
	TestNotEqual(TEXT("中文父节点变化必须改变结构哈希"), ExpectedHash, After.TopFields->GetStringField(TEXT("StructureHash")));
	Args->RemoveField(TEXT("Capability"));
	Args->SetStringField(TEXT("ExpectedStructureHash"), ExpectedHash);
	TestTrue(TEXT("拒绝中文层级变化后的旧哈希"), AssetEditCall(TEXT("ManageAssetUserWidget"), Args).HasErrors());
	TestTrue(TEXT("拒绝后控件仍在新父面板"), Label->GetParent() == Right);
	Package->SetDirtyFlag(false);
	return true;
}

#if NX_UE_HAS_WIDGET_BLUEPRINT_OPERATIONS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusAssetWidgetStructureRemovalTest, "NexusLink.AssetEdit.WidgetStructureRemoval",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusAssetWidgetStructureRemovalTest::RunTest(const FString& Parameters)
{
	UPackage* Package = AssetEditPackage();
	TStrongObjectPtr<UWidgetBlueprint> Blueprint(Cast<UWidgetBlueprint>(FKismetEditorUtilities::CreateBlueprint(UUserWidget::StaticClass(), Package,
		TEXT("Widget"), BPTYPE_Normal, UWidgetBlueprint::StaticClass(), UWidgetBlueprintGeneratedClass::StaticClass())));
	UWidgetTree* Tree = Blueprint->WidgetTree;
	UCanvasPanel* Root = Tree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("Root"));
	Tree->RootWidget = Root;
	UTextBlock* Label = Tree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("Label"));
	Label->bIsVariable = true;
	Root->AddChild(Label);
	Blueprint->OnVariableAdded(Root->GetFName());
	Blueprint->OnVariableAdded(Label->GetFName());
	FKismetEditorUtilities::CompileBlueprint(Blueprint.Get());
	FGuid VariableGuid;
	if (!TestTrue(TEXT("控件变量具有生成类 GUID"), UBlueprint::GetGuidFromClassByFieldName<FProperty>(Blueprint->SkeletonGeneratedClass, Label->GetFName(), VariableGuid))) return false;
	UEdGraph* EventGraph = FBlueprintEditorUtils::CreateNewGraph(Blueprint.Get(), TEXT("PreviewEventGraph"), UEdGraph::StaticClass(), UEdGraphSchema_K2::StaticClass());
	Blueprint->UbergraphPages.Add(EventGraph);
	UK2Node_VariableGet* Getter = NewObject<UK2Node_VariableGet>(EventGraph);
	Getter->VariableReference.SetSelfMember(Label->GetFName(), VariableGuid);
	Getter->CreateNewGuid();
	EventGraph->AddNode(Getter);
	Getter->AllocateDefaultPins();
	if (!TestTrue(TEXT("引擎识别控件变量引用"), FBlueprintEditorUtils::IsVariableUsed(Blueprint.Get(), Label->GetFName()))) return false;
	TSharedPtr<FJsonObject> Operation = MakeShared<FJsonObject>();
	Operation->SetStringField(TEXT("Action"), TEXT("Remove"));
	Operation->SetStringField(TEXT("WidgetName"), Label->GetName());
	TSharedPtr<FJsonObject> Args = AssetStructureArgs(Blueprint.Get(), TEXT("ManageAssetUserWidget"), Operation);
	Package->SetDirtyFlag(false);
	const int32 UndoCount = GEditor->Trans->GetQueueLength();
	const FCapabilityResult Preview = AssetEditCall(TEXT("GetAssetEditPreview"), Args);
	if (!TestFalse(TEXT("预览删除带引用的控件"), Preview.HasErrors())) return false;
	TestEqual(TEXT("删除计划含控件与引用节点"), Preview.TopFields->GetArrayField(TEXT("Removed")).Num(), 2);
	TestEqual(TEXT("预览不删除原 getter"), EventGraph->Nodes.Num(), 1);
	TestTrue(TEXT("预览不删除原控件"), Tree->FindWidget(TEXT("Label")) == Label);
	TestFalse(TEXT("结构预览不标脏"), Package->IsDirty());
	TestEqual(TEXT("结构预览不记录 Undo"), GEditor->Trans->GetQueueLength(), UndoCount);
	Args->RemoveField(TEXT("Capability"));
	Args->SetBoolField(TEXT("bVerifyStructure"), true);
	Args->SetBoolField(TEXT("bSaveToDisk"), true);
	int32 SaveCount = 0;
	TGuardValue<decltype(FNexusEditorServices::ApplyManageFinalize)> Guard(FNexusEditorServices::ApplyManageFinalize,
		[&](const FString&, bool, bool bSave, TSharedPtr<FJsonObject>&) { if (bSave) ++SaveCount; });
	const FCapabilityResult Changed = AssetEditCall(TEXT("ManageAssetUserWidget"), Args);
	if (!TestFalse(TEXT("真实控件删除与计划一致"), Changed.HasErrors())) return false;
	TestTrue(TEXT("控件删除通过结构验证"), Changed.Entries[0]->AsObject()->GetBoolField(TEXT("bStructureVerified")));
	TestEqual(TEXT("引擎删除引用节点"), EventGraph->Nodes.Num(), 0);
	TestNull(TEXT("引擎删除目标控件"), Tree->FindWidget(TEXT("Label")));
	TestEqual(TEXT("合法删除允许自动保存"), SaveCount, 1);
	Package->SetDirtyFlag(false);
	return true;
}
#endif

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusAssetStructureFailureSaveTest, "NexusLink.AssetEdit.StructureFailureNeverSaves",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusAssetStructureFailureSaveTest::RunTest(const FString& Parameters)
{
	UPackage* Package = AssetEditPackage();
	TStrongObjectPtr<UBlueprint> Blueprint(FKismetEditorUtilities::CreateBlueprint(AActor::StaticClass(), Package,
		TEXT("Blueprint"), BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass()));
	UEdGraph* Graph = FBlueprintEditorUtils::CreateNewGraph(Blueprint.Get(), TEXT("PreviewEventGraph"), UEdGraph::StaticClass(), UEdGraphSchema_K2::StaticClass());
	Blueprint->UbergraphPages.Add(Graph);
	TArray<TSharedPtr<FJsonValue>> Operations;
	for (int32 NodeIndex = 0; NodeIndex < 2; ++NodeIndex)
	{
		UEdGraphNode* Node = NewObject<UEdGraphNode>(Graph);
		Node->CreateNewGuid();
		Graph->AddNode(Node);
		TSharedPtr<FJsonObject> Operation = MakeShared<FJsonObject>();
		Operation->SetStringField(TEXT("Action"), TEXT("RemoveNode"));
		Operation->SetStringField(TEXT("GraphName"), Graph->GetName());
		Operation->SetStringField(TEXT("NodeId"), Node->NodeGuid.ToString());
		Operations.Add(MakeShared<FJsonValueObject>(Operation));
	}
	// 仅原图的真实第二次删除触发外部变更，制造合法写入后的结构回读不一致。
	int32 RemovalCount = 0;
	const FDelegateHandle ChangedHandle = Graph->AddOnGraphChangedHandler(FOnGraphChanged::FDelegate::CreateLambda(
		[&](const FEdGraphEditAction& Change)
		{
			if ((Change.Action & GRAPHACTION_RemoveNode) && ++RemovalCount == 2)
			{
				UEdGraphNode* Added = NewObject<UEdGraphNode>(Graph);
				Added->CreateNewGuid();
				Graph->AddNode(Added);
			}
		}));
	TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("AssetPath"), Blueprint->GetPathName());
	Args->SetArrayField(TEXT("Operations"), Operations);
	Args->SetBoolField(TEXT("bVerifyStructure"), true);
	Args->SetBoolField(TEXT("bSaveToDisk"), true);
	int32 SaveCount = 0;
	TGuardValue<decltype(FNexusEditorServices::ApplyManageFinalize)> Guard(FNexusEditorServices::ApplyManageFinalize,
		[&](const FString&, bool, bool bSave, TSharedPtr<FJsonObject>&) { if (bSave) ++SaveCount; });
	const FCapabilityResult Result = AssetEditCall(TEXT("ManageAssetBlueprint"), Args);
	Graph->RemoveOnGraphChangedHandler(ChangedHandle);
	if (!TestEqual(TEXT("合法结构操作均执行"), Result.Entries.Num(), 2)) return false;
	TestTrue(TEXT("第一项结构验证成功"), Result.Entries[0]->AsObject()->GetBoolField(TEXT("bStructureVerified")));
	TestFalse(TEXT("第二项真实结构验证失败"), Result.Entries[1]->AsObject()->GetBoolField(TEXT("bStructureVerified")));
	TestTrue(TEXT("结构不一致按错误返回"), Result.HasErrors());
	TestEqual(TEXT("部分成功后的结构回读失败禁止保存"), SaveCount, 0);
	if (!TestEqual(TEXT("保留已发生的内存变更"), Graph->Nodes.Num(), 1)) return false;
	TSharedPtr<FJsonObject> Retry = MakeShared<FJsonObject>(*Operations[0]->AsObject());
	Retry->SetStringField(TEXT("NodeId"), Graph->Nodes[0]->NodeGuid.ToString());
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Retry)});
	TestFalse(TEXT("后续合法结构写入通过验证"), AssetEditCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestEqual(TEXT("全部结构验证成功允许保存"), SaveCount, 1);
	Package->SetDirtyFlag(false);
	return true;
}
#endif
