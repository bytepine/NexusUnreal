// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"
#if WITH_EDITOR
#include "NexusCapabilityRegistry.h"
#include "NexusRelatedDataAsset.h"
#include "NexusNavigationTestData.h"
#include "Utils/NexusAssetUtils.h"
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
#include "Misc/ScopeExit.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "HAL/FileManager.h"
#include "UObject/StrongObjectPtr.h"
#include "NavigationSystem.h"
#include "K2Node_CallFunction.h"
#include "K2Node_FunctionEntry.h"
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
	Operation->SetStringField(TEXT("Action"), TEXT("ResetComponentPropertyToDefault")); Operation->RemoveField(TEXT("ExpectedValue")); Args->SetBoolField(TEXT("bVerify"), false);
	TestFalse(TEXT("Reset child to parent template"), RelatedCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
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
	TStrongObjectPtr<UBlueprint> Blueprint(RelatedBlueprint(AActor::StaticClass()));
	ON_SCOPE_EXIT { Blueprint->GetOutermost()->SetDirtyFlag(false); };
	auto Args = MakeShared<FJsonObject>(); Args->SetStringField(TEXT("AssetPath"), Blueprint->GetPathName());
	TestFalse(TEXT("Export formats query"), RelatedCall(TEXT("GetAssetExportOptions"), Args).HasErrors());
	const FString Directory = FPaths::ProjectSavedDir() / TEXT("RelatedExports") / FGuid::NewGuid().ToString(EGuidFormats::Digits);
	const FString Output = Directory / TEXT("test.t3d"); Args->SetStringField(TEXT("OutputPath"), Output); Args->SetBoolField(TEXT("bValidateOnly"), true);
	TestFalse(TEXT("Dry run"), RelatedCall(TEXT("ExportAsset"), Args).HasErrors());
	TestFalse(TEXT("Dry run creates no directory"), IFileManager::Get().DirectoryExists(*Directory));
	IFileManager::Get().MakeDirectory(*Directory, true); FFileHelper::SaveStringToFile(TEXT("existing"), *Output);
	ON_SCOPE_EXIT { IFileManager::Get().Delete(*Output); IFileManager::Get().DeleteDirectory(*Directory); };
	Args->SetStringField(TEXT("ConflictPolicy"), TEXT("Fail")); TestTrue(TEXT("Fail policy protects file"), RelatedCall(TEXT("ExportAsset"), Args).HasErrors());
	Args->SetStringField(TEXT("ConflictPolicy"), TEXT("Unique")); const auto Unique = RelatedCall(TEXT("ExportAsset"), Args);
	TestFalse(TEXT("Unique policy plans another path"), Unique.HasErrors());
	if (!Unique.HasErrors()) TestTrue(TEXT("Unique suffix"), Unique.Entries[0]->AsObject()->GetStringField(TEXT("OutputPath")).EndsWith(TEXT("test_1.t3d")));
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
