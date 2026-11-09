// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"
#if WITH_EDITOR
#include "NexusCapabilityRegistry.h"
#include "NexusRelatedDataAsset.h"
#include "NexusNavigationTestData.h"
#include "Utils/NexusAssetUtils.h"
#include "Utils/NexusArgs.h"
#include "Utils/NexusPropertyUtils.h"
#include "Utils/NexusVersionCompat.h"
#include "Utils/NexusJsonUtils.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/SCS_Node.h"
#include "Engine/InheritableComponentHandler.h"
#include "Engine/StaticMesh.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/Level.h"
#include "Engine/DataTable.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"
#include "AIController.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "WidgetBlueprint.h"
#include "Blueprint/WidgetBlueprintGeneratedClass.h"
#include "Blueprint/UserWidget.h"
#include "Animation/AnimBlueprint.h"
#include "Animation/AnimBlueprintGeneratedClass.h"
#include "Animation/AnimInstance.h"
#include "Animation/Skeleton.h"
#include "Animation/AnimSequence.h"
#include "AnimGraphNode_SequencePlayer.h"
#include "ReferenceSkeleton.h"
#if NX_UE_HAS_ANIM_SEQUENCE_DATA_MODEL
#include "Animation/AnimData/IAnimationDataController.h"
#endif
#include "Misc/ScopeExit.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "HAL/FileManager.h"
#include "UObject/StrongObjectPtr.h"
#include "NavigationSystem.h"
#include "K2Node_CallFunction.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_VariableGet.h"
#include "Kismet/KismetSystemLibrary.h"
#include "EdGraphSchema_K2.h"
#include "Utils/NexusAssetEditorUtils.h"
#include "Utils/NexusPinTypeUtils.h"
#include "Kismet2/StructureEditorUtils.h"
#if NX_UE_HAS_STRUCT_UTILS_HEADER
#include "StructUtils/UserDefinedStruct.h"
#else
#include "Engine/UserDefinedStruct.h"
#endif
#include "Misc/PackageName.h"
#include "Editor.h"

static FCapabilityResult RelatedCall(const TCHAR* Name, const TSharedPtr<FJsonObject>& Args)
{
	const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(Name);
	return Record ? Record->Instance->Run(Args) : FCapabilityResult::MakeFatal(TEXT("Missing capability"));
}
static UBlueprint* RelatedBlueprint(UClass* Parent, UClass* Type = UBlueprint::StaticClass(), UClass* Generated = UBlueprintGeneratedClass::StaticClass())
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/Related_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	return FKismetEditorUtilities::CreateBlueprint(Parent, Package, FName(*FPackageName::GetShortName(Package->GetName())), BPTYPE_Normal, Type, Generated);
}
static TSharedPtr<FJsonObject> RelatedArgs(UObject* Asset, const TSharedPtr<FJsonObject>& Operation)
{
	auto Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("AssetPath"), Asset->GetPathName());
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Operation)});
	return Args;
}
static TSharedPtr<FJsonObject> RelatedOperation(const TCHAR* Action)
{
	auto Operation = MakeShared<FJsonObject>(); Operation->SetStringField(TEXT("Action"), Action); return Operation;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusFeedbackDefaultsTest, "NexusLink.EditorRelated.FeedbackDefaultsAndReferences", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusFeedbackDefaultsTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UBlueprint> Parent(RelatedBlueprint(AActor::StaticClass()));
	FKismetEditorUtilities::CompileBlueprint(Parent.Get());
	TStrongObjectPtr<UBlueprint> Child(RelatedBlueprint(Parent->GeneratedClass));
	FKismetEditorUtilities::CompileBlueprint(Child.Get());
	ON_SCOPE_EXIT { Parent->GetOutermost()->SetDirtyFlag(false); Child->GetOutermost()->SetDirtyFlag(false); };
	auto Existing = RelatedOperation(TEXT("SetDefaults")); Existing->SetStringField(TEXT("PropertyPath"), TEXT("InitialLifeSpan")); Existing->SetStringField(TEXT("Value"), TEXT("99"));
	auto ExistingArgs = RelatedArgs(Child.Get(), Existing); ExistingArgs->SetBoolField(TEXT("bCompile"), true);
	if (!TestFalse(TEXT("Existing child override fixture"), RelatedCall(TEXT("ManageAssetBlueprint"), ExistingArgs).HasErrors())) return false;
	UPackage* WorldPackage = CreatePackage(*(TEXT("/Game/_McpTest/DefaultsWorld_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("DefaultsWorld"), WorldPackage);
	ON_SCOPE_EXIT { WorldPackage->SetDirtyFlag(false); World->DestroyWorld(false); };
	AActor* Placed = World->SpawnActor<AActor>(Child->GeneratedClass);
	if (!TestNotNull(TEXT("Placed child fixture"), Placed)) return false;
	const FString ActorName = Placed->GetName();
	auto Operation = RelatedOperation(TEXT("AddVariable"));
	Operation->SetStringField(TEXT("VariableName"), TEXT("Distance"));
	Operation->SetStringField(TEXT("VariableType"), TEXT("float"));
	Operation->SetStringField(TEXT("DefaultValue"), TEXT("120"));
	Operation->SetBoolField(TEXT("bIsPublic"), true);
	auto Args = RelatedArgs(Parent.Get(), Operation); Args->SetBoolField(TEXT("bCompile"), true);
	if (!TestFalse(TEXT("Add configured inherited variable"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	FKismetEditorUtilities::CompileBlueprint(Child.Get());
	FProperty* Property = FindFProperty<FProperty>(Parent->GeneratedClass, TEXT("Distance"));
	TestTrue(TEXT("Instance editable"), Property && !Property->HasAnyPropertyFlags(CPF_DisableEditOnInstance));
	FString Value, Error;
	void* ChildValue = nullptr; FProperty* ChildProperty = nullptr;
	if (TestTrue(TEXT("Child reads parent default"), FNexusPropertyUtils::ResolvePropertyWrite(Child->GeneratedClass->GetDefaultObject(), {TEXT("Distance")}, 0, ChildProperty, ChildValue, Error)))
		FNexusPropertyUtils::ExportText(ChildProperty, Value, ChildValue);
	TestEqual(TEXT("Default propagated"), FCString::Atod(*Value), 120.0);
	const auto ReadNumber = [&](UObject* Object, const TCHAR* Name) {
		FProperty* Field = nullptr; void* Address = nullptr; FString Text, ReadError;
		if (!FNexusPropertyUtils::ResolvePropertyWrite(Object, {Name}, 0, Field, Address, ReadError)) { AddError(ReadError); return -1.0; }
		FNexusPropertyUtils::ExportText(Field, Text, Address); return FCString::Atod(*Text);
	};
	AActor* CurrentActor = FindObject<AActor>(World->PersistentLevel, *ActorName);
	TestEqual(TEXT("Placed instance inherits new default"), ReadNumber(CurrentActor, TEXT("Distance")), 120.0);
	TestEqual(TEXT("Existing CDO override retained"), ReadNumber(Child->GeneratedClass->GetDefaultObject(), TEXT("InitialLifeSpan")), 99.0);
	TestEqual(TEXT("Existing actor override retained"), ReadNumber(CurrentActor, TEXT("InitialLifeSpan")), 99.0);
	auto Editable = RelatedOperation(TEXT("SetVariableEditable")); Editable->SetStringField(TEXT("VariableName"), TEXT("Distance")); Editable->SetBoolField(TEXT("bEditable"), false);
	TestFalse(TEXT("Disable instance editing"), RelatedCall(TEXT("ManageAssetBlueprint"), RelatedArgs(Parent.Get(), Editable)).HasErrors());
	auto Read = MakeShared<FJsonObject>(); Read->SetStringField(TEXT("AssetPath"), Parent->GetPathName()); Read->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("Variable"))});
	const auto Variables = RelatedCall(TEXT("GetAssetBlueprint"), Read);
	if (!TestFalse(TEXT("Read editable flag"), Variables.HasErrors())) return false;
	TestFalse(TEXT("Getter reports actual instance editability"), FNexusArgs(Variables.Entries[0]->AsObject()->GetArrayField(TEXT("Variables"))[0]->AsObject()).Bool(TEXT("bIsPublic")));
	Operation->SetStringField(TEXT("VariableName"), TEXT("ActorClass"));
	Operation->SetStringField(TEXT("VariableType"), TEXT("ClassReference</Script/Engine.Actor>"));
	Operation->RemoveField(TEXT("DefaultValue"));
	Args = RelatedArgs(Child.Get(), Operation); Args->SetBoolField(TEXT("bCompile"), true);
	if (!TestFalse(TEXT("Class property fixture"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	auto Edit = RelatedOperation(TEXT("SetDefaults"));
	Edit->SetStringField(TEXT("PropertyPath"), TEXT("ActorClass"));
	Edit->SetStringField(TEXT("Value"), TEXT("Class'/Script/Engine.Character'"));
	auto PreviewArgs = RelatedArgs(Child.Get(), Edit); PreviewArgs->SetStringField(TEXT("Capability"), TEXT("ManageAssetBlueprint"));
	const auto Preview = RelatedCall(TEXT("GetAssetEditPreview"), PreviewArgs);
	TestFalse(TEXT("Class reference preview"), Preview.HasErrors());
	Args = RelatedArgs(Child.Get(), Edit); Args->SetBoolField(TEXT("bCompile"), true); Args->SetBoolField(TEXT("bVerify"), true);
	Edit->SetStringField(TEXT("ExpectedValue"), TEXT("None"));
	TestFalse(TEXT("Class reference verified write"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	Edit->SetStringField(TEXT("Value"), TEXT("Class'/Script/CoreUObject.Object'"));
	Edit->RemoveField(TEXT("ExpectedValue"));
	TestTrue(TEXT("Incompatible class rejected"), RelatedCall(TEXT("GetAssetEditPreview"), PreviewArgs).HasErrors());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusFeedbackRetargetTest, "NexusLink.EditorRelated.FeedbackRetarget", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusFeedbackRetargetTest::RunTest(const FString& Parameters)
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/Retarget_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	TStrongObjectPtr<USkeleton> Source(NewObject<USkeleton>(Package, TEXT("Source"), RF_Public | RF_Standalone));
	TStrongObjectPtr<USkeleton> Target(NewObject<USkeleton>(Package, TEXT("Target"), RF_Public | RF_Standalone));
	for (USkeleton* Skeleton : {Source.Get(), Target.Get()})
	{
		FReferenceSkeletonModifier Modifier(const_cast<FReferenceSkeleton&>(Skeleton->GetReferenceSkeleton()), Skeleton);
		Modifier.Add(FMeshBoneInfo(TEXT("root"), TEXT("root"), INDEX_NONE), FTransform::Identity);
	}
	TStrongObjectPtr<UAnimSequence> Sequence(NewObject<UAnimSequence>(Package, TEXT("Sequence"), RF_Public | RF_Standalone));
	Sequence->SetSkeleton(Source.Get());
#if NX_UE_HAS_ANIM_SEQUENCE_DATA_MODEL
	auto& Controller = Sequence->GetController(); Controller.InitializeModel();
	Controller.SetFrameRate(FFrameRate(30, 1)); Controller.SetNumberOfFrames(FFrameNumber(1));
	Controller.AddBoneCurve(TEXT("root"));
	Controller.SetBoneTrackKeys(TEXT("root"), {FVector3f::ZeroVector, FVector3f::ZeroVector}, {FQuat4f::Identity, FQuat4f::Identity}, {FVector3f::OneVector, FVector3f::OneVector});
#else
	FRawAnimSequenceTrack Track; Track.PosKeys.Add(FVector::ZeroVector); Track.RotKeys.Add(FQuat::Identity); Track.ScaleKeys.Add(FVector::OneVector);
	Sequence->AddNewRawTrack(TEXT("root"), &Track); Sequence->SetRawNumberOfFrame(1); Sequence->SequenceLength = 1.f / 30.f;
	Sequence->PostProcessSequence();
#endif
	ON_SCOPE_EXIT { Package->SetDirtyFlag(false); };
	auto Operation = RelatedOperation(TEXT("Retarget")); Operation->SetStringField(TEXT("TargetSkeleton"), Target->GetPathName());
	Operation->SetBoolField(TEXT("bValidateOnly"), true);
	auto Args = RelatedArgs(Sequence.Get(), Operation);
	TestFalse(TEXT("Sequence retarget preflight"), RelatedCall(TEXT("ManageAssetAnimSequence"), Args).HasErrors());
	TestTrue(TEXT("Preflight keeps source skeleton"), Sequence->GetSkeleton() == Source.Get());
	Operation->SetBoolField(TEXT("bValidateOnly"), false);
	TestTrue(TEXT("Retarget requires acknowledgment"), RelatedCall(TEXT("ManageAssetAnimSequence"), Args).HasErrors());
	Operation->SetBoolField(TEXT("bAllowPotentialDataLoss"), true);
	TestFalse(TEXT("Sequence retarget"), RelatedCall(TEXT("ManageAssetAnimSequence"), Args).HasErrors());
	TestTrue(TEXT("Sequence uses target skeleton"), Sequence->GetSkeleton() == Target.Get());
	TStrongObjectPtr<UBlueprint> Blueprint(RelatedBlueprint(UAnimInstance::StaticClass(), UAnimBlueprint::StaticClass(), UAnimBlueprintGeneratedClass::StaticClass()));
	CastChecked<UAnimBlueprint>(Blueprint.Get())->TargetSkeleton = Source.Get();
	FKismetEditorUtilities::CompileBlueprint(Blueprint.Get());
	ON_SCOPE_EXIT { Blueprint->GetOutermost()->SetDirtyFlag(false); };
	Args = RelatedArgs(Blueprint.Get(), Operation); Args->SetBoolField(TEXT("bCompile"), true);
	TStrongObjectPtr<UAnimSequence> Original(DuplicateObject<UAnimSequence>(Sequence.Get(), Package, TEXT("Original")));
	Original->SetSkeleton(Source.Get());
	auto AddNode = RelatedOperation(TEXT("AddNode")); AddNode->SetStringField(TEXT("GraphName"), TEXT("AnimGraph"));
	AddNode->SetStringField(TEXT("NodeClass"), TEXT("SequencePlayer")); AddNode->SetStringField(TEXT("SequencePath"), Original->GetPathName());
	const auto Added = RelatedCall(TEXT("ManageAssetAnimBlueprint"), RelatedArgs(Blueprint.Get(), AddNode));
	if (!TestFalse(TEXT("Animation reference fixture"), Added.HasErrors())) return false;
	TestTrue(TEXT("Unmapped animation rejected"), RelatedCall(TEXT("ManageAssetAnimBlueprint"), Args).HasErrors());
	auto Remap = MakeShared<FJsonObject>(); Remap->SetStringField(TEXT("SourceAssetPath"), Original->GetPathName()); Remap->SetStringField(TEXT("TargetAssetPath"), Sequence->GetPathName());
	Operation->SetArrayField(TEXT("AnimationRemaps"), {MakeShared<FJsonValueObject>(Remap)});
	TestFalse(TEXT("Blueprint retarget"), RelatedCall(TEXT("ManageAssetAnimBlueprint"), Args).HasErrors());
	TestTrue(TEXT("Blueprint uses target skeleton"), CastChecked<UAnimBlueprint>(Blueprint.Get())->TargetSkeleton == Target.Get());
	TArray<UAnimGraphNode_SequencePlayer*> Players;
	FBlueprintEditorUtils::GetAllNodesOfClass(Blueprint.Get(), Players);
	TestTrue(TEXT("Animation node remapped"), Players.Num() == 1 && Players[0]->GetAnimationAsset() == Sequence.Get());
	TestTrue(TEXT("Source animation is unchanged"), Original->GetSkeleton() == Source.Get());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRelatedTypesTest, "NexusLink.EditorRelated.VariableTypes", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusRelatedTypesTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UBlueprint> Blueprint(RelatedBlueprint(AActor::StaticClass()));
	ON_SCOPE_EXIT { Blueprint->GetOutermost()->SetDirtyFlag(false); };
	auto Operation = RelatedOperation(TEXT("AddVariable"));
	Operation->SetStringField(TEXT("VariableName"), TEXT("Items")); Operation->SetStringField(TEXT("VariableType"), TEXT("Map<name,vector>"));
	auto Args = RelatedArgs(Blueprint.Get(), Operation); Args->SetBoolField(TEXT("bCompile"), true);
	if (!TestFalse(TEXT("Create map"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	const FGuid Guid = Blueprint->NewVariables[0].VarGuid;
	auto Read = MakeShared<FJsonObject>(); Read->SetStringField(TEXT("AssetPath"), Blueprint->GetPathName()); Read->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("variable"))});
	const auto Result = RelatedCall(TEXT("GetAssetBlueprint"), Read);
	if (!TestFalse(TEXT("Read type"), Result.HasErrors())) return false;
	const auto Variables = Result.Entries[0]->AsObject()->GetArrayField(TEXT("Variables"));
	if (!TestEqual(TEXT("One variable"), Variables.Num(), 1)) return false;
	const auto Type = Variables[0]->AsObject();
	TestEqual(TEXT("Container kind retained"), Type->GetStringField(TEXT("ContainerType")), FString(TEXT("Map")));
	TestEqual(TEXT("Key type retained"), Type->GetStringField(TEXT("KeyType")), FString(TEXT("name")));
	TestTrue(TEXT("Value type path retained"), Type->GetStringField(TEXT("ValueTypeObjectPath")).EndsWith(TEXT(".Vector")));
	Operation->SetStringField(TEXT("Action"), TEXT("ChangeVariableType")); Operation->SetStringField(TEXT("VariableType"), TEXT("int"));
	TestTrue(TEXT("Type change needs loss opt-in"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	Operation->SetBoolField(TEXT("bAllowPotentialDataLoss"), true);
	AddExpectedError(TEXT("Type mismatch in Items"), EAutomationExpectedErrorFlags::Contains, 0);
	TestFalse(TEXT("Change member type"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestTrue(TEXT("GUID survives"), Blueprint->NewVariables[0].VarGuid == Guid);
	Operation = RelatedOperation(TEXT("AddFunction")); Operation->SetStringField(TEXT("FunctionName"), TEXT("Compute")); Args = RelatedArgs(Blueprint.Get(), Operation);
	TestFalse(TEXT("Function fixture"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	Operation->SetStringField(TEXT("Action"), TEXT("AddLocalVariable")); Operation->SetStringField(TEXT("VariableName"), TEXT("LocalValue")); Operation->SetStringField(TEXT("VariableType"), TEXT("int")); Args->SetBoolField(TEXT("bCompile"), true);
	TestFalse(TEXT("Local fixture"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	Operation->SetStringField(TEXT("Action"), TEXT("RenameLocalVariable")); Operation->SetStringField(TEXT("NewVariableName"), TEXT("RenamedLocal"));
	TestFalse(TEXT("Rename local"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	UEdGraph* Compute = nullptr;
	for (UEdGraph* Graph : Blueprint->FunctionGraphs) if (Graph && Graph->GetName() == TEXT("Compute")) Compute = Graph;
	if (TestNotNull(TEXT("Function graph retained"), Compute)) TestNotNull(TEXT("Renamed local exists"), FBlueprintEditorUtils::FindLocalVariable(Blueprint.Get(), Compute, TEXT("RenamedLocal")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRelatedVariableSafetyTest, "NexusLink.EditorRelated.VariableSafety", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusRelatedVariableSafetyTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UBlueprint> Blueprint(RelatedBlueprint(AActor::StaticClass()));
	ON_SCOPE_EXIT { Blueprint->GetOutermost()->SetDirtyFlag(false); };
	FEdGraphPinType Integer; Integer.PinCategory = UEdGraphSchema_K2::PC_Int;
	FBlueprintEditorUtils::AddMemberVariable(Blueprint.Get(), TEXT("Value"), Integer, TEXT("17"));
	FBPVariableDescription& Variable = Blueprint->NewVariables[0];
	FGuid OriginalGuid = Variable.VarGuid;
	UEdGraph* Graph = Blueprint->UbergraphPages[0];
	UK2Node_VariableGet* Reference = NewObject<UK2Node_VariableGet>(Graph);
	Reference->VariableReference.SetSelfMember(TEXT("Value"), OriginalGuid);
	Graph->AddNode(Reference); Reference->CreateNewGuid(); Reference->AllocateDefaultPins();
	auto Operation = RelatedOperation(TEXT("ChangeVariableType"));
	Operation->SetStringField(TEXT("VariableName"), TEXT("Value")); Operation->SetStringField(TEXT("VariableType"), TEXT("float")); Operation->SetBoolField(TEXT("bAllowPotentialDataLoss"), true);
	auto Args = RelatedArgs(Blueprint.Get(), Operation);
	Variable.RepNotifyFunc = TEXT("OnRep_Value");
	TestTrue(TEXT("RepNotify function blocks a type change"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestEqual(TEXT("Rejected type preserves default"), Variable.DefaultValue, FString(TEXT("17")));
	Variable.RepNotifyFunc = NAME_None; Variable.PropertyFlags |= CPF_RepNotify;
	TestTrue(TEXT("RepNotify flag blocks a type change"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	Variable.PropertyFlags &= ~CPF_RepNotify; Variable.PropertyFlags |= CPF_Net;
	Operation->SetStringField(TEXT("VariableType"), TEXT("Set<int>"));
	TestTrue(TEXT("Replicated set rejected"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	Operation->SetStringField(TEXT("VariableType"), TEXT("Map<name,int>"));
	TestTrue(TEXT("Replicated map rejected"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestTrue(TEXT("All rejected changes preserve type and GUID"), Variable.VarType == Integer && Variable.VarGuid == OriginalGuid);
	Variable.PropertyFlags &= ~CPF_Net; Operation->SetStringField(TEXT("VariableType"), TEXT("float"));
	if (!TestFalse(TEXT("Owned type change succeeds"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	TestTrue(TEXT("Type change clears the incompatible default"), Blueprint->NewVariables[0].DefaultValue.IsEmpty());
	TestTrue(TEXT("Member GUID retained"), Blueprint->NewVariables[0].VarGuid == OriginalGuid);
	TestTrue(TEXT("Reference GUID retained"), Reference->VariableReference.GetMemberGuid() == OriginalGuid);
	UEdGraphPin* ValuePin = Reference->FindPin(TEXT("Value"));
	if (!TestNotNull(TEXT("Reconstructed variable pin"), ValuePin)) return false;
	FEdGraphPinType Float; FString TypeError; FNexusPinTypeUtils::ParsePinType(TEXT("float"), Float, TypeError);
	TestTrue(TEXT("Graph pin receives the new type"), ValuePin->PinType == Float);
	FKismetEditorUtilities::CompileBlueprint(Blueprint.Get());
	TStrongObjectPtr<UBlueprint> Child(RelatedBlueprint(Blueprint->GeneratedClass));
	ON_SCOPE_EXIT { Child->GetOutermost()->SetDirtyFlag(false); };
	const FEdGraphPinType Before = Blueprint->NewVariables[0].VarType;
	Operation->SetStringField(TEXT("VariableType"), TEXT("int"));
	TestTrue(TEXT("Descendant prevents parent type change"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestTrue(TEXT("Parent and child remain compatible"), Blueprint->NewVariables[0].VarType == Before && Child->ParentClass == Blueprint->GeneratedClass);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRelatedLocalRenameTest, "NexusLink.EditorRelated.LocalRenameReferences", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusRelatedLocalRenameTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UBlueprint> Blueprint(RelatedBlueprint(AActor::StaticClass()));
	ON_SCOPE_EXIT { Blueprint->GetOutermost()->SetDirtyFlag(false); };
	auto Operation = RelatedOperation(TEXT("AddFunction")); Operation->SetStringField(TEXT("FunctionName"), TEXT("Compute"));
	auto Args = RelatedArgs(Blueprint.Get(), Operation); Args->SetBoolField(TEXT("bCompile"), true);
	if (!TestFalse(TEXT("Function fixture"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	Operation->SetStringField(TEXT("Action"), TEXT("AddLocalVariable")); Operation->SetStringField(TEXT("VariableType"), TEXT("int"));
	Operation->SetStringField(TEXT("VariableName"), TEXT("LocalValue"));
	if (!TestFalse(TEXT("Local fixture"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	Operation->SetStringField(TEXT("VariableName"), TEXT("Occupied"));
	if (!TestFalse(TEXT("Collision fixture"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	UEdGraph* Graph = nullptr;
	for (UEdGraph* Candidate : Blueprint->FunctionGraphs) if (Candidate && Candidate->GetName() == TEXT("Compute")) Graph = Candidate;
	if (!TestNotNull(TEXT("Local function graph"), Graph)) return false;
	FBPVariableDescription* Local = FBlueprintEditorUtils::FindLocalVariable(Blueprint.Get(), Graph, TEXT("LocalValue"));
	if (!TestNotNull(TEXT("Original local"), Local)) return false;
	const FGuid Guid = Local->VarGuid;
	UK2Node_VariableGet* Reference = NewObject<UK2Node_VariableGet>(Graph);
	Reference->VariableReference.SetLocalMember(TEXT("LocalValue"), Graph->GetName(), Guid);
	Graph->AddNode(Reference); Reference->CreateNewGuid(); Reference->AllocateDefaultPins();
	Operation->SetStringField(TEXT("Action"), TEXT("RenameLocalVariable")); Operation->SetStringField(TEXT("VariableName"), TEXT("LocalValue")); Operation->SetStringField(TEXT("NewVariableName"), TEXT("Occupied"));
	TestTrue(TEXT("Local name collision rejected"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestEqual(TEXT("Collision preserves graph reference"), Reference->GetVarName(), FName(TEXT("LocalValue")));
	Operation->SetStringField(TEXT("NewVariableName"), TEXT("RenamedLocal"));
	if (!TestFalse(TEXT("Rename succeeds"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	Local = FBlueprintEditorUtils::FindLocalVariable(Blueprint.Get(), Graph, TEXT("RenamedLocal"));
	if (TestNotNull(TEXT("Renamed local exists"), Local)) TestTrue(TEXT("Local GUID retained"), Local->VarGuid == Guid);
	TestNull(TEXT("Old local removed"), FBlueprintEditorUtils::FindLocalVariable(Blueprint.Get(), Graph, TEXT("LocalValue")));
	TestEqual(TEXT("Graph reference renamed"), Reference->GetVarName(), FName(TEXT("RenamedLocal")));
	TestTrue(TEXT("Graph reference GUID retained"), Reference->VariableReference.GetMemberGuid() == Guid);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRelatedScalarTest, "NexusLink.EditorRelated.ScalarPreviewAndLevel", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusRelatedScalarTest::RunTest(const FString& Parameters)
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/Data_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	TStrongObjectPtr<UNexusRelatedDataAsset> Data(NewObject<UNexusRelatedDataAsset>(Package, TEXT("Data"), RF_Public | RF_Standalone));
	ON_SCOPE_EXIT { Package->SetDirtyFlag(false); };
	auto Operation = RelatedOperation(TEXT("Set")); Operation->SetStringField(TEXT("PropertyName"), TEXT("Location.X")); Operation->SetStringField(TEXT("Value"), TEXT("17")); Operation->SetStringField(TEXT("ExpectedValue"), TEXT("0"));
	auto Args = RelatedArgs(Data.Get(), Operation); Args->SetStringField(TEXT("Capability"), TEXT("ManageAssetDataAsset"));
	TestFalse(TEXT("DataAsset preview"), RelatedCall(TEXT("GetAssetEditPreview"), Args).HasErrors());
	TestEqual(TEXT("Preview does not write"), Data->Location.X, static_cast<decltype(Data->Location.X)>(0));
	Args->RemoveField(TEXT("Capability")); Args->SetBoolField(TEXT("bVerify"), true);
	TestFalse(TEXT("DataAsset verified write"), RelatedCall(TEXT("ManageAssetDataAsset"), Args).HasErrors());
	TestEqual(TEXT("DataAsset readback"), Data->Location.X, static_cast<decltype(Data->Location.X)>(17));
	TestTrue(TEXT("Stale precondition rejected"), RelatedCall(TEXT("ManageAssetDataAsset"), Args).HasErrors());
	Data->Values.Add(TEXT("a.b"), 3); FString Previous, Actual, Error;
	TestTrue(TEXT("Dotted map key stays one accessor"), FNexusPropertyUtils::WritePropertyAndEcho(Data.Get(), {TEXT("Values[\"a.b\"]")}, 0, TEXT("8"), Previous, Actual, Error));
	TestEqual(TEXT("Map value changed"), Data->Values[TEXT("a.b")], 8);
	TestFalse(TEXT("Invalid number rejected"), FNexusPropertyUtils::WritePropertyAndEcho(Data.Get(), {TEXT("Location.X")}, 0, TEXT("invalid-number"), Previous, Actual, Error));
	TestTrue(TEXT("Partial struct update"), FNexusPropertyUtils::WritePropertyAndEcho(Data.Get(), {TEXT("Location")}, 0, TEXT("(Y=3)"), Previous, Actual, Error));
	TestEqual(TEXT("Unspecified struct field retained"), Data->Location.X, static_cast<decltype(Data->Location.X)>(17));
	UPackage* WorldPackage = CreatePackage(*(TEXT("/Game/_McpTest/Level_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("RelatedLevel"), WorldPackage);
	ON_SCOPE_EXIT { World->GetOutermost()->SetDirtyFlag(false); World->DestroyWorld(false); };
	AActor* Actor = World->SpawnActor<AActor>();
	Operation = RelatedOperation(TEXT("SetActorProperty")); Operation->SetStringField(TEXT("ActorName"), Actor->GetName()); Operation->SetStringField(TEXT("PropertyPath"), TEXT("InitialLifeSpan")); Operation->SetStringField(TEXT("Value"), TEXT("12")); Operation->SetStringField(TEXT("ExpectedValue"), TEXT("0"));
	Args = RelatedArgs(World, Operation); Args->SetBoolField(TEXT("bVerify"), true);
	TestFalse(TEXT("Level verified write"), RelatedCall(TEXT("ManageAssetLevel"), Args).HasErrors());
	TestEqual(TEXT("Actor value"), Actor->InitialLifeSpan, 12.f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRelatedComponentsTest, "NexusLink.EditorRelated.ComponentBaseline", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusRelatedComponentsTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UBlueprint> Parent(RelatedBlueprint(AActor::StaticClass()));
	ON_SCOPE_EXIT { Parent->GetOutermost()->SetDirtyFlag(false); };
	auto Operation = RelatedOperation(TEXT("AddComponent")); Operation->SetStringField(TEXT("ComponentName"), TEXT("Probe")); Operation->SetStringField(TEXT("ComponentClass"), TEXT("SceneComponent"));
	auto Args = RelatedArgs(Parent.Get(), Operation); Args->SetBoolField(TEXT("bCompile"), true);
	if (!TestFalse(TEXT("Parent component"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	Operation->SetStringField(TEXT("Action"), TEXT("SetComponentProperty")); Operation->SetStringField(TEXT("PropertyPath"), TEXT("RelativeLocation.X")); Operation->SetStringField(TEXT("Value"), TEXT("31"));
	TestFalse(TEXT("Parent value"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TStrongObjectPtr<UBlueprint> Child(RelatedBlueprint(Parent->GeneratedClass));
	ON_SCOPE_EXIT { Child->GetOutermost()->SetDirtyFlag(false); };
	Args->SetStringField(TEXT("AssetPath"), Child->GetPathName()); Operation->SetStringField(TEXT("Value"), TEXT("72")); Operation->SetStringField(TEXT("ExpectedValue"), TEXT("31")); Args->SetBoolField(TEXT("bVerify"), true);
	const auto Override = RelatedCall(TEXT("ManageAssetBlueprint"), Args);
	if (Override.HasErrors()) for (const auto& Entry : Override.Entries) AddInfo(FNexusJsonUtils::SerializeCondensed(Entry->AsObject()));
	TestFalse(TEXT("Child override"), Override.HasErrors());
	auto Read = MakeShared<FJsonObject>(); Read->SetStringField(TEXT("AssetPath"), Child->GetPathName()); Read->SetStringField(TEXT("ComponentName"), TEXT("Probe")); Read->SetStringField(TEXT("Baseline"), TEXT("ParentTemplate")); Read->SetArrayField(TEXT("PropertyPaths"), {MakeShared<FJsonValueString>(TEXT("RelativeLocation.X"))}); Read->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("Component"))});
	const auto Result = RelatedCall(TEXT("GetAssetBlueprint"), Read);
	if (Result.HasErrors()) for (const auto& Entry : Result.Entries) AddInfo(FNexusJsonUtils::SerializeCondensed(Entry->AsObject()));
	if (!TestFalse(TEXT("Parent baseline query"), Result.HasErrors())) return false;
	const auto Property = Result.Entries[0]->AsObject()->GetArrayField(TEXT("Properties"))[0]->AsObject();
	TestTrue(TEXT("Child differs from parent"), Property->GetBoolField(TEXT("bDiffersFromDefault")));
	TestEqual(TEXT("Parent is baseline"), FCString::Atod(*Property->GetStringField(TEXT("DefaultValue"))), 31.0);
	// 关卡实例的继承 SCS 成员在 CDO 上为空，默认值应来自子蓝图的覆盖模板。
	UPackage* WorldPackage = CreatePackage(*(TEXT("/Game/_McpTest/ScsLevel_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("ScsLevel"), WorldPackage);
	GEngine->CreateNewWorldContext(EWorldType::Editor).SetCurrentWorld(World);
	ON_SCOPE_EXIT { WorldPackage->SetDirtyFlag(false); GEngine->DestroyWorldContext(World); World->DestroyWorld(false); };
	AActor* Actor = World->SpawnActor<AActor>(Child->GeneratedClass);
	if (!TestNotNull(TEXT("SCS Actor"), Actor)) return false;
	FObjectPropertyBase* Member = FindFProperty<FObjectPropertyBase>(Actor->GetClass(), TEXT("Probe"));
	if (!TestNotNull(TEXT("SCS 成员"), Member)) return false;
	TestNull(TEXT("Actor CDO 的 SCS 指针为空"), Member->GetObjectPropertyValue_InContainer(Actor->GetClass()->GetDefaultObject()));
	USceneComponent* Instance = Cast<USceneComponent>(Member->GetObjectPropertyValue_InContainer(Actor));
	if (!TestNotNull(TEXT("SCS 实例"), Instance)) return false;
	Instance->SetRelativeLocation(FVector(99, 0, 0));
	auto LevelRead = MakeShared<FJsonObject>();
	LevelRead->SetStringField(TEXT("AssetPath"), World->GetPathName());
	LevelRead->SetStringField(TEXT("ActorName"), Actor->GetName());
	LevelRead->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("ActorProperties"))});
	LevelRead->SetArrayField(TEXT("PropertyPaths"), {MakeShared<FJsonValueString>(TEXT("Probe.RelativeLocation.X"))});
	const auto LevelResult = RelatedCall(TEXT("GetAssetLevel"), LevelRead);
	if (!TestFalse(TEXT("关卡 SCS 默认值比较"), LevelResult.HasErrors())) return false;
	const auto LevelProperty = LevelResult.Entries[0]->AsObject()->GetArrayField(TEXT("Properties"))[0]->AsObject();
	TestEqual(TEXT("使用子蓝图覆盖值"), FCString::Atod(*LevelProperty->GetStringField(TEXT("DefaultValue"))), 72.0);
	TestTrue(TEXT("实例与模板不同"), LevelProperty->GetBoolField(TEXT("bDiffersFromDefault")));
	auto ResetActor = RelatedOperation(TEXT("ResetActorPropertyToDefault"));
	ResetActor->SetStringField(TEXT("ActorName"), Actor->GetName());
	ResetActor->SetStringField(TEXT("PropertyPath"), TEXT("Probe.RelativeLocation.X"));
	if (!TestFalse(TEXT("关卡 SCS 属性重置"), RelatedCall(TEXT("ManageAssetLevel"), RelatedArgs(World, ResetActor)).HasErrors())) return false;
	TestEqual(TEXT("实例恢复为子蓝图模板"), static_cast<double>(Instance->GetRelativeLocation().X), 72.0);
	GEditor->UndoTransaction();
	TestEqual(TEXT("重置可撤销"), static_cast<double>(Instance->GetRelativeLocation().X), 99.0);
	Operation->SetStringField(TEXT("Action"), TEXT("ResetComponentPropertyToDefault")); Operation->RemoveField(TEXT("ExpectedValue")); Args->SetBoolField(TEXT("bVerify"), false);
	TestFalse(TEXT("Reset child to parent template"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	const auto Reset = RelatedCall(TEXT("GetAssetBlueprint"), Read);
	if (!TestFalse(TEXT("Read reset value"), Reset.HasErrors())) return false;
	const auto ResetProperty = Reset.Entries[0]->AsObject()->GetArrayField(TEXT("Properties"))[0]->AsObject();
	TestEqual(TEXT("Reset writes actual parent value"), FCString::Atod(*ResetProperty->GetStringField(TEXT("Value"))), 31.0);
	TestFalse(TEXT("Reset removes the difference"), ResetProperty->GetBoolField(TEXT("bDiffersFromDefault")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRelatedCompileTest, "NexusLink.EditorRelated.CompileFailureNeverSaves", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusRelatedCompileTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UBlueprint> Blueprint(RelatedBlueprint(AActor::StaticClass()));
	auto Operation = RelatedOperation(TEXT("AddFunction")); Operation->SetStringField(TEXT("FunctionName"), TEXT("InvalidLatentFunction"));
	auto Args = RelatedArgs(Blueprint.Get(), Operation); Args->SetBoolField(TEXT("bCompile"), true); Args->SetBoolField(TEXT("bSaveToDisk"), true);
	if (!TestFalse(TEXT("Save valid fixture"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	const FString PackagePath = Blueprint->GetOutermost()->GetName();
	const FString Filename = FPackageName::LongPackageNameToFilename(PackagePath, FPackageName::GetAssetPackageExtension());
	ON_SCOPE_EXIT { Blueprint->GetOutermost()->SetDirtyFlag(false); IFileManager::Get().Delete(*Filename); };
	TArray<uint8> Before; FFileHelper::LoadFileToArray(Before, *Filename);
	UEdGraph* Graph = nullptr;
	for (UEdGraph* Candidate : Blueprint->FunctionGraphs) if (Candidate && Candidate->GetName() == TEXT("InvalidLatentFunction")) Graph = Candidate;
	if (!TestNotNull(TEXT("Invalid function fixture"), Graph)) return false;
	UK2Node_CallFunction* Delay = NewObject<UK2Node_CallFunction>(Graph);
	Graph->AddNode(Delay); Delay->CreateNewGuid();
	Delay->SetFromFunction(UKismetSystemLibrary::StaticClass()->FindFunctionByName(TEXT("Delay"))); Delay->AllocateDefaultPins();
	for (UEdGraphNode* Node : Graph->Nodes) if (UK2Node_FunctionEntry* Entry = Cast<UK2Node_FunctionEntry>(Node))
		if (UEdGraphPin* Then = Entry->FindPin(UEdGraphSchema_K2::PN_Then)) Then->MakeLinkTo(Delay->GetExecPin());
	Blueprint->MarkPackageDirty();
	auto CompileArgs = MakeShared<FJsonObject>(); CompileArgs->SetStringField(TEXT("AssetPath"), Blueprint->GetPathName()); CompileArgs->SetBoolField(TEXT("bSaveToDisk"), true);
	const auto Result = RelatedCall(TEXT("CompileBlueprint"), CompileArgs);
	if (!TestTrue(TEXT("Compiler error returned"), Result.HasErrors())) return false;
	const auto Entry = Result.Entries[0]->AsObject();
	TestFalse(TEXT("Failed compile is not saved"), Entry->GetBoolField(TEXT("bSaved")));
	TestTrue(TEXT("Structured compiler messages"), Entry->GetArrayField(TEXT("CompilerMessages")).Num() > 0);
	TestFalse(TEXT("Creation helper also rejects failed compile"), FNexusAssetEditorUtils::CompileAndSaveBlueprint(Blueprint->GetOutermost(), Blueprint.Get(), PackagePath));
	TArray<uint8> After; FFileHelper::LoadFileToArray(After, *Filename);
	TestTrue(TEXT("Existing package bytes unchanged"), Before.Num() > 0 && Before == After);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRelatedExportTest, "NexusLink.EditorRelated.ExportPreflight", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusRelatedExportTest::RunTest(const FString& Parameters)
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/Export_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	TStrongObjectPtr<UNexusRelatedDataAsset> Asset(NewObject<UNexusRelatedDataAsset>(Package, TEXT("Export"), RF_Public | RF_Standalone));
	ON_SCOPE_EXIT { Package->SetDirtyFlag(false); };
	auto Args = MakeShared<FJsonObject>(); Args->SetStringField(TEXT("AssetPath"), Asset->GetPathName());
	TestFalse(TEXT("Export formats query"), RelatedCall(TEXT("GetAssetExportOptions"), Args).HasErrors());
	const FString Directory = FPaths::ProjectSavedDir() / TEXT("RelatedExports") / FGuid::NewGuid().ToString(EGuidFormats::Digits);
	const FString Output = Directory / TEXT("test.t3d"); Args->SetStringField(TEXT("OutputPath"), Output); Args->SetBoolField(TEXT("bValidateOnly"), true);
	TestFalse(TEXT("Dry run"), RelatedCall(TEXT("ExportAsset"), Args).HasErrors());
	TestFalse(TEXT("Dry run creates no directory"), IFileManager::Get().DirectoryExists(*Directory));
	IFileManager::Get().MakeDirectory(*Directory, true); FFileHelper::SaveStringToFile(TEXT("existing"), *Output);
	const FString UniqueOutput = Directory / TEXT("test_1.t3d");
	ON_SCOPE_EXIT { IFileManager::Get().Delete(*Output); IFileManager::Get().Delete(*UniqueOutput); IFileManager::Get().DeleteDirectory(*Directory); };
	Args->SetStringField(TEXT("ConflictPolicy"), TEXT("Fail")); TestTrue(TEXT("Fail policy protects file"), RelatedCall(TEXT("ExportAsset"), Args).HasErrors());
	Args->SetStringField(TEXT("ConflictPolicy"), TEXT("Unique")); const auto Unique = RelatedCall(TEXT("ExportAsset"), Args);
	TestFalse(TEXT("Unique policy plans another path"), Unique.HasErrors());
	if (!Unique.HasErrors()) TestTrue(TEXT("Unique suffix"), Unique.Entries[0]->AsObject()->GetStringField(TEXT("OutputPath")).EndsWith(TEXT("test_1.t3d")));
	Args->SetBoolField(TEXT("bValidateOnly"), false);
	Args->SetStringField(TEXT("ConflictPolicy"), TEXT("Fail"));
	TestTrue(TEXT("Real Fail policy rejects overwrite"), RelatedCall(TEXT("ExportAsset"), Args).HasErrors());
	FString Original; FFileHelper::LoadFileToString(Original, *Output);
	TestEqual(TEXT("Rejected export keeps original bytes"), Original, FString(TEXT("existing")));
	Args->SetStringField(TEXT("ConflictPolicy"), TEXT("Unique"));
	const auto Written = RelatedCall(TEXT("ExportAsset"), Args);
	if (!TestFalse(TEXT("Unique actually exports"), Written.HasErrors())) return false;
	TestTrue(TEXT("Unique reports a write"), Written.Entries[0]->AsObject()->GetBoolField(TEXT("bWritten")));
	FString Exported; FFileHelper::LoadFileToString(Exported, *UniqueOutput);
	TestTrue(TEXT("Unique contains serialized asset"), Exported.Contains(TEXT("Begin Object")) && Exported.Contains(TEXT("NexusRelatedDataAsset")));
	FFileHelper::LoadFileToString(Original, *Output);
	TestEqual(TEXT("Unique preserves original"), Original, FString(TEXT("existing")));
	Args->SetStringField(TEXT("ConflictPolicy"), TEXT("Replace"));
	TestFalse(TEXT("Replace actually exports"), RelatedCall(TEXT("ExportAsset"), Args).HasErrors());
	FFileHelper::LoadFileToString(Original, *Output);
	TestEqual(TEXT("Replace writes same serialized content"), Original, Exported);
	Args->SetStringField(TEXT("AssetPath"), TEXT("/Game/_McpTest/MissingExportAsset"));
	TestTrue(TEXT("Missing asset rejects replacement"), RelatedCall(TEXT("ExportAsset"), Args).HasErrors());
	FString AfterFailure; FFileHelper::LoadFileToString(AfterFailure, *Output);
	TestEqual(TEXT("Failure preserves exported file"), AfterFailure, Original);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRelatedSpecializedTest, "NexusLink.EditorRelated.SpecializedReparent", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusRelatedSpecializedTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UBlueprint> Widget(RelatedBlueprint(UUserWidget::StaticClass(), UWidgetBlueprint::StaticClass(), UWidgetBlueprintGeneratedClass::StaticClass()));
	TStrongObjectPtr<UBlueprint> WidgetParent(RelatedBlueprint(UUserWidget::StaticClass(), UWidgetBlueprint::StaticClass(), UWidgetBlueprintGeneratedClass::StaticClass()));
	ON_SCOPE_EXIT { Widget->GetOutermost()->SetDirtyFlag(false); WidgetParent->GetOutermost()->SetDirtyFlag(false); };
	auto Operation = RelatedOperation(TEXT("Reparent")); Operation->SetStringField(TEXT("ParentClass"), WidgetParent->GetPathName());
	auto Args = RelatedArgs(Widget.Get(), Operation); Args->SetStringField(TEXT("Capability"), TEXT("ManageAssetBlueprint"));
	TestFalse(TEXT("Widget reparent preview"), RelatedCall(TEXT("GetAssetEditPreview"), Args).HasErrors());
	TestTrue(TEXT("Preview preserves parent"), Widget->ParentClass == UUserWidget::StaticClass());
	Args->RemoveField(TEXT("Capability")); Args->SetBoolField(TEXT("bCompile"), true);
	TestFalse(TEXT("Widget reparent"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestTrue(TEXT("Widget asset type retained"), Widget->GetClass() == UWidgetBlueprint::StaticClass());
	TStrongObjectPtr<UBlueprint> Animation(RelatedBlueprint(UAnimInstance::StaticClass(), UAnimBlueprint::StaticClass(), UAnimBlueprintGeneratedClass::StaticClass()));
	TStrongObjectPtr<UBlueprint> AnimationParent(RelatedBlueprint(UAnimInstance::StaticClass(), UAnimBlueprint::StaticClass(), UAnimBlueprintGeneratedClass::StaticClass()));
	ON_SCOPE_EXIT { Animation->GetOutermost()->SetDirtyFlag(false); AnimationParent->GetOutermost()->SetDirtyFlag(false); };
	Operation->SetStringField(TEXT("ParentClass"), AnimationParent->GetPathName()); Args->SetStringField(TEXT("AssetPath"), Animation->GetPathName()); Args->SetBoolField(TEXT("bCompile"), false);
	TestFalse(TEXT("Animation reparent preserves specialized asset"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
#if WITH_GAS
	UClass* Ability = FNexusAssetUtils::FindClassWithUPrefix(TEXT("GameplayAbility"));
	UClass* AbilityBlueprint = FNexusAssetUtils::FindClassWithUPrefix(TEXT("GameplayAbilityBlueprint"));
	if (TestNotNull(TEXT("Ability blueprint class"), AbilityBlueprint) && TestNotNull(TEXT("Ability class"), Ability))
	{
		TStrongObjectPtr<UBlueprint> Asset(RelatedBlueprint(Ability, AbilityBlueprint));
		TStrongObjectPtr<UBlueprint> Parent(RelatedBlueprint(Ability, AbilityBlueprint));
		ON_SCOPE_EXIT { Asset->GetOutermost()->SetDirtyFlag(false); Parent->GetOutermost()->SetDirtyFlag(false); };
		Operation->SetStringField(TEXT("ParentClass"), Parent->GetPathName()); Args->SetStringField(TEXT("AssetPath"), Asset->GetPathName()); Args->SetBoolField(TEXT("bCompile"), true);
		TestFalse(TEXT("Native GameplayAbilityBlueprint reparent"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	}
#endif
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRelatedReparentGuardsTest, "NexusLink.EditorRelated.ReparentGuards", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusRelatedReparentGuardsTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UBlueprint> Widget(RelatedBlueprint(UUserWidget::StaticClass(), UWidgetBlueprint::StaticClass(), UWidgetBlueprintGeneratedClass::StaticClass()));
	TStrongObjectPtr<UBlueprint> Animation(RelatedBlueprint(UAnimInstance::StaticClass(), UAnimBlueprint::StaticClass(), UAnimBlueprintGeneratedClass::StaticClass()));
	TStrongObjectPtr<UBlueprint> AnimationParent(RelatedBlueprint(UAnimInstance::StaticClass(), UAnimBlueprint::StaticClass(), UAnimBlueprintGeneratedClass::StaticClass()));
	TStrongObjectPtr<UBlueprint> Asset(RelatedBlueprint(AActor::StaticClass()));
	TStrongObjectPtr<UBlueprint> Parent(RelatedBlueprint(AActor::StaticClass()));
	ON_SCOPE_EXIT { for (UBlueprint* Blueprint : {Widget.Get(), Animation.Get(), AnimationParent.Get(), Asset.Get(), Parent.Get()}) Blueprint->GetOutermost()->SetDirtyFlag(false); };
	auto Operation = RelatedOperation(TEXT("Reparent")); Operation->SetStringField(TEXT("ParentClass"), TEXT("Actor"));
	auto Args = RelatedArgs(Widget.Get(), Operation);
	TestTrue(TEXT("Widget rejects Actor parent"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestTrue(TEXT("Widget rejection leaves parent intact"), Widget->ParentClass == UUserWidget::StaticClass());
	Args->SetStringField(TEXT("AssetPath"), Animation->GetPathName());
	TestTrue(TEXT("Animation rejects Actor parent"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	PRAGMA_DISABLE_DEPRECATION_WARNINGS
	CastChecked<UAnimBlueprint>(Animation.Get())->TargetSkeleton = NewObject<USkeleton>(Animation.Get());
	CastChecked<UAnimBlueprint>(AnimationParent.Get())->TargetSkeleton = NewObject<USkeleton>(AnimationParent.Get());
	PRAGMA_ENABLE_DEPRECATION_WARNINGS
	Operation->SetStringField(TEXT("ParentClass"), AnimationParent->GetPathName());
	const auto Incompatible = RelatedCall(TEXT("ManageAssetBlueprint"), Args);
	TestTrue(TEXT("Different animation skeleton rejected"), Incompatible.HasErrors());
	TestTrue(TEXT("Animation rejection leaves parent intact"), Animation->ParentClass == UAnimInstance::StaticClass());
	FEdGraphPinType Integer; Integer.PinCategory = UEdGraphSchema_K2::PC_Int;
	FBlueprintEditorUtils::AddMemberVariable(Asset.Get(), TEXT("Collision"), Integer, TEXT("17"));
	FBlueprintEditorUtils::AddMemberVariable(Parent.Get(), TEXT("Collision"), Integer, TEXT("42"));
	FKismetEditorUtilities::CompileBlueprint(Parent.Get());
	const FGuid Guid = Asset->NewVariables[0].VarGuid;
	Args->SetStringField(TEXT("AssetPath"), Asset->GetPathName()); Operation->SetStringField(TEXT("ParentClass"), Parent->GetPathName());
	TestTrue(TEXT("Inherited member conflict rejected"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestTrue(TEXT("Conflict preserves parent and owned member"), Asset->ParentClass == AActor::StaticClass() && Asset->NewVariables[0].VarGuid == Guid && Asset->NewVariables[0].DefaultValue == TEXT("17"));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRelatedStructMetadataTest, "NexusLink.EditorRelated.StructTypeMetadata", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusRelatedStructMetadataTest::RunTest(const FString& Parameters)
{
	const FString Path = TEXT("/Game/_McpTest/StructMetadata_") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
	UUserDefinedStruct* Struct = FStructureEditorUtils::CreateUserDefinedStruct(CreatePackage(*Path), *FPackageName::GetShortName(Path), RF_Public | RF_Standalone);
	if (!TestNotNull(TEXT("Struct fixture"), Struct)) return false;
	ON_SCOPE_EXIT { Struct->GetOutermost()->SetDirtyFlag(false); };
	FEdGraphPinType MapType;
	FString Error;
	if (!TestTrue(TEXT("Map type fixture"), FNexusPinTypeUtils::ParsePinType(TEXT("Map<name,vector>"), MapType, Error))) return false;
	if (!TestTrue(TEXT("Add struct map field"), FStructureEditorUtils::AddVariable(Struct, MapType))) return false;
	auto Args = MakeShared<FJsonObject>(); Args->SetStringField(TEXT("AssetPath"), Struct->GetPathName());
	const auto Result = RelatedCall(TEXT("GetAssetStruct"), Args);
	if (!TestFalse(TEXT("Read struct fields"), Result.HasErrors())) return false;
	const auto Fields = Result.Entries[0]->AsObject()->GetArrayField(TEXT("Fields"));
	TestEqual(TEXT("Scalar and map fields returned"), Fields.Num(), 2);
	bool bFoundMap = false;
	for (const auto& Field : Fields)
	{
		const auto Metadata = Field->AsObject();
		if (!TestTrue(TEXT("Type metadata remains alive through iteration"), Metadata->HasField(TEXT("ContainerType")) && Metadata->HasField(TEXT("CanonicalType")))) continue;
		if (Metadata->GetStringField(TEXT("ContainerType")) == TEXT("Map"))
		{
			bFoundMap = true;
			TestEqual(TEXT("Map key retained"), Metadata->GetStringField(TEXT("KeyType")), FString(TEXT("name")));
			TestTrue(TEXT("Map value path retained"), Metadata->GetStringField(TEXT("ValueTypeObjectPath")).EndsWith(TEXT(".Vector")));
		}
	}
	TestTrue(TEXT("Map metadata returned"), bFoundMap);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRelatedNumericTextTest, "NexusLink.EditorRelated.NumericTextCompatibility", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusRelatedNumericTextTest::RunTest(const FString& Parameters)
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/NumericText_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	TStrongObjectPtr<UNexusRelatedDataAsset> Data(NewObject<UNexusRelatedDataAsset>(Package, TEXT("Data"), RF_Public | RF_Standalone));
	ON_SCOPE_EXIT { Package->SetDirtyFlag(false); };
	FString Previous, Actual, Error;
	for (const TCHAR* Text : {TEXT("1e3"), TEXT("-2.5E-2"), TEXT("+3.0e+2"), TEXT("0e0"), TEXT("2.5f")})
	{
		TestTrue(TEXT("Complete numeric text accepted"), FNexusPropertyUtils::WritePropertyAndEcho(Data.Get(), {TEXT("Location.X")}, 0, Text, Previous, Actual, Error));
		TestTrue(TEXT("Scientific value converted correctly"), FMath::Abs(static_cast<double>(Data->Location.X) - FCString::Atod(Text)) < 0.00001);
	}
	Data->Location.X = 17;
	for (const TCHAR* Text : {TEXT("."), TEXT("1e"), TEXT("1e3junk"), TEXT("nan"), TEXT("1e9999"), TEXT("--1")})
	{
		TestFalse(TEXT("Invalid numeric text rejected"), FNexusPropertyUtils::WritePropertyAndEcho(Data.Get(), {TEXT("Location.X")}, 0, Text, Previous, Actual, Error));
		TestEqual(TEXT("Invalid input never writes"), static_cast<double>(Data->Location.X), 17.0);
	}
	FProperty* FloatProperty = FindFProperty<FProperty>(AActor::StaticClass(), TEXT("InitialLifeSpan"));
	if (!TestNotNull(TEXT("Float range fixture"), FloatProperty)) return false;
	FDefaultConstructedPropertyElement Storage(FloatProperty);
	TestFalse(TEXT("Finite double outside float range rejected"), FNexusPropertyUtils::ParsePropertyValue(FloatProperty, TEXT("1e40"), Storage.GetObjAddress(), nullptr, Error));
	auto Operation = RelatedOperation(TEXT("Set")); Operation->SetStringField(TEXT("PropertyName"), TEXT("Location.X"));
	Operation->SetStringField(TEXT("Value"), TEXT("1e3")); Operation->SetStringField(TEXT("ExpectedValue"), TEXT("1.7e1"));
	auto Args = RelatedArgs(Data.Get(), Operation); Args->SetStringField(TEXT("Capability"), TEXT("ManageAssetDataAsset"));
	TestFalse(TEXT("Scientific preview and precondition"), RelatedCall(TEXT("GetAssetEditPreview"), Args).HasErrors());
	TestEqual(TEXT("Preview stays read-only"), static_cast<double>(Data->Location.X), 17.0);
	Args->RemoveField(TEXT("Capability")); Args->SetBoolField(TEXT("bVerify"), true);
	TestFalse(TEXT("Scientific verified write"), RelatedCall(TEXT("ManageAssetDataAsset"), Args).HasErrors());
	TestEqual(TEXT("Verified exponent value"), static_cast<double>(Data->Location.X), 1000.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRelatedInheritedUndoTest, "NexusLink.EditorRelated.InheritedComponentUndo", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusRelatedInheritedUndoTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UBlueprint> Parent(RelatedBlueprint(AActor::StaticClass()));
	ON_SCOPE_EXIT { Parent->GetOutermost()->SetDirtyFlag(false); };
	auto Operation = RelatedOperation(TEXT("AddComponent")); Operation->SetStringField(TEXT("ComponentName"), TEXT("Probe")); Operation->SetStringField(TEXT("ComponentClass"), TEXT("SceneComponent"));
	if (!TestFalse(TEXT("Add parent component"), RelatedCall(TEXT("ManageAssetBlueprint"), RelatedArgs(Parent.Get(), Operation)).HasErrors())) return false;
	FKismetEditorUtilities::CompileBlueprint(Parent.Get());
	TStrongObjectPtr<UBlueprint> Child(RelatedBlueprint(Parent->GeneratedClass));
	ON_SCOPE_EXIT { Child->GetOutermost()->SetDirtyFlag(false); };
	USCS_Node* Node = Parent->SimpleConstructionScript->FindSCSNode(TEXT("Probe"));
	USceneComponent* Override = Cast<USceneComponent>(Child->GetInheritableComponentHandler(true)->CreateOverridenComponentTemplate(FComponentKey(Node)));
	if (!TestNotNull(TEXT("Inherited override fixture"), Override)) return false;
	Override->SetRelativeLocation(FVector(10,0,0)); Override->ClearFlags(RF_Transactional);
	Operation = RelatedOperation(TEXT("SetComponentProperty")); Operation->SetStringField(TEXT("ComponentName"), TEXT("Probe")); Operation->SetStringField(TEXT("PropertyPath"), TEXT("RelativeLocation.X")); Operation->SetStringField(TEXT("Value"), TEXT("20"));
	auto Args = RelatedArgs(Child.Get(), Operation);
	if (!TestFalse(TEXT("Default unverified inherited write"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	TestEqual(TEXT("Inherited value written"), static_cast<double>(Override->GetRelativeLocation().X), 20.0);
	GEditor->UndoTransaction();
	TestEqual(TEXT("Undo restores inherited value"), static_cast<double>(Override->GetRelativeLocation().X), 10.0);
	Override->SetRelativeLocation(FVector(30,0,0)); Override->ClearFlags(RF_Transactional);
	Operation->SetStringField(TEXT("Action"), TEXT("ResetComponentPropertyToDefault"));
	if (!TestFalse(TEXT("Reset inherited value"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	TestEqual(TEXT("Parent default restored"), static_cast<double>(Override->GetRelativeLocation().X), 0.0);
	GEditor->UndoTransaction();
	TestEqual(TEXT("Undo restores pre-reset value"), static_cast<double>(Override->GetRelativeLocation().X), 30.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRelatedResetBoundaryTest, "NexusLink.EditorRelated.ComponentResetBoundaries", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusRelatedResetBoundaryTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UBlueprint> Parent(RelatedBlueprint(AActor::StaticClass()));
	ON_SCOPE_EXIT { Parent->GetOutermost()->SetDirtyFlag(false); };
	auto Operation = RelatedOperation(TEXT("AddComponent")); Operation->SetStringField(TEXT("ComponentName"), TEXT("Probe")); Operation->SetStringField(TEXT("ComponentClass"), TEXT("StaticMeshComponent"));
	if (!TestFalse(TEXT("Add parent component"), RelatedCall(TEXT("ManageAssetBlueprint"), RelatedArgs(Parent.Get(), Operation)).HasErrors())) return false;
	USCS_Node* Node = Parent->SimpleConstructionScript->FindSCSNode(TEXT("Probe"));
	UStaticMeshComponent* ParentComponent = CastChecked<UStaticMeshComponent>(Node->ComponentTemplate);
	TStrongObjectPtr<UStaticMesh> ParentMesh(NewObject<UStaticMesh>()), ChildMesh(NewObject<UStaticMesh>());
	FIntProperty* Resolution = FindFProperty<FIntProperty>(UStaticMesh::StaticClass(), TEXT("LightMapResolution"));
	if (!TestNotNull(TEXT("Mesh resolution fixture"), Resolution)) return false;
	Resolution->SetPropertyValue_InContainer(ParentMesh.Get(), 64); Resolution->SetPropertyValue_InContainer(ChildMesh.Get(), 128);
	ParentComponent->SetStaticMesh(ParentMesh.Get());
	FKismetEditorUtilities::CompileBlueprint(Parent.Get());
	TStrongObjectPtr<UBlueprint> Child(RelatedBlueprint(Parent->GeneratedClass));
	ON_SCOPE_EXIT { Child->GetOutermost()->SetDirtyFlag(false); };
	UStaticMeshComponent* Override = CastChecked<UStaticMeshComponent>(Child->GetInheritableComponentHandler(true)->CreateOverridenComponentTemplate(FComponentKey(Node)));
	Override->SetStaticMesh(ChildMesh.Get());
	Operation = RelatedOperation(TEXT("ResetComponentPropertyToDefault")); Operation->SetStringField(TEXT("ComponentName"), TEXT("Probe")); Operation->SetStringField(TEXT("PropertyPath"), TEXT("StaticMesh.LightMapResolution"));
	auto Args = RelatedArgs(Child.Get(), Operation);
	TestTrue(TEXT("External baseline traversal rejected"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestEqual(TEXT("External target stays unchanged"), Resolution->GetPropertyValue_InContainer(ChildMesh.Get()), 128);
	UStaticMesh* OwnedParentMesh = NewObject<UStaticMesh>(ParentComponent);
	Resolution->SetPropertyValue_InContainer(OwnedParentMesh, 64); ParentComponent->SetStaticMesh(OwnedParentMesh);
	TestTrue(TEXT("External target traversal rejected"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestEqual(TEXT("External target still unchanged"), Resolution->GetPropertyValue_InContainer(ChildMesh.Get()), 128);
	UStaticMesh* OwnedChildMesh = NewObject<UStaticMesh>(Override);
	Resolution->SetPropertyValue_InContainer(OwnedChildMesh, 128); Override->SetStaticMesh(OwnedChildMesh);
	TestFalse(TEXT("Owned subobject reset allowed"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestEqual(TEXT("Owned subobject value restored"), Resolution->GetPropertyValue_InContainer(OwnedChildMesh), 64);
	GEditor->UndoTransaction();
	TestEqual(TEXT("Undo snapshots the actual owned object"), Resolution->GetPropertyValue_InContainer(OwnedChildMesh), 128);
	return true;
}
#endif
