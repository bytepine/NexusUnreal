// Copyright byteyang. All Rights Reserved.

#include "Misc/AutomationTest.h"

#if WITH_EDITOR
#include "NexusEditorServices.h"
#include "Utils/NexusAssetUtils.h"
#include "Engine/Level.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "Misc/PackageName.h"
#include "Misc/ScopeExit.h"
#include "UObject/Package.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusMapSaveValidationTest,
	"NexusLink.AssetSave.TransientMapRejected",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusMapSaveValidationTest::RunTest(const FString& Parameters)
{
	const FString PackagePath = TEXT("/Game/_McpTest/TransientMap_") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
	UPackage* Package = CreatePackage(*PackagePath);
	UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false, *FPackageName::GetShortName(PackagePath), Package);
	if (!TestNotNull(TEXT("Map world"), World)) return false;
	ULevel* PersistentLevel = World->PersistentLevel;
	if (!TestNotNull(TEXT("Persistent level"), PersistentLevel)) return false;
	const FString Filename = FPackageName::LongPackageNameToFilename(PackagePath, FPackageName::GetMapPackageExtension());
	const auto OriginalSaveMap = FNexusEditorServices::SaveMapPackage;
	int32 NativeSaveCalls = 0;
	FNexusEditorServices::SaveMapPackage = [&NativeSaveCalls](UWorld*, const FString&) { ++NativeSaveCalls; return true; };
	ON_SCOPE_EXIT
	{
		FNexusEditorServices::SaveMapPackage = OriginalSaveMap;
		World->ClearFlags(RF_Transient);
		World->PersistentLevel->ClearFlags(RF_Transient);
		Package->SetDirtyFlag(false);
		World->DestroyWorld(false);
	};
	// 分别模拟旧世界和持久层残留 Transient；防护不得清标志或进入原生保存。
	for (UObject* TransientObject : {static_cast<UObject*>(World), static_cast<UObject*>(World->PersistentLevel)})
	{
		TransientObject->SetFlags(RF_Transient);
		Package->MarkPackageDirty();
		FString Error;
		TestFalse(TEXT("Transient map rejected"), FNexusAssetUtils::SaveNewAsset(Package, World, PackagePath, &Error));
		TestTrue(TEXT("Save failure explains recovery"), Error.Contains(TEXT("transient UWorld/PersistentLevel")) && Error.Contains(TEXT("world leaks")));
		TestTrue(TEXT("Dirty state preserved"), Package->IsDirty());
		TestTrue(TEXT("Transient flag preserved"), TransientObject->HasAnyFlags(RF_Transient));
		TransientObject->ClearFlags(RF_Transient);
	}
	TestEqual(TEXT("Native save was never invoked"), NativeSaveCalls, 0);
	TestFalse(TEXT("No map file was written"), IFileManager::Get().FileExists(*Filename));
	return true;
}
#endif
