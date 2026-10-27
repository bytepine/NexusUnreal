// Copyright byteyang. All Rights Reserved.
#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Tests/AutomationCommon.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusEditorAutomationOutcomeProbe, "NexusLink.EditorOperations.Probe.Outcome", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusEditorAutomationOutcomeProbe::RunTest(const FString& Parameters)
{
	// Opt in only in the isolated adapter acceptance fixture; ordinary suite runs pass.
	if (FParse::Param(FCommandLine::Get(), TEXT("NexusEditorOperationFailureProbe")))
	{
		AddError(TEXT("Nexus adapter intentional failure probe"));
		return false;
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusEditorAutomationLatentProbe, "NexusLink.EditorOperations.Probe.Latent", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusEditorAutomationLatentProbe::RunTest(const FString& Parameters)
{
	ADD_LATENT_AUTOMATION_COMMAND(FWaitLatentCommand(5.0f));
	return true;
}
