// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"
#if WITH_EDITOR
#include "NexusCapabilityRegistry.h"
#include "NexusEditorServices.h"
#include "Utils/NexusAssetUtils.h"
#include "Utils/NexusAnimGraphUtils.h"
#include "Utils/NexusVersionCompat.h"
#include "Utils/NexusJsonUtils.h"
#include "Animation/Skeleton.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimBlueprint.h"
#include "Animation/AnimBlueprintGeneratedClass.h"
#include "Animation/AnimInstance.h"
#include "Animation/BlendSpace1D.h"
#include "ReferenceSkeleton.h"
#if NX_UE_HAS_ANIM_DATA_CONTROLLER
#include "Animation/AnimData/IAnimationDataController.h"
#endif
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/World.h"
#include "Engine/Level.h"
#include "EdGraph/EdGraph.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Character.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/ScopeExit.h"
#include "Misc/PackageName.h"
#include "HAL/FileManager.h"
#include "NavMesh/RecastNavMeshDataChunk.h"
#include "Editor.h"

static FCapabilityResult FeedbackNov12Call(const TCHAR* Name, const TSharedPtr<FJsonObject>& Args)
{
	const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(Name);
	return Record ? Record->Instance->Run(Args) : FCapabilityResult::MakeFatal(TEXT("Missing capability"));
}

static TSharedPtr<FJsonObject> FeedbackNov12Args(UObject* Asset, const TCHAR* Action = nullptr)
{
	auto Args = MakeShared<FJsonObject>(); Args->SetStringField(TEXT("AssetPath"), Asset->GetPathName());
	if (Action)
	{
		auto Op = MakeShared<FJsonObject>(); Op->SetStringField(TEXT("Action"), Action);
		Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Op)});
	}
	return Args;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusFeedbackAnimation12Test, "NexusLink.FeedbackNov12.Animation", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusFeedbackAnimation12Test::RunTest(const FString& Parameters)
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/Animation12_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	ON_SCOPE_EXIT { Package->SetDirtyFlag(false); };
	USkeleton* Skeleton = NewObject<USkeleton>(Package, TEXT("Skeleton"), RF_Public | RF_Standalone);
	{
		FReferenceSkeletonModifier Modifier(const_cast<FReferenceSkeleton&>(Skeleton->GetReferenceSkeleton()), Skeleton);
		Modifier.Add(FMeshBoneInfo(TEXT("root"), TEXT("root"), INDEX_NONE), FTransform::Identity);
	}
	UAnimSequence* Sequence = NewObject<UAnimSequence>(Package, TEXT("Sequence"), RF_Public | RF_Standalone);
	Sequence->SetSkeleton(Skeleton);
#if NX_UE_HAS_ANIM_DATA_CONTROLLER
	auto& Controller = Sequence->GetController();
#if NX_UE_HAS_ANIM_CONTROLLER_MODEL_INIT
	Controller.InitializeModel(); Controller.SetFrameRate(FFrameRate(30, 1)); Controller.SetNumberOfFrames(FFrameNumber(1)); Controller.AddBoneCurve(TEXT("root"));
#else
	Controller.SetFrameRate(FFrameRate(30, 1)); Controller.SetPlayLength(1.f / 30.f); Controller.AddBoneTrack(TEXT("root"));
#endif
	Controller.SetBoneTrackKeys(TEXT("root"), {FVector3f(12,0,0), FVector3f(12,0,0)}, {FQuat4f::Identity, FQuat4f::Identity}, {FVector3f::OneVector, FVector3f::OneVector});
#else
	FRawAnimSequenceTrack Track; Track.PosKeys.Add(FVector(12,0,0)); Track.RotKeys.Add(FQuat::Identity); Track.ScaleKeys.Add(FVector::OneVector);
	Sequence->AddNewRawTrack(TEXT("root"), &Track); Sequence->SetRawNumberOfFrame(1); Sequence->SequenceLength = 1.f / 30.f; Sequence->PostProcessSequence();
#endif
	auto Args = FeedbackNov12Args(Sequence);
	Args->SetArrayField(TEXT("BoneNames"), {MakeShared<FJsonValueString>(TEXT("root"))});
	Args->SetArrayField(TEXT("SampleTimes"), {MakeShared<FJsonValueNumber>(0)});
	auto Read = FeedbackNov12Call(TEXT("GetAssetAnimSequence"), Args);
	if (!TestFalse(TEXT("Bone sampling works on legacy engines"), Read.HasErrors())) return false;
	TestEqual(TEXT("Local pose uses animation track"), Read.Entries[0]->AsObject()->GetArrayField(TEXT("BoneSamples"))[0]->AsObject()->GetArrayField(TEXT("Translation"))[0]->AsNumber(), 12.0);
	UBlendSpace1D* Blend = NewObject<UBlendSpace1D>(Package, TEXT("Blend"), RF_Public | RF_Standalone); Blend->SetSkeleton(Skeleton);
	Args = FeedbackNov12Args(Blend, TEXT("SetAxis"));
	auto Axis = Args->GetArrayField(TEXT("Operations"))[0]->AsObject(); Axis->SetNumberField(TEXT("Min"), 0); Axis->SetNumberField(TEXT("Max"), 100); Axis->SetNumberField(TEXT("GridNum"), 4);
	if (!TestFalse(TEXT("1D axis edit"), FeedbackNov12Call(TEXT("ManageAssetBlendSpace"), Args).HasErrors())) return false;
	Args = FeedbackNov12Args(Blend, TEXT("AddSample"));
	auto Sample = Args->GetArrayField(TEXT("Operations"))[0]->AsObject(); Sample->SetStringField(TEXT("AnimationPath"), Sequence->GetPathName()); Sample->SetNumberField(TEXT("X"), 0);
	if (!TestFalse(TEXT("1D add sample"), FeedbackNov12Call(TEXT("ManageAssetBlendSpace"), Args).HasErrors())) return false;
	Sample->SetNumberField(TEXT("X"), 100);
	UAnimSequence* SecondSequence = DuplicateObject<UAnimSequence>(Sequence, Package, TEXT("SecondSequence"));
	Sample->SetStringField(TEXT("AnimationPath"), SecondSequence->GetPathName());
	if (!TestFalse(TEXT("1D second sample"), FeedbackNov12Call(TEXT("ManageAssetBlendSpace"), Args).HasErrors())) return false;
	TestTrue(TEXT("Duplicate sample rejected"), FeedbackNov12Call(TEXT("ManageAssetBlendSpace"), Args).HasErrors());
	TArray<FBlendSampleData> Weights;
#if NX_UE_HAS_BLEND_SPACE_BASE
	Blend->GetSamplesFromBlendInput(FVector(50,0,0), Weights);
#else
	int32 CachedIndex = 0;
	Blend->GetSamplesFromBlendInput(FVector(50,0,0), Weights, CachedIndex, false);
#endif
	TestEqual(TEXT("Interpolation grid usable without opening Persona"), Weights.Num(), 2);
	if (Weights.Num() == 2) TestTrue(TEXT("Midpoint weights"), FMath::IsNearlyEqual(Weights[0].TotalWeight, .5f) && FMath::IsNearlyEqual(Weights[1].TotalWeight, .5f));
	Read = FeedbackNov12Call(TEXT("GetAssetBlendSpace"), FeedbackNov12Args(Blend));
	if (!TestFalse(TEXT("1D getter resolves exact object"), Read.HasErrors())) return false;
	TestEqual(TEXT("1D exposes only one axis"), Read.Entries[0]->AsObject()->GetArrayField(TEXT("Axes")).Num(), 1);
	Axis->SetNumberField(TEXT("AxisIndex"), 1); Args = FeedbackNov12Args(Blend); Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Axis)});
	TestTrue(TEXT("1D rejects second axis"), FeedbackNov12Call(TEXT("ManageAssetBlendSpace"), Args).HasErrors());
	UAnimBlueprint* Blueprint = CastChecked<UAnimBlueprint>(FKismetEditorUtilities::CreateBlueprint(UAnimInstance::StaticClass(), Package, TEXT("AnimBP"), BPTYPE_Normal, UAnimBlueprint::StaticClass(), UAnimBlueprintGeneratedClass::StaticClass()));
	Blueprint->TargetSkeleton = Skeleton;
	Args = FeedbackNov12Args(Blueprint, TEXT("AddStateMachine"));
	Args->GetArrayField(TEXT("Operations"))[0]->AsObject()->SetStringField(TEXT("StateMachineName"), TEXT("Locomotion"));
	if (!TestFalse(TEXT("State machine fixture"), FeedbackNov12Call(TEXT("ManageAssetAnimBlueprint"), Args).HasErrors())) return false;
	Args = FeedbackNov12Args(Blueprint, TEXT("AddState"));
	auto State = Args->GetArrayField(TEXT("Operations"))[0]->AsObject(); State->SetStringField(TEXT("StateMachineName"), TEXT("Locomotion")); State->SetStringField(TEXT("StateName"), TEXT("Move"));
	const auto CreatedState = FeedbackNov12Call(TEXT("ManageAssetAnimBlueprint"), Args);
	if (!TestFalse(TEXT("Nested state fixture"), CreatedState.HasErrors())) return false;
	const FString StateGraphName = CreatedState.Entries[0]->AsObject()->GetStringField(TEXT("StateName"));
	UEdGraph* Graph = FNexusAnimGraphUtils::FindAnimGraph(Blueprint, StateGraphName);
	if (!Graph)
	{
		AddInfo(TEXT("Requested state graph: ") + StateGraphName);
		TArray<UEdGraph*> Graphs; Blueprint->GetAllGraphs(Graphs);
		for (UEdGraph* Candidate : Graphs) if (Candidate) AddInfo(Candidate->GetPathName());
	}
	if (!TestNotNull(TEXT("Find nested state graph"), Graph)) return false;
	Args = FeedbackNov12Args(Blueprint, TEXT("AddNode"));
	auto Node = Args->GetArrayField(TEXT("Operations"))[0]->AsObject(); Node->SetStringField(TEXT("GraphName"), Graph->GetPathName()); Node->SetStringField(TEXT("NodeClass"), TEXT("SequencePlayer")); Node->SetStringField(TEXT("SequencePath"), Sequence->GetPathName());
	if (!TestFalse(TEXT("Add player to nested graph by path"), FeedbackNov12Call(TEXT("ManageAssetAnimBlueprint"), Args).HasErrors())) return false;
	Args = FeedbackNov12Args(Blueprint); Args->SetStringField(TEXT("GraphName"), StateGraphName); Args->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("graph"))});
	TestFalse(TEXT("Read nested graph"), FeedbackNov12Call(TEXT("GetAssetAnimBlueprint"), Args).HasErrors());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusFeedbackMap12Test, "NexusLink.FeedbackNov12.StreamedMapSave", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusFeedbackMap12Test::RunTest(const FString& Parameters)
{
	UWorld* EditorWorld = GEditor->GetEditorWorldContext().World();
	const FString Path = TEXT("/Game/_McpTest/Map12_") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
	UPackage* Package = CreatePackage(*Path);
	UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false, *FPackageName::GetShortName(Path), Package);
	ULevel* Level = World->PersistentLevel; EditorWorld->AddLevel(Level); Level->OwningWorld = EditorWorld; Level->bIsVisible = false;
	Level->NavDataChunks.Add(NewObject<URecastNavMeshDataChunk>(Level));
	const FString Filename = FPackageName::LongPackageNameToFilename(Path, FPackageName::GetMapPackageExtension());
	ON_SCOPE_EXIT { EditorWorld->RemoveLevel(Level); Level->OwningWorld = World; Package->SetDirtyFlag(false); World->DestroyWorld(false); IFileManager::Get().Delete(*Filename); };
	auto Args = FeedbackNov12Args(World); Args->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("Navigation"))});
	auto Read = FeedbackNov12Call(TEXT("GetAssetLevel"), Args);
	if (!TestFalse(TEXT("Hidden level navigation inspection"), Read.HasErrors())) return false;
	TestEqual(TEXT("Serialized navigation chunk counted"), Read.Entries[0]->AsObject()->GetNumberField(TEXT("NavDataChunkCount")), 1.0);
	TestFalse(TEXT("Read preserves visibility"), Level->bIsVisible);
	FActorSpawnParameters Spawn; Spawn.OverrideLevel = Level;
	AActor* Actor = EditorWorld->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, Spawn);
	if (!TestNotNull(TEXT("Hidden level actor fixture"), Actor)) return false;
	Actor->Tags.Add(TEXT("Temporary"));
	Args = FeedbackNov12Args(World, TEXT("SetActorProperty"));
	auto Set = Args->GetArrayField(TEXT("Operations"))[0]->AsObject(); Set->SetStringField(TEXT("ActorName"), Actor->GetName()); Set->SetStringField(TEXT("PropertyPath"), TEXT("bCanBeDamaged")); Set->SetStringField(TEXT("Value"), TEXT("false"));
	auto Reset = MakeShared<FJsonObject>(*Set); Reset->SetStringField(TEXT("Action"), TEXT("ResetActorPropertyToDefault")); Reset->SetStringField(TEXT("PropertyPath"), TEXT("Tags")); Reset->RemoveField(TEXT("Value"));
	Args->SetBoolField(TEXT("bVerify"), true); Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Set), MakeShared<FJsonValueObject>(Reset)});
	TestFalse(TEXT("Level scalar verification permits array reset"), FeedbackNov12Call(TEXT("ManageAssetLevel"), Args).HasErrors());
	TestTrue(TEXT("Array reset applied"), Actor->Tags.Num() == 0);
	// 传入非 World 主对象也必须按包查找 UWorld，不能触发地图对象 ensure。
	FString Error;
	if (!TestTrue(TEXT("Native streamed map save"), FNexusAssetUtils::SaveNewAsset(Package, Level->NavDataChunks[0], Path, &Error))) { AddError(Error); return false; }
	TestTrue(TEXT("Map written"), IFileManager::Get().FileExists(*Filename));
	TestFalse(TEXT("Save clears dirty flag"), Package->IsDirty());
	UPackage* Invalid = CreatePackage(*(Path + TEXT("_Invalid"))); Invalid->SetPackageFlags(PKG_ContainsMap);
	TestFalse(TEXT("Invalid map fails before SavePackage"), FNexusAssetUtils::SaveNewAsset(Invalid, nullptr, Invalid->GetName(), &Error));
	TestTrue(TEXT("Invalid map structured error"), Error.Contains(TEXT("UWorld/PersistentLevel")));
	Invalid->SetDirtyFlag(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusFeedbackNative12Test, "NexusLink.FeedbackNov12.NativeComponents", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusFeedbackNative12Test::RunTest(const FString& Parameters)
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/Native12_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	UBlueprint* Blueprint = FKismetEditorUtilities::CreateBlueprint(ACharacter::StaticClass(), Package, TEXT("Blueprint"), BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
	ON_SCOPE_EXIT { Package->SetDirtyFlag(false); };
	const ACharacter* Defaults = CastChecked<ACharacter>(Blueprint->GeneratedClass->GetDefaultObject());
	auto Args = FeedbackNov12Args(Blueprint, TEXT("SetComponentProperty"));
	auto Set = Args->GetArrayField(TEXT("Operations"))[0]->AsObject(); Set->SetStringField(TEXT("ComponentName"), Defaults->GetMesh()->GetName()); Set->SetStringField(TEXT("PropertyPath"), TEXT("bHiddenInGame")); Set->SetStringField(TEXT("Value"), TEXT("true"));
	Args->SetBoolField(TEXT("bCompile"), true); Args->SetBoolField(TEXT("bVerify"), true);
	if (!TestFalse(TEXT("Native CharacterMesh0 verified write and compile"), FeedbackNov12Call(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	auto Reset = MakeShared<FJsonObject>(*Set); Reset->SetStringField(TEXT("Action"), TEXT("ResetComponentPropertyToDefault")); Reset->SetStringField(TEXT("PropertyPath"), TEXT("ComponentTags")); Reset->RemoveField(TEXT("Value"));
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Set), MakeShared<FJsonValueObject>(Reset)});
	TestFalse(TEXT("Verified scalar set can mix with array reset"), FeedbackNov12Call(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	Reset->SetStringField(TEXT("ExpectedValue"), TEXT("()"));
	TestTrue(TEXT("Reset still rejects ExpectedValue"), FeedbackNov12Call(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	return true;
}
#endif
