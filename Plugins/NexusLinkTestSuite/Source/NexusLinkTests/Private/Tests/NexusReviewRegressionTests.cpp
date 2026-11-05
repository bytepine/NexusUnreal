// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"

#if WITH_EDITOR
#include "NexusCapabilityRegistry.h"
#include "Utils/NexusVersionCompat.h"
#include "Components/SceneComponent.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/Engine.h"
#include "Engine/InheritableComponentHandler.h"
#include "Engine/SCS_Node.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Editor.h"
#include "FileHelpers.h"
#include "Misc/ScopeExit.h"

static FCapabilityResult ReviewCall(const TCHAR* Name, const TSharedPtr<FJsonObject>& Args)
{
	const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(Name);
	return Record ? Record->Instance->Run(Args) : FCapabilityResult::MakeFatal(TEXT("Capability missing"));
}

static UBlueprint* ReviewBlueprint(UClass* ParentClass)
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/Review_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	return FKismetEditorUtilities::CreateBlueprint(ParentClass, Package, TEXT("Blueprint"),
		BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusReviewScsTest, "NexusLink.Review.ScsReattachAndCopy",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusReviewScsTest::RunTest(const FString& Parameters)
{
	UBlueprint* Parent = ReviewBlueprint(ACharacter::StaticClass());
	if (!TestNotNull(TEXT("Parent blueprint"), Parent)) return false;
	USCS_Node* Inherited = Parent->SimpleConstructionScript->CreateNode(USceneComponent::StaticClass(), TEXT("InheritedPart"));
	Parent->SimpleConstructionScript->AddNode(Inherited);
	CastChecked<USceneComponent>(Inherited->ComponentTemplate)->SetRelativeLocation(FVector(10, 20, 30));
	FKismetEditorUtilities::CompileBlueprint(Parent);
	UBlueprint* Child = ReviewBlueprint(Parent->GeneratedClass);
	if (!TestNotNull(TEXT("Child blueprint"), Child)) return false;
	USimpleConstructionScript* SCS = Child->SimpleConstructionScript;
	USCS_Node* First = SCS->CreateNode(USceneComponent::StaticClass(), TEXT("FirstPart"));
	SCS->AddNode(First);
	USCS_Node* Second = SCS->CreateNode(USceneComponent::StaticClass(), TEXT("SecondPart"));
	First->AddChildNode(Second);
	FKismetEditorUtilities::CompileBlueprint(Child);
	auto Reattach = [&](const TCHAR* Name, const TCHAR* Target)
	{
		TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
		Args->SetStringField(TEXT("AssetPath"), Child->GetPathName());
		TSharedPtr<FJsonObject> Op = MakeShared<FJsonObject>();
		Op->SetStringField(TEXT("Action"), TEXT("ReattachComponent"));
		Op->SetStringField(TEXT("ComponentName"), Name);
		Op->SetStringField(TEXT("AttachTo"), Target);
		Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Op)});
		return ReviewCall(TEXT("ManageAssetBlueprint"), Args);
	};
	TestTrue(TEXT("Self attachment rejected"), Reattach(TEXT("FirstPart"), TEXT("FirstPart")).HasErrors());
	TestTrue(TEXT("Descendant attachment rejected"), Reattach(TEXT("FirstPart"), TEXT("SecondPart")).HasErrors());
	TestTrue(TEXT("Rejected cycle preserves tree"), First->GetChildNodes().Contains(Second));
	const int32 NodeCount = SCS->GetAllNodes().Num();
	TestFalse(TEXT("Child to native parent"), Reattach(TEXT("SecondPart"), *ACharacter::CapsuleComponentName.ToString()).HasErrors());
	TestTrue(TEXT("Native attachment becomes SCS root"), SCS->GetRootNodes().Contains(Second));
	TestFalse(TEXT("Old parent detached"), First->GetChildNodes().Contains(Second));
	TestEqual(TEXT("AllNodes unchanged"), SCS->GetAllNodes().Num(), NodeCount);
	TestFalse(TEXT("Root to local parent"), Reattach(TEXT("SecondPart"), TEXT("FirstPart")).HasErrors());
	TestFalse(TEXT("Local child removed from roots"), SCS->GetRootNodes().Contains(Second));
	TestTrue(TEXT("Local attachment restored"), First->GetChildNodes().Contains(Second));
	TestEqual(TEXT("No duplicate AllNodes"), SCS->GetAllNodes().Num(), NodeCount);
	TestFalse(TEXT("Local child to inherited parent"), Reattach(TEXT("SecondPart"), TEXT("InheritedPart")).HasErrors());
	TestTrue(TEXT("Inherited attachment becomes root"), SCS->GetRootNodes().Contains(Second));

	UActorComponent* Override = Child->GetInheritableComponentHandler(true)->CreateOverridenComponentTemplate(FComponentKey(Inherited));
	USceneComponent* SceneOverride = Cast<USceneComponent>(Override);
	if (!TestNotNull(TEXT("Inherited override"), SceneOverride)) return false;
	const FVector OverrideLocation(111, 222, 333);
	SceneOverride->SetRelativeLocation(OverrideLocation);
	FKismetEditorUtilities::CompileBlueprint(Child);
	UBlueprint* Dest = ReviewBlueprint(AActor::StaticClass());
	if (!TestNotNull(TEXT("Destination blueprint"), Dest)) return false;
	TSharedPtr<FJsonObject> CopyArgs = MakeShared<FJsonObject>();
	CopyArgs->SetStringField(TEXT("AssetPath"), Dest->GetPathName());
	TSharedPtr<FJsonObject> Copy = MakeShared<FJsonObject>();
	Copy->SetStringField(TEXT("Action"), TEXT("CopyComponent"));
	Copy->SetStringField(TEXT("SourceAssetPath"), Child->GetPathName());
	Copy->SetStringField(TEXT("SourceComponentName"), TEXT("InheritedPart"));
	Copy->SetStringField(TEXT("ComponentName"), TEXT("CopiedPart"));
	CopyArgs->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Copy)});
	TestFalse(TEXT("Copy inherited component"), ReviewCall(TEXT("ManageAssetBlueprint"), CopyArgs).HasErrors());
	USCS_Node* Copied = Dest->SimpleConstructionScript->FindSCSNode(TEXT("CopiedPart"));
	if (TestNotNull(TEXT("Copied node"), Copied))
	{
		TestTrue(TEXT("Child override copied"), CastChecked<USceneComponent>(Copied->ComponentTemplate)->GetRelativeLocation().Equals(OverrideLocation));
	}
	for (UBlueprint* Blueprint : {Parent, Child, Dest}) Blueprint->GetOutermost()->SetDirtyFlag(false);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusReviewTransformTest, "NexusLink.Review.TransformValidation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusReviewTransformTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
	ON_SCOPE_EXIT { GEngine->DestroyWorldContext(World); World->DestroyWorld(false); };
	AActor* Actor = World->SpawnActor<AActor>();
	if (!TestNotNull(TEXT("Actor"), Actor)) return false;
	USceneComponent* Root = NewObject<USceneComponent>(Actor);
	Actor->SetRootComponent(Root);
	Root->RegisterComponent();
	Actor->SetActorLocation(FVector(7, 8, 9));
	const FTransform Before = Actor->GetActorTransform();
	TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("ActorName"), Actor->GetName());
	Args->SetStringField(TEXT("Location"), TEXT("100,200,300"));
	Args->SetStringField(TEXT("Rotation"), TEXT("bad"));
	TestTrue(TEXT("Malformed rotation rejected"), ReviewCall(TEXT("SetRuntimeActorTransform"), Args).HasErrors());
	TestTrue(TEXT("Rotation failure leaves complete transform unchanged"), Actor->GetActorTransform().Equals(Before));
	Args->SetStringField(TEXT("Rotation"), TEXT("0,90,0"));
	Args->SetStringField(TEXT("Scale"), TEXT("1,2"));
	TestTrue(TEXT("Malformed scale rejected"), ReviewCall(TEXT("SetRuntimeActorTransform"), Args).HasErrors());
	TestTrue(TEXT("Scale failure leaves complete transform unchanged"), Actor->GetActorTransform().Equals(Before));
	Args->RemoveField(TEXT("Rotation"));
	Args->RemoveField(TEXT("Scale"));
	for (const TCHAR* Invalid : {TEXT("abc,0,0"), TEXT("1x,2,3"), TEXT("nan,0,0"), TEXT("inf,0,0"), TEXT("1e80,0,0"), TEXT("1,,2,3")})
	{
		Args->SetStringField(TEXT("Location"), Invalid);
		TestTrue(FString::Printf(TEXT("Reject %s"), Invalid), ReviewCall(TEXT("SetRuntimeActorTransform"), Args).HasErrors());
		TestTrue(TEXT("Invalid numbers never move Actor"), Actor->GetActorTransform().Equals(Before));
	}
	Args->SetStringField(TEXT("Location"), TEXT("1e2, -2.5, 3"));
	Args->SetStringField(TEXT("Rotation"), TEXT("0 90 0"));
	Args->SetStringField(TEXT("Scale"), TEXT("2,2,2"));
	const FCapabilityResult Changed = ReviewCall(TEXT("SetRuntimeActorTransform"), Args);
	TestFalse(TEXT("Valid transform succeeds"), Changed.HasErrors());
	TestTrue(TEXT("Location applied"), Actor->GetActorLocation().Equals(FVector(100, -2.5, 3)));
	TestTrue(TEXT("Rotation applied"), Actor->GetActorRotation().Equals(FRotator(0, 90, 0)));
	TestTrue(TEXT("Scale applied"), Actor->GetActorScale3D().Equals(FVector(2)));
	if (TestEqual(TEXT("Transform result"), Changed.Entries.Num(), 1))
	{
		TestEqual(TEXT("Previous transform returned"), Changed.Entries[0]->AsObject()->GetStringField(TEXT("OldLocation")), FString(TEXT("7.0,8.0,9.0")));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusReviewDirtyLevelTest, "NexusLink.Review.DirtyLevelProtection",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusReviewDirtyLevelTest::RunTest(const FString& Parameters)
{
	// 暂存已有脏标记，让断言只由测试的非当前地图/外部 Actor 包触发。
	TArray<UPackage*> ExistingDirty;
	FEditorFileUtils::GetDirtyWorldPackages(ExistingDirty);
	for (UPackage* Package : ExistingDirty) Package->SetDirtyFlag(false);
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/DirtyLevel_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	UWorld* OtherWorld = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("DirtyLevel"), Package);
	UWorld* CurrentWorld = GEditor->GetEditorWorldContext().World();
	ON_SCOPE_EXIT
	{
		Package->SetDirtyFlag(false);
		OtherWorld->DestroyWorld(false);
		for (UPackage* Existing : ExistingDirty) Existing->SetDirtyFlag(true);
	};
	TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("AssetPath"), TEXT("/Engine/Maps/Entry"));
	Package->SetDirtyFlag(true);
	TestTrue(TEXT("Dirty non-current level blocks map switch"), ReviewCall(TEXT("ControlEditorLevel"), Args).HasErrors());
	TestTrue(TEXT("Rejected switch preserves world"), GEditor->GetEditorWorldContext().World() == CurrentWorld);
	TestTrue(TEXT("Rejected switch preserves dirty flag"), Package->IsDirty());
#if NX_UE_AT_LEAST(5, 0)
	AActor* ExternalActor = OtherWorld->SpawnActor<AActor>();
	if (!TestNotNull(TEXT("External Actor"), ExternalActor)) return false;
	UPackage* ExternalPackage = CreatePackage(*(Package->GetName() + TEXT("_Actor")));
	ExternalActor->SetExternalPackage(ExternalPackage);
	ExternalPackage->SetDirtyFlag(true);
	Package->SetDirtyFlag(false);
	TestTrue(TEXT("Dirty external Actor blocks switch with clean world"), ReviewCall(TEXT("ControlEditorLevel"), Args).HasErrors());
	TestTrue(TEXT("External dirty flag preserved"), ExternalPackage->IsDirty());
	TestTrue(TEXT("External rejection preserves world"), GEditor->GetEditorWorldContext().World() == CurrentWorld);
	ExternalPackage->SetDirtyFlag(false);
	ExternalActor->SetExternalPackage(nullptr);
#endif
	return true;
}
#endif
