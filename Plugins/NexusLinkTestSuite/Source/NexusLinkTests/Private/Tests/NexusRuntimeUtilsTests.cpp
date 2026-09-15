// Copyright byteyang. All Rights Reserved.

#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Utils/NexusRuntimeUtils.h"

#if WITH_EDITOR
#include "Editor.h"
#endif

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
