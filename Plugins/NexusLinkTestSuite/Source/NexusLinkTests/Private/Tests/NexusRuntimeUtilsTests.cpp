// Copyright byteyang. All Rights Reserved.

#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/DataTable.h"
#include "Utils/NexusRuntimeUtils.h"

#if WITH_EDITOR
#include "Editor.h"
#endif

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusObjectIdentityTest, "NexusLink.Utils.Runtime.ObjectIdentity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusObjectIdentityTest::RunTest(const FString& Parameters)
{
	UObject* First = NewObject<UDataTable>();
	UObject* Second = NewObject<UDataTable>();
	const FString FirstId = FNexusRuntimeUtils::GetObjectIdentity(First);
	TestTrue(TEXT("Null has no identity"), FNexusRuntimeUtils::GetObjectIdentity(nullptr).IsEmpty());
	TestTrue(TEXT("Contains slot and serial"), FirstId.Contains(TEXT(":")));
	TestEqual(TEXT("Stable while alive"), FNexusRuntimeUtils::GetObjectIdentity(First), FirstId);
	TestNotEqual(TEXT("Distinct local objects"), FNexusRuntimeUtils::GetObjectIdentity(Second), FirstId);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FNexusLinkRuntimeUtilsPlayWorldTest,
	"NexusLink.Utils.Runtime.RequirePlayWorld",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusLinkRuntimeUtilsPlayWorldTest::RunTest(const FString& Parameters)
{
#if WITH_EDITOR
	if (GEditor && GEditor->PlayWorld)
	{
		AddInfo(TEXT("skip: PIE already running"));
		return true;
	}
#endif

	FString PlayError;
	UWorld* PlayWorld = FNexusRuntimeUtils::RequirePlayWorld(PlayError);
	TestNull(TEXT("RequirePlayWorld is null without PIE/Game"), PlayWorld);
	TestTrue(TEXT("RequirePlayWorld error mentions PIE/Game"),
		PlayError.Contains(TEXT("PIE")) && PlayError.Contains(TEXT("Game")));

	UWorld* ActiveWorld = FNexusRuntimeUtils::GetActiveWorld();
	TestNotNull(TEXT("GetActiveWorld still finds Editor world"), ActiveWorld);
	if (ActiveWorld)
	{
		TestTrue(TEXT("GetActiveWorld falls back to Editor"),
			ActiveWorld->WorldType == EWorldType::Editor);
	}

	return true;
}
