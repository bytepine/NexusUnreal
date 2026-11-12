// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"
#include "Server/NexusJsonMessageBuffer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusMigrationFramesTest, "NexusLink.FeedbackMigration.FragmentedJson", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusMigrationFramesTest::RunTest(const FString& Parameters)
{
	const FString Request = TEXT("{\"jsonrpc\":\"2.0\",\"id\":1,\"params\":{\"text\":\"中文\\\"}[") + FString::ChrN(10000, TEXT('x')) + TEXT("\"}}\n");
	FTCHARToUTF8 Utf8(*Request);
	for (int32 ChunkSize : {1, 4096})
	{
		FNexusJsonMessageBuffer Buffer; TArray<TArray<uint8>> Messages;
		for (int32 Offset = 0; Offset < Utf8.Length(); Offset += ChunkSize)
			TestTrue(TEXT("Fragments accepted"), Buffer.Append(reinterpret_cast<const uint8*>(Utf8.Get()) + Offset, FMath::Min(ChunkSize, Utf8.Length() - Offset), 1024 * 1024, Messages));
		if (!TestEqual(TEXT("Exactly one request assembled"), Messages.Num(), 1)) return false;
		TestEqual(TEXT("UTF8 bytes survive arbitrary splits"), Messages[0].Num(), Utf8.Length() - 1);
		TestTrue(TEXT("Payload unchanged"), FMemory::Memcmp(Messages[0].GetData(), Utf8.Get(), Messages[0].Num()) == 0);
	}
	FNexusJsonMessageBuffer Buffer; TArray<TArray<uint8>> Messages;
	const ANSICHAR* Pair = "{\"id\":1}{\"id\":2}";
	TestTrue(TEXT("Coalesced messages accepted"), Buffer.Append(reinterpret_cast<const uint8*>(Pair), FCStringAnsi::Strlen(Pair), 64, Messages));
	TestEqual(TEXT("Two boundaries"), Messages.Num(), 2);
	Messages.Reset();
	TestFalse(TEXT("Cumulative limit enforced"), Buffer.Append(reinterpret_cast<const uint8*>(Utf8.Get()), Utf8.Length(), 64, Messages));
	TestTrue(TEXT("Oversize connection quarantined"), Buffer.bRejected);
	TestTrue(TEXT("Rejected tail ignored"), Buffer.Append(reinterpret_cast<const uint8*>(Pair), FCStringAnsi::Strlen(Pair), 64, Messages));
	TestEqual(TEXT("Tail cannot execute"), Messages.Num(), 0);
	return true;
}

#if WITH_EDITOR
#include "NexusCapabilityRegistry.h"
#include "NexusEditorServices.h"
#include "NexusMcpToolRegistry.h"
#include "NexusReliabilityTestTypes.h"
#include "Utils/NexusAssetUtils.h"
#include "Utils/NexusBlueprintGraphUtils.h"
#include "Utils/NexusJsonUtils.h"
#include "Utils/NexusPropertyUtils.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/World.h"
#include "Engine/Level.h"
#include "GameFramework/Character.h"
#include "Components/SkeletalMeshComponent.h"
#include "K2Node_CustomEvent.h"
#include "K2Node_VariableGet.h"
#include "K2Node_CallFunction.h"
#include "EdGraphSchema_K2.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/ScopeExit.h"
#include "Misc/PackageName.h"
#include "HAL/FileManager.h"

static FCapabilityResult MigrationCall(const TCHAR* Capability, const TSharedPtr<FJsonObject>& Args)
{
	const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(Capability);
	return Record ? Record->Instance->Run(Args) : FCapabilityResult::MakeFatal(TEXT("Missing capability"));
}

static TSharedPtr<FJsonObject> MigrationArgs(UObject* Asset, const TCHAR* Action = nullptr)
{
	auto Args = MakeShared<FJsonObject>(); Args->SetStringField(TEXT("AssetPath"), Asset->GetPathName());
	if (Action) { auto Op = MakeShared<FJsonObject>(); Op->SetStringField(TEXT("Action"), Action); Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Op)}); }
	return Args;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusMigrationBlueprintTest, "NexusLink.FeedbackMigration.BlueprintEdits", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusMigrationBlueprintTest::RunTest(const FString& Parameters)
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/Migration_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	UBlueprint* Blueprint = FKismetEditorUtilities::CreateBlueprint(ACharacter::StaticClass(), Package, TEXT("Blueprint"), BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
	ON_SCOPE_EXIT { Package->SetDirtyFlag(false); };
	const FString GraphName = Blueprint->UbergraphPages[0]->GetName();
	auto Args = MigrationArgs(Blueprint, TEXT("AddNode")); auto Op = Args->GetArrayField(TEXT("Operations"))[0]->AsObject();
	Op->SetStringField(TEXT("GraphName"), GraphName); Op->SetStringField(TEXT("NodeClass"), TEXT("K2Node_CustomEvent")); Op->SetStringField(TEXT("FunctionName"), TEXT("InitNPC"));
	TestTrue(TEXT("Irrelevant FunctionName rejected"), MigrationCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	Op->RemoveField(TEXT("FunctionName")); Op->SetStringField(TEXT("CustomEventName"), TEXT("InitNPC"));
	auto Created = MigrationCall(TEXT("ManageAssetBlueprint"), Args);
	if (!TestFalse(TEXT("Named custom event created"), Created.HasErrors())) return false;
	TestEqual(TEXT("Final event name"), Created.Entries[0]->AsObject()->GetStringField(TEXT("CustomEventName")), FString(TEXT("InitNPC")));
	TestTrue(TEXT("Duplicate event name rejected"), MigrationCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	Op->SetStringField(TEXT("Action"), TEXT("SetNode")); Op->SetStringField(TEXT("NodeId"), Created.Entries[0]->AsObject()->GetStringField(TEXT("NodeId"))); Op->SetStringField(TEXT("CustomEventName"), TEXT("InitNPC2"));
	TestFalse(TEXT("Event rename"), MigrationCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	Args = MigrationArgs(Blueprint, TEXT("SetArray")); Op = Args->GetArrayField(TEXT("Operations"))[0]->AsObject();
	Op->SetStringField(TEXT("PropertyPath"), TEXT("Tags")); Op->SetArrayField(TEXT("Values"), {MakeShared<FJsonValueString>(TEXT("First")), MakeShared<FJsonValueString>(TEXT("Second"))});
	Args->SetBoolField(TEXT("bVerify"), true); Args->SetBoolField(TEXT("bCompile"), true);
	if (!TestFalse(TEXT("Typed array verified after compile"), MigrationCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	TestEqual(TEXT("Two tags"), CastChecked<AActor>(Blueprint->GeneratedClass->GetDefaultObject())->Tags.Num(), 2);
	Op->SetStringField(TEXT("Action"), TEXT("ClearArray")); Op->RemoveField(TEXT("Values"));
	TestFalse(TEXT("Explicit clear verified"), MigrationCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestEqual(TEXT("No default array element"), CastChecked<AActor>(Blueprint->GeneratedClass->GetDefaultObject())->Tags.Num(), 0);
	Op->SetStringField(TEXT("Action"), TEXT("SetDefaults")); Op->SetStringField(TEXT("PropertyPath"), TEXT("Mesh.RelativeLocation")); Op->SetStringField(TEXT("Value"), TEXT("(X=13,Y=7,Z=0)"));
	TestFalse(TEXT("Struct write verified"), MigrationCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	Args = MigrationArgs(Blueprint); Args->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("Defaults"))});
	Args->SetArrayField(TEXT("PropertyPaths"), {MakeShared<FJsonValueString>(TEXT("Mesh.RelativeLocation")), MakeShared<FJsonValueString>(TEXT("Missing.Path"))});
	auto Read = MigrationCall(TEXT("GetAssetBlueprint"), Args);
	TestTrue(TEXT("Missing requested path is an error"), Read.HasErrors());
	const auto Detail = Read.Entries[0]->AsObject();
	TestEqual(TEXT("Nested path and error both represented"), Detail->GetArrayField(TEXT("Defaults")).Num(), 2);
	TestEqual(TEXT("Missing path listed"), Detail->GetArrayField(TEXT("MissingPropertyPaths")).Num(), 1);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusMigrationArrayNumericTest, "NexusLink.FeedbackMigration.TypedArrayNumbers", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusMigrationArrayNumericTest::RunTest(const FString& Parameters)
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/Array_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	UBlueprint* Blueprint = FKismetEditorUtilities::CreateBlueprint(ANexusArrayEditTestActor::StaticClass(), Package, TEXT("Blueprint"), BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
	ON_SCOPE_EXIT { Package->SetDirtyFlag(false); };
	auto* Defaults = CastChecked<ANexusArrayEditTestActor>(Blueprint->GeneratedClass->GetDefaultObject());
	Defaults->Integers = {7}; Defaults->Bytes = {7}; Defaults->WideIntegers = {7}; Defaults->Floats = {7}; Defaults->Rows.AddDefaulted();
	auto Args = MigrationArgs(Blueprint, TEXT("SetArray"));
	auto Op = Args->GetArrayField(TEXT("Operations"))[0]->AsObject();
	Args->SetBoolField(TEXT("bVerify"), true); Args->SetBoolField(TEXT("bSaveToDisk"), true);
	int32 SaveCount = 0;
	TGuardValue<decltype(FNexusEditorServices::ApplyManageFinalize)> SaveGuard(FNexusEditorServices::ApplyManageFinalize,
		[&](const FString&, bool, bool bSave, TSharedPtr<FJsonObject>&) { if (bSave) ++SaveCount; });
	const auto Reject = [&](const TCHAR* PropertyName, const TArray<TSharedPtr<FJsonValue>>& Values)
	{
		FProperty* Property = FindFProperty<FProperty>(Defaults->GetClass(), PropertyName);
		FString Before; FNexusPropertyUtils::ExportText(Property, Before, Property->ContainerPtrToValuePtr<void>(Defaults));
		Op->SetStringField(TEXT("PropertyPath"), PropertyName); Op->SetArrayField(TEXT("Values"), Values);
		Package->SetDirtyFlag(false);
		auto Preview = MakeShared<FJsonObject>(*Args); Preview->SetStringField(TEXT("Capability"), TEXT("ManageAssetBlueprint"));
		Preview->RemoveField(TEXT("bVerify")); Preview->RemoveField(TEXT("bSaveToDisk"));
		const auto InvalidPreview = MigrationCall(TEXT("GetAssetEditPreview"), Preview);
		TestTrue(TEXT("Preview reaches reflected validation"), InvalidPreview.FatalError.IsEmpty());
		TestTrue(FString(PropertyName) + TEXT(" invalid preview rejected"), InvalidPreview.HasErrors());
		auto Write = MigrationCall(TEXT("ManageAssetBlueprint"), Args);
		TestTrue(TEXT("Write reaches reflected validation"), Write.FatalError.IsEmpty());
		TestTrue(FString(PropertyName) + TEXT(" invalid write rejected"), Write.HasErrors());
		if (Write.Entries.Num()) TestFalse(TEXT("Rejected value is not written"), Write.Entries[0]->AsObject()->GetBoolField(TEXT("bWritten")));
		FString After; FNexusPropertyUtils::ExportText(Property, After, Property->ContainerPtrToValuePtr<void>(Defaults));
		TestEqual(TEXT("Rejected array preserves all original elements"), After, Before);
		TestFalse(TEXT("Rejected array keeps package clean"), Package->IsDirty());
	};
	for (double Number : {1.5, 2147483648.0, -2147483649.0})
		Reject(TEXT("Integers"), {MakeShared<FJsonValueNumber>(42), MakeShared<FJsonValueNumber>(Number)});
	Reject(TEXT("Integers"), {MakeShared<FJsonValueString>(TEXT("oops"))});
	Reject(TEXT("Integers"), {MakeShared<FJsonValueBoolean>(true)});
	Reject(TEXT("Integers"), {MakeShared<FJsonValueNull>()});
	for (double Number : {-1.0, 256.0}) Reject(TEXT("Bytes"), {MakeShared<FJsonValueNumber>(Number)});
	Reject(TEXT("WideIntegers"), {MakeShared<FJsonValueNumber>(9223372036854775808.0)});
	Reject(TEXT("Floats"), {MakeShared<FJsonValueNumber>(1e300)});
	auto Row = MakeShared<FJsonObject>(); Row->SetNumberField(TEXT("Count"), 1.5);
	Reject(TEXT("Rows"), {MakeShared<FJsonValueObject>(Row)});
	Row->SetNumberField(TEXT("Count"), 1); Row->SetArrayField(TEXT("Values"), {MakeShared<FJsonValueNumber>(1.5)});
	Reject(TEXT("Rows"), {MakeShared<FJsonValueObject>(Row)});
	TestEqual(TEXT("No invalid array is saved"), SaveCount, 0);
	Args->SetBoolField(TEXT("bSaveToDisk"), false);
	Op->SetStringField(TEXT("PropertyPath"), TEXT("Integers"));
	Op->SetArrayField(TEXT("Values"), {MakeShared<FJsonValueNumber>(-2147483648.0), MakeShared<FJsonValueNumber>(2147483647.0)});
	const auto Valid = MigrationCall(TEXT("ManageAssetBlueprint"), Args);
	if (!TestFalse(TEXT("Integer boundaries accepted"), Valid.HasErrors()) || !Valid.Entries.Num()) return false;
	TestTrue(TEXT("Valid array readback passes"), Valid.Entries[0]->AsObject()->GetBoolField(TEXT("bVerified")));
	if (!TestEqual(TEXT("Both integer boundary elements are present"), Defaults->Integers.Num(), 2)) return false;
	TestEqual(TEXT("Minimum int32 stored exactly"), Defaults->Integers[0], MIN_int32);
	TestEqual(TEXT("Maximum int32 stored exactly"), Defaults->Integers[1], MAX_int32);
	Op->SetStringField(TEXT("PropertyPath"), TEXT("Rows")); Row->SetNumberField(TEXT("Count"), 0);
	Row->SetArrayField(TEXT("Values"), {MakeShared<FJsonValueNumber>(-1), MakeShared<FJsonValueNumber>(2)});
	Op->SetArrayField(TEXT("Values"), {MakeShared<FJsonValueObject>(Row)});
	auto NestedPreview = MakeShared<FJsonObject>(*Args); NestedPreview->SetStringField(TEXT("Capability"), TEXT("ManageAssetBlueprint"));
	NestedPreview->RemoveField(TEXT("bVerify")); NestedPreview->RemoveField(TEXT("bSaveToDisk"));
	TestFalse(TEXT("Nested valid numeric fields can be previewed"), MigrationCall(TEXT("GetAssetEditPreview"), NestedPreview).HasErrors());
	const auto Nested = MigrationCall(TEXT("ManageAssetBlueprint"), Args);
	FString NestedError = Nested.FatalError;
	for (const auto& Entry : Nested.Entries)
	{
		FString Error; if (Entry->AsObject()->TryGetStringField(TEXT("Error"), Error)) NestedError += Error;
	}
	if (!TestFalse(TEXT("Nested valid numeric fields accepted: ") + NestedError, Nested.HasErrors())
		|| !TestEqual(TEXT("One struct element is present"), Defaults->Rows.Num(), 1)
		|| !TestEqual(TEXT("Both nested integer elements are present"), Defaults->Rows[0].Values.Num(), 2)) return false;
	TestEqual(TEXT("Nested integer stored exactly"), Defaults->Rows[0].Values[0], -1);
	Op->SetArrayField(TEXT("Values"), {});
	TestFalse(TEXT("Empty array still clears"), MigrationCall(TEXT("ManageAssetBlueprint"), Args).HasErrors());
	TestEqual(TEXT("Array cleared"), Defaults->Rows.Num(), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusMigrationSaveTest, "NexusLink.FeedbackMigration.UnsafeSuperSave", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusMigrationSaveTest::RunTest(const FString& Parameters)
{
	const FString Path = TEXT("/Game/_McpTest/UnsafeSuper_") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
	UPackage* Package = CreatePackage(*Path);
	UBlueprint* Blueprint = FKismetEditorUtilities::CreateBlueprint(AActor::StaticClass(), Package, TEXT("Blueprint"), BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
	UClass* TransientOwner = NewObject<UClass>(GetTransientPackage(), NAME_None, RF_Transient);
	UFunction* Super = NewObject<UFunction>(TransientOwner, TEXT("ReceiveBeginPlay"), RF_Public);
	UFunction* Function = NewObject<UFunction>(Blueprint->GeneratedClass, TEXT("UnsafeOverride"), RF_Public);
	Function->SetSuperStruct(Super);
	ON_SCOPE_EXIT { Function->SetSuperStruct(nullptr); Package->SetDirtyFlag(false); };
	FString Error; TArray<TSharedPtr<FJsonValue>> Diagnostics;
	TestFalse(TEXT("Transient super blocked before SavePackage"), FNexusAssetUtils::SaveNewAsset(Package, Blueprint, Path, &Error, &Diagnostics));
	TestTrue(TEXT("Dirty flag preserved"), Package->IsDirty());
	if (!TestEqual(TEXT("Structured diagnostic"), Diagnostics.Num(), 1)) return false;
	TestEqual(TEXT("Diagnostic kind"), Diagnostics[0]->AsObject()->GetStringField(TEXT("ErrorKind")), FString(TEXT("InvalidSuperFunction")));
	TestFalse(TEXT("No file created"), IFileManager::Get().FileExists(*FPackageName::LongPackageNameToFilename(Path, FPackageName::GetAssetPackageExtension())));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusMigrationLevelTest, "NexusLink.FeedbackMigration.FullResetAndSchema", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusMigrationLevelTest::RunTest(const FString& Parameters)
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/Reset_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("ResetWorld"), Package);
	UBlueprint* Blueprint = FKismetEditorUtilities::CreateBlueprint(ACharacter::StaticClass(), Package, TEXT("Blueprint"), BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
	ACharacter* Default = CastChecked<ACharacter>(Blueprint->GeneratedClass->GetDefaultObject());
	Default->GetMesh()->BodyInstance.SetCollisionProfileName(TEXT("NoCollision"));
	Default->GetMesh()->BodyInstance.SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Default->GetMesh()->BodyInstance.SetObjectType(ECC_WorldStatic);
	ACharacter* Actor = World->SpawnActor<ACharacter>(Blueprint->GeneratedClass);
	ON_SCOPE_EXIT { Package->SetDirtyFlag(false); World->DestroyWorld(false); };
	if (!TestNotNull(TEXT("Character fixture"), Actor)) return false;
	Actor->GetMesh()->BodyInstance.SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Actor->GetMesh()->BodyInstance.SetObjectType(ECC_Pawn);
	auto Args = MigrationArgs(World, TEXT("ResetActorPropertyToDefault")); auto Op = Args->GetArrayField(TEXT("Operations"))[0]->AsObject();
	Op->SetStringField(TEXT("ActorName"), Actor->GetName()); Op->SetStringField(TEXT("PropertyPath"), TEXT("Mesh.BodyInstance"));
	if (!TestFalse(TEXT("Complete struct reset"), MigrationCall(TEXT("ManageAssetLevel"), Args).HasErrors())) return false;
	TestEqual(TEXT("Zero collision enabled restored"), Actor->GetMesh()->BodyInstance.GetCollisionEnabled(), ECollisionEnabled::NoCollision);
	TestEqual(TEXT("Zero object type restored"), Actor->GetMesh()->BodyInstance.GetObjectType(), ECC_WorldStatic);
	ANexusOwnedSettingsTestActor* Owner = World->SpawnActor<ANexusOwnedSettingsTestActor>();
	Owner->Settings = NewObject<UNexusOwnedSettingsTestObject>(Owner);
	TestNull(TEXT("CDO reference is null"), GetDefault<ANexusOwnedSettingsTestActor>()->Settings);
	Args = MigrationArgs(World); Args->SetStringField(TEXT("ActorName"), Owner->GetName());
	Args->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("ActorPropertySchema"))});
	Args->SetArrayField(TEXT("PropertyPaths"), {MakeShared<FJsonValueString>(TEXT("Settings"))});
	auto Read = MigrationCall(TEXT("GetAssetLevel"), Args);
	if (!TestFalse(TEXT("Instance subobject schema works without CDO reference"), Read.HasErrors())) return false;
	const auto Schema = Read.Entries[0]->AsObject()->GetArrayField(TEXT("PropertySchemas"))[0]->AsObject();
	TestEqual(TEXT("Child name discovered"), Schema->GetArrayField(TEXT("Properties"))[0]->AsObject()->GetStringField(TEXT("Name")), FString(TEXT("Threshold")));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusMigrationRemapTest, "NexusLink.FeedbackMigration.MemberRemap", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusMigrationRemapTest::RunTest(const FString& Parameters)
{
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/Remap_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	UBlueprint* Parent = FKismetEditorUtilities::CreateBlueprint(AActor::StaticClass(), Package, TEXT("Parent"), BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
	FEdGraphPinType Type; Type.PinCategory = UEdGraphSchema_K2::PC_Object; Type.PinSubCategoryObject = USkeletalMeshComponent::StaticClass();
	FBlueprintEditorUtils::AddMemberVariable(Parent, TEXT("OldMesh"), Type); FKismetEditorUtilities::CompileBlueprint(Parent);
	UBlueprint* Child = FKismetEditorUtilities::CreateBlueprint(Parent->GeneratedClass, Package, TEXT("Child"), BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
	ON_SCOPE_EXIT { Package->SetDirtyFlag(false); };
	UEdGraph* Graph = Child->UbergraphPages[0];
	UK2Node_VariableGet* Getter = NewObject<UK2Node_VariableGet>(Graph); Getter->VariableReference.SetSelfMember(TEXT("OldMesh"));
	Graph->AddNode(Getter); Getter->CreateNewGuid(); Getter->AllocateDefaultPins();
	UFunction* IsValid = UKismetSystemLibrary::StaticClass()->FindFunctionByName(TEXT("IsValid"));
	UK2Node_CallFunction* Call = CastChecked<UK2Node_CallFunction>(FNexusBlueprintGraphUtils::MakeCallFunctionNode(Graph, IsValid, 200, 0));
	UEdGraphPin* ValuePin = Getter->FindPin(TEXT("OldMesh")); UEdGraphPin* Input = Call->FindPin(TEXT("Object"));
	if (!TestNotNull(TEXT("Original value pin"), ValuePin) || !TestNotNull(TEXT("Call input"), Input)) return false;
	ValuePin->MakeLinkTo(Input);
	auto Args = MigrationArgs(Child, TEXT("Reparent")); auto Op = Args->GetArrayField(TEXT("Operations"))[0]->AsObject();
	Op->SetStringField(TEXT("ParentClass"), TEXT("Character")); Op->SetBoolField(TEXT("bAllowPotentialDataLoss"), true);
	auto Result = MigrationCall(TEXT("ManageAssetBlueprint"), Args);
	if (!TestFalse(TEXT("Reparent without compile"), Result.HasErrors())) return false;
	TestTrue(TEXT("Explicit stale generated state"), Result.TopFields->GetBoolField(TEXT("bRequiresCompile")));
	TestTrue(TEXT("Preview includes affected graph references"), Result.Entries[0]->AsObject()->GetArrayField(TEXT("AffectedGraphReferences")).Num() > 0);
	// Reparent 原生 RefreshAllNodes 会重建 pin 对象；随后迁移必须保留重建后的实际连线。
	Input = Call->FindPin(TEXT("Object"));
	TestTrue(TEXT("Reparent preserves the original graph connection"), Getter->FindPin(TEXT("OldMesh"))->LinkedTo.Contains(Input));
	Op->SetStringField(TEXT("Action"), TEXT("RemapMemberReferences")); Op->SetStringField(TEXT("OldMemberName"), TEXT("OldMesh")); Op->SetStringField(TEXT("NewMemberName"), TEXT("Mesh")); Op->SetBoolField(TEXT("bValidateOnly"), true);
	if (!TestFalse(TEXT("Dry run type checked"), MigrationCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	TestEqual(TEXT("Dry run unchanged"), Getter->GetVarName(), FName(TEXT("OldMesh")));
	Op->SetBoolField(TEXT("bValidateOnly"), false);
	if (!TestFalse(TEXT("Inherited getter remapped"), MigrationCall(TEXT("ManageAssetBlueprint"), Args).HasErrors())) return false;
	TestEqual(TEXT("New member reference"), Getter->GetVarName(), FName(TEXT("Mesh")));
	TestTrue(TEXT("Existing wiring preserved"), Getter->FindPin(TEXT("Mesh"))->LinkedTo.Contains(Input));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusMigrationSearchTest, "NexusLink.FeedbackMigration.NarrowDiscovery", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusMigrationSearchTest::RunTest(const FString& Parameters)
{
	auto Tool = FNexusMcpToolRegistry::Get().CreateTool(TEXT("SearchCapabilities"));
	if (!TestTrue(TEXT("Search tool registered"), Tool.IsValid())) return false;
	for (const TCHAR* Query : {TEXT("property"), TEXT("Lua"), TEXT("ASSET"), TEXT("runtime"), TEXT("Animation")})
	{
		auto Args = MakeShared<FJsonObject>(); Args->SetStringField(TEXT("Query"), Query);
		const auto Result = Tool->Execute(Args).StructuredContent;
		TestEqual(TEXT("Broad queries rejected consistently"), Result->GetStringField(TEXT("ErrorKind")), FString(TEXT("QueryTooBroad")));
		TestTrue(TEXT("Actionable narrow queries"), Result->GetArrayField(TEXT("SuggestedQueries")).Num() > 0);
	}
	return true;
}
#endif
