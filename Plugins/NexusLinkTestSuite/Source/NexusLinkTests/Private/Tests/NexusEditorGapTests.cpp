// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"
#include <limits>

#if WITH_EDITOR
#include "NexusNavigationTestData.h"
#include "NexusCapabilityRegistry.h"
#include "Utils/NexusJsonUtils.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Editor.h"
#include "Misc/ScopeExit.h"
#include "Misc/App.h"
#include "NavigationSystem.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "UObject/StrongObjectPtr.h"

static FCapabilityResult EditorGapCall(const TCHAR* Name, const TSharedPtr<FJsonObject>& Args)
{
	const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(Name);
	return Record ? Record->Instance->Run(Args) : FCapabilityResult::MakeFatal(TEXT("Missing capability"));
}

static UBlueprint* EditorGapBlueprint(UClass* Parent)
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/EditorGap_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	return FKismetEditorUtilities::CreateBlueprint(Parent, Package, TEXT("Blueprint"), BPTYPE_Normal,
		UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusEditorGapReparentTest, "NexusLink.EditorGaps.Reparent",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusEditorGapReparentTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UBlueprint> Blueprint(EditorGapBlueprint(AActor::StaticClass()));
	if (!TestNotNull(TEXT("Blueprint"), Blueprint.Get())) return false;
	ON_SCOPE_EXIT { Blueprint->GetOutermost()->SetDirtyFlag(false); };
	auto Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("AssetPath"), Blueprint->GetPathName());
	auto Variable = MakeShared<FJsonObject>();
	Variable->SetStringField(TEXT("Action"), TEXT("AddVariable"));
	Variable->SetStringField(TEXT("VariableName"), TEXT("OwnValue"));
	Variable->SetStringField(TEXT("VariableType"), TEXT("int"));
	Variable->SetStringField(TEXT("DefaultValue"), TEXT("7"));
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Variable)});
	Args->SetBoolField(TEXT("bCompile"), true);
	if (!TestFalse(TEXT("Owned variable fixture"), EditorGapCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	const FGuid VariableGuid = Blueprint->NewVariables[0].VarGuid;
	Args->SetBoolField(TEXT("bCompile"), false);
	auto Operation = MakeShared<FJsonObject>();
	Operation->SetStringField(TEXT("Action"), TEXT("Reparent"));
	Operation->SetStringField(TEXT("ParentClass"), TEXT("Character"));
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Operation)});
	int32 GarbageCollections = 0;
	const auto Handle = FCoreUObjectDelegates::GetPreGarbageCollectDelegate().AddLambda([&]() { ++GarbageCollections; });
	ON_SCOPE_EXIT { FCoreUObjectDelegates::GetPreGarbageCollectDelegate().Remove(Handle); };
	TestFalse(TEXT("Reparent without implicit compile"), EditorGapCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestTrue(TEXT("Parent changed"), Blueprint->ParentClass == ACharacter::StaticClass());
	TestEqual(TEXT("No hidden full compile/GC"), GarbageCollections, 0);
	GEditor->UndoTransaction();
	TestTrue(TEXT("Undo restores parent"), Blueprint->ParentClass == AActor::StaticClass());
	Args->SetBoolField(TEXT("bCompile"), true);
	FCapabilityResult Changed = EditorGapCall(TEXT("ManageAssetBlueprint"), Args);
	if (Changed.HasErrors()) for (const auto& Entry : Changed.Entries) AddInfo(FNexusJsonUtils::SerializeCondensed(Entry->AsObject()));
	TestFalse(TEXT("Reparent and final compile"), Changed.HasErrors());
	TestTrue(TEXT("Generated class has new parent"), Blueprint->GeneratedClass->IsChildOf(ACharacter::StaticClass()));
	TestTrue(TEXT("Owned variable GUID retained"), Blueprint->NewVariables[0].VarGuid == VariableGuid);
	FIntProperty* OwnValue = FindFProperty<FIntProperty>(Blueprint->GeneratedClass, TEXT("OwnValue"));
	if (TestNotNull(TEXT("Owned variable retained"), OwnValue))
		TestEqual(TEXT("Owned default retained"), OwnValue->GetPropertyValue_InContainer(Blueprint->GeneratedClass->GetDefaultObject()), 7);
	Operation->SetStringField(TEXT("ParentClass"), TEXT("Actor"));
	TestTrue(TEXT("Leaving hierarchy needs explicit loss opt-in"), EditorGapCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestTrue(TEXT("Rejected reparent preserves parent"), Blueprint->ParentClass == ACharacter::StaticClass());
	Operation->SetBoolField(TEXT("bAllowPotentialDataLoss"), true);
	TestFalse(TEXT("Explicitly leave old hierarchy"), EditorGapCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestTrue(TEXT("Recompiled Actor parent"), Blueprint->ParentClass == AActor::StaticClass());
	TStrongObjectPtr<UBlueprint> Child(EditorGapBlueprint(Blueprint->GeneratedClass));
	if (!TestNotNull(TEXT("Child"), Child.Get())) return false;
	ON_SCOPE_EXIT { Child->GetOutermost()->SetDirtyFlag(false); };
	Operation->SetStringField(TEXT("ParentClass"), Child->GeneratedClass->GetPathName());
	TestTrue(TEXT("Inheritance cycle rejected"), EditorGapCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	Operation->SetStringField(TEXT("ParentClass"), TEXT("Object"));
	TestTrue(TEXT("Actor/non-Actor family crossing rejected"), EditorGapCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusEditorGapNavigationTest, "NexusLink.EditorGaps.NavigationPath",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusEditorGapNavigationTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
	GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
	ON_SCOPE_EXIT { GEngine->DestroyWorldContext(World); World->DestroyWorld(false); };
	auto Point = [](double X) { auto Value = MakeShared<FJsonObject>(); Value->SetNumberField(TEXT("X"), X); Value->SetNumberField(TEXT("Y"), 0); Value->SetNumberField(TEXT("Z"), 0); return Value; };
	auto Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("World"), TEXT("Play"));
	Args->SetObjectField(TEXT("Start"), Point(0));
	Args->SetObjectField(TEXT("End"), Point(100));
	const auto Unavailable = EditorGapCall(TEXT("GetNavigationPath"), Args);
	if (!TestFalse(TEXT("Navigation availability query"), Unavailable.HasErrors())) return false;
	TestFalse(TEXT("Missing nav data is explicit"), Unavailable.Entries[0]->AsObject()->GetBoolField(TEXT("bNavigationAvailable")));
	auto Navigation = NewObject<UNavigationSystemV1>(World);
	World->SetNavigationSystem(Navigation);
	ANexusNavigationTestData* NavData = World->SpawnActor<ANexusNavigationTestData>();
	if (!TestNotNull(TEXT("Deterministic nav data"), NavData)) return false;
	Navigation->MainNavData = NavData;
	AActor* Actor = World->SpawnActor<AActor>();
	if (!TestNotNull(TEXT("Ordinary actor without controller"), Actor)) return false;
	const FTransform Before = Actor->GetActorTransform();
	Args->SetStringField(TEXT("ActorName"), Actor->GetName());
	Args->SetNumberField(TEXT("MaxPoints"), 1);
	const auto Found = EditorGapCall(TEXT("GetNavigationPath"), Args);
	if (!TestFalse(TEXT("Path query succeeds"), Found.HasErrors())) return false;
	const auto Path = Found.Entries[0]->AsObject();
	TestTrue(TEXT("Path found without AIController"), Path->GetBoolField(TEXT("bPathFound")));
	TestEqual(TEXT("Complete path length"), Path->GetNumberField(TEXT("Length")), 100.0);
	TestEqual(TEXT("Point count before truncation"), Path->GetIntegerField(TEXT("PointCount")), 2);
	TestEqual(TEXT("Bounded returned points"), Path->GetArrayField(TEXT("Points")).Num(), 1);
	TestTrue(TEXT("Truncation reported"), Path->GetBoolField(TEXT("bTruncated")));
	TestTrue(TEXT("Actor never moves"), Actor->GetActorTransform().Equals(Before));
	Args->SetObjectField(TEXT("End"), Point(1000));
	TestFalse(TEXT("Partial path rejected by default"), EditorGapCall(TEXT("GetNavigationPath"), Args).Entries[0]->AsObject()->GetBoolField(TEXT("bPathFound")));
	Args->SetBoolField(TEXT("bAllowPartialPath"), true);
	const auto Partial = EditorGapCall(TEXT("GetNavigationPath"), Args).Entries[0]->AsObject();
	TestTrue(TEXT("Partial path allowed explicitly"), Partial->GetBoolField(TEXT("bPathFound")) && Partial->GetBoolField(TEXT("bPartial")));
	Args->SetObjectField(TEXT("Start"), Point(std::numeric_limits<double>::infinity()));
	TestTrue(TEXT("Nonfinite coordinate rejected"), EditorGapCall(TEXT("GetNavigationPath"), Args).bIsArgInvalid);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusEditorGapAssetEditorTest, "NexusLink.EditorGaps.AssetEditor",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusEditorGapAssetEditorTest::RunTest(const FString& Parameters)
{
	TStrongObjectPtr<UBlueprint> Blueprint(EditorGapBlueprint(AActor::StaticClass()));
	if (!TestNotNull(TEXT("Editor asset"), Blueprint.Get())) return false;
	UAssetEditorSubsystem* Editors = GEditor->GetEditorSubsystem<UAssetEditorSubsystem>();
	if (!TestNotNull(TEXT("Editor subsystem"), Editors)) return false;
	ON_SCOPE_EXIT { Blueprint->GetOutermost()->SetDirtyFlag(false); Editors->CloseAllEditorsForAsset(Blueprint.Get()); };
	auto Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("AssetPath"), Blueprint->GetPathName());
	Args->SetStringField(TEXT("Action"), TEXT("Status"));
	TestFalse(TEXT("Initially closed"), EditorGapCall(TEXT("ControlEditorAssetEditor"), Args).Entries[0]->AsObject()->GetBoolField(TEXT("bIsOpen")));
	Args->SetStringField(TEXT("Action"), TEXT("Focus"));
	TestTrue(TEXT("Focus closed editor rejected"), EditorGapCall(TEXT("ControlEditorAssetEditor"), Args).HasErrors());
	Args->SetStringField(TEXT("Action"), TEXT("Open"));
	Args->SetBoolField(TEXT("bValidateOnly"), true);
	TestFalse(TEXT("Validate target"), EditorGapCall(TEXT("ControlEditorAssetEditor"), Args).HasErrors());
	TestNull(TEXT("Validation never opens an editor"), Editors->FindEditorForAsset(Blueprint.Get(), false));
	Args->SetBoolField(TEXT("bValidateOnly"), false);
	const auto Opened = EditorGapCall(TEXT("ControlEditorAssetEditor"), Args);
	if (!FApp::CanEverRender())
	{
		TestTrue(TEXT("Headless Open rejected safely"), Opened.HasErrors());
		TestNull(TEXT("Rejected headless call creates no editor"), Editors->FindEditorForAsset(Blueprint.Get(), false));
		return true;
	}
	if (!TestFalse(TEXT("Native asset editor opened"), Opened.HasErrors())) return false;
	TestTrue(TEXT("Subsystem confirms editor"), Opened.Entries[0]->AsObject()->GetBoolField(TEXT("bIsOpen")));
	const int32 Count = Editors->GetAllEditedAssets().Num();
	Args->SetStringField(TEXT("Action"), TEXT("Focus"));
	TestFalse(TEXT("Focus existing editor"), EditorGapCall(TEXT("ControlEditorAssetEditor"), Args).HasErrors());
	TestEqual(TEXT("Focus does not duplicate editor"), Editors->GetAllEditedAssets().Num(), Count);
	return true;
}
#endif
