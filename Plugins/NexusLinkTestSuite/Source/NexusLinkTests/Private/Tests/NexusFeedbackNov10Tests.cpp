// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"
#if WITH_EDITOR
#include "NexusCapabilityRegistry.h"
#include "NexusMcpToolRegistry.h"
#include "NexusLinkSettings.h"
#include "NexusRelatedDataAsset.h"
#include "Utils/NexusAssetUtils.h"
#include "Utils/NexusEditorLevelUtils.h"
#include "Utils/NexusPropertyUtils.h"
#include "Utils/NexusCapResultAdapter.h"
#include "Engine/World.h"
#include "Engine/Level.h"
#include "Model.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "Components/SceneComponent.h"
#include "Editor.h"
#include "Misc/ScopeExit.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformFileManager.h"
#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#endif

static FCapabilityResult FeedbackNov10Call(const TCHAR* Name, const TSharedPtr<FJsonObject>& Args)
{
	const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(Name);
	return Record ? Record->Instance->Run(Args) : FCapabilityResult::MakeFatal(TEXT("Missing capability"));
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusFeedbackStreamingLevelTest, "NexusLink.FeedbackNov10.StreamingLevelScope", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusFeedbackStreamingLevelTest::RunTest(const FString& Parameters)
{
	UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	if (!TestNotNull(TEXT("Editor fixture"), EditorWorld)) return false;
	ULevel* OriginalCurrent = EditorWorld->GetCurrentLevel();
	const bool bOriginalDirty = EditorWorld->GetOutermost()->IsDirty();
	UNexusLinkSettings* Settings = GetMutableDefault<UNexusLinkSettings>();
	const auto OriginalEnabled = Settings->SessionEnabledCapabilities;
	ON_SCOPE_EXIT { Settings->SessionEnabledCapabilities = OriginalEnabled; };
	Settings->SessionEnabledCapabilities.Add(TEXT("ControlEditorScene"));
	UPackage* Package = CreatePackage(*(TEXT("/Game/_McpTest/Streaming_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	UWorld* ChildWorld = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("Streaming"), Package);
	ULevel* ChildLevel = ChildWorld->PersistentLevel;
	EditorWorld->AddLevel(ChildLevel);
	ChildLevel->OwningWorld = EditorWorld;
	ON_SCOPE_EXIT { EditorWorld->SetCurrentLevel(OriginalCurrent); EditorWorld->RemoveLevel(ChildLevel); ChildLevel->OwningWorld = ChildWorld; Package->SetDirtyFlag(false); ChildWorld->DestroyWorld(false); EditorWorld->GetOutermost()->SetDirtyFlag(bOriginalDirty); };
	AActor* Actor = nullptr;
	FString Error;
	if (!TestTrue(TEXT("Spawn into child level"), FNexusEditorLevelUtils::SpawnActorInLevelWorld(ChildWorld, ANavMeshBoundsVolume::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator, Actor, Error))) return false;
	TestTrue(TEXT("Actor owns exact sublevel"), Actor->GetLevel() == ChildLevel && Actor->GetWorld() == EditorWorld);
	bool bEditorWorld = false;
	TestTrue(TEXT("Loaded sublevel resolves live asset world"), FNexusEditorLevelUtils::LoadLevelWorldForRead(Package->GetName(), bEditorWorld, Error) == ChildWorld && bEditorWorld);
	TestTrue(TEXT("Sublevel lookup finds live actor"), FNexusEditorLevelUtils::FindLevelActorByNameOrLabel(ChildWorld, Actor->GetName(), false) == Actor);
	TestNull(TEXT("Persistent level cannot address child actor"), FNexusEditorLevelUtils::FindLevelActorByNameOrLabel(EditorWorld, Actor->GetName(), false));
	auto Args = MakeShared<FJsonObject>();
	Args->SetStringField(TEXT("AssetPath"), ChildWorld->GetPathName());
	Args->SetStringField(TEXT("ActorName"), Actor->GetName());
	Args->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("Actors"))});
	auto Read = FeedbackNov10Call(TEXT("GetAssetLevel"), Args);
	if (!TestFalse(TEXT("Read scoped actors"), Read.HasErrors()) || !Read.Entries.Num()) return false;
	TestTrue(TEXT("Scoped actor enumeration is nonempty"), Read.Entries[0]->AsObject()->GetNumberField(TEXT("ActorTotalCount")) > 0);
	Args->RemoveField(TEXT("Sections")); Args->RemoveField(TEXT("ActorName"));
	auto Operation = MakeShared<FJsonObject>();
	Operation->SetStringField(TEXT("Action"), TEXT("SetActorProperty")); Operation->SetStringField(TEXT("ActorName"), Actor->GetName());
	Operation->SetStringField(TEXT("PropertyPath"), TEXT("RootComponent.RelativeLocation.Z")); Operation->SetStringField(TEXT("Value"), TEXT("123"));
	Operation->SetStringField(TEXT("ExpectedValue"), TEXT("0"));
	auto PreviewArgs = MakeShared<FJsonObject>(); PreviewArgs->SetStringField(TEXT("AssetPath"), ChildWorld->GetPathName());
	PreviewArgs->SetStringField(TEXT("Capability"), TEXT("ManageAssetLevel")); PreviewArgs->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Operation)});
	auto PreviewResult = FeedbackNov10Call(TEXT("GetAssetEditPreview"), PreviewArgs);
	if (!TestFalse(TEXT("Read sublevel preview"), PreviewResult.HasErrors()) || !PreviewResult.Entries.Num()) return false;
	auto Preview = PreviewResult.Entries[0]->AsObject();
	TestTrue(TEXT("Sublevel preview resolves actor"), Preview->GetBoolField(TEXT("bValid")));
	TestEqual(TEXT("Preview never writes"), static_cast<double>(Actor->GetActorLocation().Z), 0.0);
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Operation)}); Args->SetBoolField(TEXT("bVerify"), true);
	if (!TestFalse(TEXT("Verified sublevel write"), FeedbackNov10Call(TEXT("ManageAssetLevel"), Args).HasErrors())) return false;
	TestEqual(TEXT("Component world transform refreshed"), static_cast<double>(Actor->GetRootComponent()->GetComponentLocation().Z), 123.0);
	TestEqual(TEXT("Owning package echoed"), Preview->GetStringField(TEXT("LevelPath")), Package->GetName());
	// 验证混合批在任何写入前拒绝，避免前半段属性已改、后半段创建失败。
	Operation->SetStringField(TEXT("Value"), TEXT("456")); Operation->SetStringField(TEXT("ExpectedValue"), TEXT("123"));
	auto Bounds = MakeShared<FJsonObject>(); Bounds->SetStringField(TEXT("Action"), TEXT("CreateNavMeshBoundsVolume"));
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Operation), MakeShared<FJsonValueObject>(Bounds)});
	TestTrue(TEXT("Mixed verified batch rejected before writes"), FeedbackNov10Call(TEXT("ManageAssetLevel"), Args).HasErrors());
	TestEqual(TEXT("Rejected mixed batch preserves first value"), static_cast<double>(Actor->GetActorLocation().Z), 123.0);
	Args->RemoveField(TEXT("bVerify"));
	for (const auto& Pair : {TPair<FString, FVector>(TEXT("BoundsMin"), FVector(-100,-200,-300)), TPair<FString, FVector>(TEXT("BoundsMax"), FVector(100,200,300))})
	{
		auto Vector = MakeShared<FJsonObject>();
		Vector->SetNumberField(TEXT("X"), Pair.Value.X); Vector->SetNumberField(TEXT("Y"), Pair.Value.Y); Vector->SetNumberField(TEXT("Z"), Pair.Value.Z);
		Bounds->SetObjectField(Pair.Key, Vector);
	}
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Bounds)});
	auto Created = FeedbackNov10Call(TEXT("ManageAssetLevel"), Args);
	if (!TestFalse(TEXT("Build native cube brush in sublevel"), Created.HasErrors()) || !Created.Entries.Num()) return false;
	const FString VolumeName = Created.Entries[0]->AsObject()->GetStringField(TEXT("ActorName"));
	AActor* Volume = FNexusEditorLevelUtils::FindLevelActorByNameOrLabel(ChildWorld, VolumeName, false);
	if (!TestNotNull(TEXT("Created volume belongs to sublevel"), Volume)) return false;
	TestTrue(TEXT("Bounds use geometry with unit scale"), Volume->GetActorScale3D().Equals(FVector::OneVector) && Volume->GetComponentsBoundingBox(true).GetSize().Equals(FVector(200,400,600), 0.1f));
	auto PropertyArgs = MakeShared<FJsonObject>(); PropertyArgs->SetStringField(TEXT("AssetPath"), ChildWorld->GetPathName());
	PropertyArgs->SetStringField(TEXT("ActorName"), VolumeName);
	PropertyArgs->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("ActorProperties"))});
	PropertyArgs->SetArrayField(TEXT("PropertyPaths"), {MakeShared<FJsonValueString>(TEXT("BrushBuilder.X"))});
	Read = FeedbackNov10Call(TEXT("GetAssetLevel"), PropertyArgs);
	if (!TestFalse(TEXT("Null CDO brush builder is nonfatal"), Read.HasErrors()) || !Read.Entries.Num()) return false;
	auto Property = Read.Entries[0]->AsObject()->GetArrayField(TEXT("Properties"))[0]->AsObject();
	TestTrue(TEXT("Actor value retained with default warning"), Property->HasField(TEXT("Value")) && Property->GetBoolField(TEXT("bDefaultUnavailable")));
	Bounds->SetStringField(TEXT("Action"), TEXT("ResizeNavMeshBoundsVolume")); Bounds->SetStringField(TEXT("ActorName"), VolumeName);
	Bounds->GetObjectField(TEXT("BoundsMax"))->SetNumberField(TEXT("X"), 300);
	TestFalse(TEXT("Resize existing native brush"), FeedbackNov10Call(TEXT("ManageAssetLevel"), Args).HasErrors());
	TestTrue(TEXT("Resize preserves identity and updates geometry"), FNexusEditorLevelUtils::FindLevelActorByNameOrLabel(ChildWorld, VolumeName, false) == Volume && Volume->GetComponentsBoundingBox(true).GetSize().Equals(FVector(400,400,600), 0.1f));
	auto LevelArgs = MakeShared<FJsonObject>(); LevelArgs->SetStringField(TEXT("AssetPath"), Package->GetName());
	for (const TCHAR* Action : {TEXT("LoadStreaming"), TEXT("Hide"), TEXT("Show"), TEXT("MakeCurrent")})
	{
		LevelArgs->SetStringField(TEXT("Action"), Action);
		TestFalse(TEXT("Named sublevel state operation"), FeedbackNov10Call(TEXT("ControlEditorLevel"), LevelArgs).HasErrors());
	}
	TestTrue(TEXT("MakeCurrent targets exact child"), EditorWorld->GetCurrentLevel() == ChildLevel && ChildLevel->bIsVisible);
	// 此夹具手工挂接 ULevel，未迁移原世界的 LevelCollection；预检用持久层体积避免迭代器过滤夹具。
	FActorSpawnParameters RootParams; RootParams.OverrideLevel = EditorWorld->PersistentLevel;
	AActor* RootBounds = EditorWorld->SpawnActor<ANavMeshBoundsVolume>(FVector::ZeroVector, FRotator::ZeroRotator, RootParams);
	if (!TestNotNull(TEXT("Navigation preflight bounds fixture"), RootBounds)) return false;
	auto BuildArgs = MakeShared<FJsonObject>(); BuildArgs->SetStringField(TEXT("Action"), TEXT("BuildNavigation")); BuildArgs->SetBoolField(TEXT("bSaveToDisk"), true);
	auto Rejected = FeedbackNov10Call(TEXT("ControlEditorScene"), BuildArgs);
	AddInfo(TEXT("Navigation preflight result: ") + Rejected.FatalError);
	TestTrue(TEXT("Dirty navigation build rejects before starting"), Rejected.bIsArgInvalid && Rejected.TopFields.IsValid() && Rejected.TopFields->GetArrayField(TEXT("DirtyLevelPaths")).Num() > 0);
	const auto MultiTool = FNexusCapResultAdapter::Convert(Rejected, TEXT("ControlEditorScene"));
	TestTrue(TEXT("MultiTool preserves dirty-package diagnostics"), MultiTool.bIsError && MultiTool.StructuredContent.IsValid() && MultiTool.StructuredContent->HasField(TEXT("DirtyLevelPaths")));
	auto CallTool = FNexusMcpToolRegistry::Get().CreateTool(TEXT("CallCapability"));
	auto CallArgs = MakeShared<FJsonObject>(); CallArgs->SetStringField(TEXT("Capability"), TEXT("ControlEditorScene")); CallArgs->SetObjectField(TEXT("Arguments"), BuildArgs);
	if (!TestTrue(TEXT("CallCapability tool registered"), CallTool.IsValid())) return false;
	const auto SearchMode = CallTool->Execute(CallArgs);
	TestTrue(TEXT("SearchMode preserves dirty-package diagnostics"), SearchMode.bIsError && SearchMode.StructuredContent.IsValid() && SearchMode.StructuredContent->HasField(TEXT("DirtyLevelPaths")));
	EditorWorld->EditorDestroyActor(RootBounds, true);
	Operation->SetStringField(TEXT("Action"), TEXT("RemoveActor")); Args->RemoveField(TEXT("bVerify")); Operation->RemoveField(TEXT("ExpectedValue"));
	Args->SetArrayField(TEXT("Operations"), {MakeShared<FJsonValueObject>(Operation)});
	TestFalse(TEXT("Remove uses owning editor world"), FeedbackNov10Call(TEXT("ManageAssetLevel"), Args).HasErrors());
	TestNull(TEXT("Removed actor no longer resolves"), FNexusEditorLevelUtils::FindLevelActorByNameOrLabel(ChildWorld, Actor->GetName(), false));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusFeedbackSaveFailureTest, "NexusLink.FeedbackNov10.SaveFailure", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusFeedbackSaveFailureTest::RunTest(const FString& Parameters)
{
	const FString Path = TEXT("/Game/_McpTest/SaveFailure_") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
	UPackage* Package = CreatePackage(*Path);
	UNexusRelatedDataAsset* Asset = NewObject<UNexusRelatedDataAsset>(Package, *FPackageName::GetShortName(Path), RF_Public | RF_Standalone);
	const FString Filename = FPaths::ConvertRelativePathToFull(FPackageName::LongPackageNameToFilename(Path, FPackageName::GetAssetPackageExtension()));
	ON_SCOPE_EXIT { Package->SetDirtyFlag(false); FPlatformFileManager::Get().GetPlatformFile().SetReadOnly(*Filename, false); IFileManager::Get().Delete(*Filename); };
	FString Error;
	if (!TestTrue(TEXT("Initial save"), FNexusAssetUtils::SaveNewAsset(Package, Asset, Path, &Error))) return false;
	TArray<uint8> Before, After;
	if (!TestTrue(TEXT("Read original file"), FFileHelper::LoadFileToArray(Before, *Filename))) return false;
	Asset->Location.Z = 99; Package->MarkPackageDirty();
	FPlatformFileManager::Get().GetPlatformFile().SetReadOnly(*Filename, true);
	TestFalse(TEXT("Read-only destination rejected"), FNexusAssetUtils::SaveNewAsset(Package, Asset, Path, &Error));
	TestTrue(TEXT("Save failure has diagnostics and retains dirty state"), Error.Contains(TEXT("read-only")) && Package->IsDirty());
	FPlatformFileManager::Get().GetPlatformFile().SetReadOnly(*Filename, false);
#if PLATFORM_WINDOWS
	HANDLE Lock = ::CreateFileW(*Filename, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
	if (!TestTrue(TEXT("External lock fixture"), Lock != INVALID_HANDLE_VALUE)) return false;
	TestFalse(TEXT("Locked destination returns without fatal"), FNexusAssetUtils::SaveNewAsset(Package, Asset, Path, &Error));
	TestTrue(TEXT("Lock failure is explicit"), Error.Contains(TEXT("locked")) && Package->IsDirty());
	::CloseHandle(Lock);
#endif
	TestTrue(TEXT("Read preserved file"), FFileHelper::LoadFileToArray(After, *Filename));
	TestTrue(TEXT("Failed saves preserve existing bytes"), Before == After);
	TestTrue(TEXT("Save succeeds once lock is released"), FNexusAssetUtils::SaveNewAsset(Package, Asset, Path, &Error));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusFeedbackDiscoveryTest, "NexusLink.FeedbackNov10.FreshDiscovery", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusFeedbackDiscoveryTest::RunTest(const FString& Parameters)
{
	auto Tool = FNexusMcpToolRegistry::Get().CreateTool(TEXT("SearchCapabilities"));
	if (!TestTrue(TEXT("Discovery tool registered"), Tool.IsValid())) return false;
	UNexusLinkSettings* Settings = GetMutableDefault<UNexusLinkSettings>();
	const auto OriginalDisabled = Settings->SessionDisabledCapabilities;
	ON_SCOPE_EXIT { Settings->SessionDisabledCapabilities = OriginalDisabled; };
	const FString Name = TEXT("GetAssetLevel");
	auto Args = MakeShared<FJsonObject>(); Args->SetStringField(TEXT("CapabilityName"), Name);
	Settings->SessionDisabledCapabilities.Add(Name);
	auto Disabled = Tool->Execute(Args).StructuredContent;
	TestEqual(TEXT("Disabled discovery never cached"), Disabled->GetNumberField(TEXT("TtlSeconds")), 0.0);
	TestEqual(TEXT("Access status comes from UE"), Disabled->GetStringField(TEXT("AccessStateSource")), FString(TEXT("UE")));
	TestTrue(TEXT("Reports session gate"), Disabled->GetBoolField(TEXT("bSessionDisabled")));
	Settings->SessionDisabledCapabilities.Remove(Name);
	auto Enabled = Tool->Execute(Args).StructuredContent;
	TestTrue(TEXT("Fresh discovery reflects enabled state"), Enabled->HasField(TEXT("Capability")));
	TestEqual(TEXT("Enabled discovery never cached"), Enabled->GetNumberField(TEXT("TtlSeconds")), 0.0);
	return true;
}
#endif
