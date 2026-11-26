// Copyright byteyang. All Rights Reserved.

#include "Misc/AutomationTest.h"
#include "Interfaces/IPluginManager.h"
#include "NexusCapabilityRegistry.h"
#include "NexusSchemaTestUtils.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FNexusCapabilityGapNewCapsRegistered,
	"NexusLink.Smoke.PluginAndRegistry.GapCaps",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusCapabilityGapNewCapsRegistered::RunTest(const FString& Parameters)
{
	const TArray<FCapRecord>& Records = FNexusCapabilityRegistry::Get().GetAllRecords();
	TestTrue(TEXT("registry not empty"), Records.Num() > 0);

	auto ExpectPresent = [this](const TCHAR* Name, bool bExpect)
	{
		const FCapRecord* Rec = FNexusCapabilityRegistry::Get().FindRecordByName(Name);
		if (bExpect)
		{
			TestNotNull(Name, Rec);
		}
		else
		{
			TestNull(FString::Printf(TEXT("%s absent"), Name), Rec);
		}
	};

	const TSharedPtr<IPlugin> Niagara = IPluginManager::Get().FindPlugin(TEXT("Niagara"));
	const bool bExpectNiagara = WITH_NIAGARA && Niagara.IsValid() && Niagara->IsEnabled();
	ExpectPresent(TEXT("CreateAssetNiagaraSystem"), bExpectNiagara);
	ExpectPresent(TEXT("InteractRuntimeActorNiagara"), bExpectNiagara);
	if (bExpectNiagara)
		TestTrue(TEXT("Niagara SetEmitterEnabled"), NexusSchemaActionContains(TEXT("ManageAssetNiagaraSystem"), TEXT("SetEmitterEnabled"), *this));
#if WITH_STATETREE
	ExpectPresent(TEXT("CreateAssetStateTree"), true);
	TestTrue(TEXT("ST AddTask"), NexusSchemaActionContains(TEXT("ManageAssetStateTree"), TEXT("AddTask"), *this));
#endif
#if WITH_GAS
	ExpectPresent(TEXT("CreateAssetGameplayCueNotify"), true);
	TestTrue(TEXT("GCNotify SetCueName"), NexusSchemaActionContains(TEXT("ManageAssetGameplayCueNotify"), TEXT("SetCueName"), *this));
#else
	ExpectPresent(TEXT("CreateAssetGameplayCueNotify"), false);
#endif
#if WITH_PAPER2D
	ExpectPresent(TEXT("CreateAssetPaperSprite"), true);
#else
	ExpectPresent(TEXT("CreateAssetPaperSprite"), false);
#endif
#if WITH_COMMON_UI
	ExpectPresent(TEXT("CreateAssetCommonButtonStyle"), true);
#else
	ExpectPresent(TEXT("CreateAssetCommonButtonStyle"), false);
#endif
#if WITH_MOVIE_RENDER_PIPELINE
	ExpectPresent(TEXT("CreateAssetMoviePipelineConfig"), true);
#else
	ExpectPresent(TEXT("CreateAssetMoviePipelineConfig"), false);
#endif

	TestTrue(TEXT("BP AddMacro"), NexusSchemaActionContains(TEXT("ManageAssetBlueprint"), TEXT("AddMacro"), *this));
	TestTrue(TEXT("WBP AddAnimation"), NexusSchemaActionContains(TEXT("ManageAssetUserWidget"), TEXT("AddAnimation"), *this));
	return true;
}

#endif
