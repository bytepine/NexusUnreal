// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"
#include "NexusMultiSectionCapability.h"
#include "NexusCapabilityRegistry.h"

/** 覆盖显式 PascalCase section、兼容大小写与 All 展开。 */
class FNexusSectionProbe final : public FNexusMultiSectionCapability
{
	virtual void BuildDefinition(FNexusCapabilityDefinition& Out) const override { Out.Name = TEXT("SectionProbe"); }
	virtual TSharedPtr<FJsonObject> BuildCapabilitySchema() const override { return MakeShared<FJsonObject>(); }
	virtual TArray<FString> GetSectionNames() const override { return { TEXT("FirstSection"), TEXT("SecondSection") }; }
	virtual void ExecuteSection(const FString& Section, const TSharedPtr<FJsonObject>& Args, void* Target,
		TSharedPtr<FJsonObject>& Detail, FString& Error) const override { Detail->SetBoolField(Section, true); }
	virtual bool ShouldAutoUnloadIntrospected() const override { return false; }
};

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusMultiSectionCaseTest, "NexusLink.Gas.MultiSectionCase",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusMultiSectionCaseTest::RunTest(const FString& Parameters)
{
	FNexusSectionProbe Probe;
	for (const FString& Section : { FString(TEXT("FirstSection")), FString(TEXT("firstsection")), FString(TEXT("All")) })
	{
		TSharedPtr<FJsonObject> Args = MakeShared<FJsonObject>();
		Args->SetArrayField(TEXT("Sections"), { MakeShared<FJsonValueString>(Section) });
		FCapabilityResult Result = Probe.Execute(Args);
		TestFalse(TEXT("No section errors"), Result.HasErrors());
		TestEqual(TEXT("One entry"), Result.Entries.Num(), 1);
		if (Result.Entries.Num() == 1)
		{
			TestTrue(TEXT("Canonical section executed"), Result.Entries[0]->AsObject()->GetBoolField(TEXT("FirstSection")));
			if (Section == TEXT("All")) TestTrue(TEXT("All expands second section"), Result.Entries[0]->AsObject()->GetBoolField(TEXT("SecondSection")));
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusGasRegistrationTest, "NexusLink.Gas.OptionalRegistration",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusGasRegistrationTest::RunTest(const FString& Parameters)
{
	for (const FString& Name : { FString(TEXT("GetRuntimeActorAbilitySystem")), FString(TEXT("InteractRuntimeActorAbilitySystem")) })
	{
		const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(Name);
#if WITH_GAS
		TestNotNull(Name, Record);
#else
		TestNull(Name, Record);
#endif
	}
	return true;
}
