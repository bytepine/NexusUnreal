// Copyright byteyang. All Rights Reserved.
#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#include "NexusEditorOperation.h"
#include "NexusLinkSettings.h"
#include "NexusCapabilityRegistry.h"
#include "NexusMcpToolRegistry.h"
#include "NexusMcpTool.h"
#include "Dom/JsonValue.h"
#include "Utils/NexusResponseCompactorUtils.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusOperationIsolationTest, "NexusLink.EditorOperations.OwnerAndContract", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusOperationIsolationTest::RunTest(const FString& Parameters)
{
	TGuardValue<FString> Owner(FNexusEditorOperations::RequestOwner(), TEXT("test-owner-a"));
	auto Operation = FNexusEditorOperations::Create(TEXT("Test"));
	TestTrue(TEXT("Created owned operation"), Operation.IsValid());
	if (!Operation.IsValid()) return false;
	{
		TGuardValue<FString> Foreign(FNexusEditorOperations::RequestOwner(), TEXT("test-owner-b"));
		TestFalse(TEXT("Another session cannot read operation"), FNexusEditorOperations::Find(Operation->Id).IsValid());
		TestFalse(TEXT("Another session cannot cancel operation"), FNexusEditorOperations::Cancel(Operation->Id));
	}
	TestFalse(TEXT("Uncancellable work stays running"), FNexusEditorOperations::Cancel(Operation->Id));
	auto Result = MakeShared<FJsonObject>(); Result->SetStringField(TEXT("Outcome"), TEXT("Unknown"));
	FNexusEditorOperations::Finish(Operation, TEXT("Completed"), Result);
	FNexusEditorOperations::Finish(Operation, TEXT("Failed"), nullptr, TEXT("Late callback"));
	TestEqual(TEXT("Late completion cannot overwrite outcome"), Operation->State, FString(TEXT("Completed")));
	auto Copy = Operation->Snapshot();
	Copy->GetObjectField(TEXT("Result"))->SetStringField(TEXT("Outcome"), TEXT("Changed"));
	TestEqual(TEXT("Snapshot does not mutate retained result"), Operation->Result->GetStringField(TEXT("Outcome")), FString(TEXT("Unknown")));
	const auto* Record = FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("GetEditorOperation"));
	if (!TestNotNull(TEXT("GetEditorOperation is registered"), Record)) return false;
	FString Error;
	TestTrue(TEXT("Snapshot satisfies output contract"), FNexusCapability::ValidateOutput(Operation->Snapshot(), Record->Def.OutputSchema, Error));
    auto EmptyTitle = Operation->Snapshot(); auto Window = MakeShared<FJsonObject>();
    Window->SetStringField(TEXT("Ref"), TEXT("window")); Window->SetStringField(TEXT("Title"), TEXT(""));
    auto Windows = MakeShared<FJsonObject>(); Windows->SetArrayField(TEXT("Windows"), {MakeShared<FJsonValueObject>(Window)});
    EmptyTitle->SetObjectField(TEXT("Result"), Windows);
    TestTrue(TEXT("Output permits an untitled window"), FNexusCapability::ValidateOutput(EmptyTitle, Record->Def.OutputSchema, Error));
    TArray<TSharedPtr<FJsonValue>> Nodes;
    for (int32 Index = 0; Index < 10; ++Index) { auto Node = MakeShared<FJsonObject>(); Node->SetStringField(TEXT("Ref"), FString::Printf(TEXT("widget-%d"), Index)); Node->SetStringField(TEXT("Type"), TEXT("STextBlock")); Node->SetBoolField(TEXT("bEnabled"), true); Nodes.Add(MakeShared<FJsonValueObject>(Node)); }
    Windows->SetArrayField(TEXT("Nodes"), Nodes);
    TGuardValue<bool> Compact(GetMutableDefault<UNexusLinkSettings>()->bCompactResponseDefaults, true);
    FNexusResponseCompactorUtils::AutoCompactRecursive(EmptyTitle);
    TestTrue(TEXT("Fixture actually exercised compaction"), Windows->HasField(TEXT("Nodes_defaults")));
    TestTrue(TEXT("Final compacted output satisfies contract"), FNexusCapability::ValidateOutput(EmptyTitle, Record->Def.OutputSchema, Error));
    Window->SetNumberField(TEXT("Title"), 7);
    TestFalse(TEXT("Nested output type is checked"), FNexusCapability::ValidateOutput(EmptyTitle, Record->Def.OutputSchema, Error));
	auto Invalid = Operation->Snapshot(); Invalid->SetBoolField(TEXT("State"), false);
	TestFalse(TEXT("Wrong result field type is rejected"), FNexusCapability::ValidateOutput(Invalid, Record->Def.OutputSchema, Error));
	for (const TCHAR* Name : {TEXT("GetEditorSlate"), TEXT("CaptureEditorSlate"), TEXT("InteractEditorSlate"), TEXT("ControlEditorAutomation"), TEXT("ListEditorAutomationTests"), TEXT("CompileEditorLiveCoding"), TEXT("GetEditorOperation")})
	{
		const auto* Item = FNexusCapabilityRegistry::Get().FindRecordByName(Name);
		if (!TestNotNull(Name, Item)) continue;
		TestFalse(TEXT("No automatic transaction"), Item->Def.bAutoTransaction);
		TestFalse(TEXT("No batch side effects"), Item->Def.bAllowBatch);
		TestFalse(TEXT("No cached state"), Item->Def.bCacheable);
		TestTrue(TEXT("Output contract exists"), Item->Def.OutputSchema.IsValid());
	}
	return true;
}

static int32 GNexusBatchProbeCalls = 0;
class FNexusEditorBatchProbeCapability final : public FNexusCapability
{
	void BuildDefinition(FNexusCapabilityDefinition& Out) const override
	{
		Out.Name = TEXT("GetEditorBatchProbe");
		Out.Description = TEXT("Inspect test probe. Counts calls for batch preflight verification.");
		Out.Tags = {TEXT("Readonly"), TEXT("Editor")};
		Out.InputSchema = MakeShared<FJsonObject>(); Out.InputSchema->SetStringField(TEXT("type"), TEXT("object"));
	}
	FCapabilityResult Execute(const TSharedPtr<FJsonObject>& Arguments) const override { ++GNexusBatchProbeCalls; return FCapabilityResult(); }
};

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusBatchPreflightTest, "NexusLink.EditorOperations.BatchPreflight", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusBatchPreflightTest::RunTest(const FString& Parameters)
{
    struct FRestoreRegistry final {
        TArray<FCapRecord> Records = FNexusCapabilityRegistry::Get().GetAllRecords();
        ~FRestoreRegistry() {
            FNexusCapabilityRegistry::Get().Reset();
            for (const auto& Record : Records) {
                const FString File = TEXT("Private/Capabilities/") + Record.SourceRelDir + TEXT("/Restore.cpp");
                FNexusCapabilityRegistry::Get().Register(Record.Instance, *File);
            }
        }
    } Restore;
	if (!FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("GetEditorBatchProbe")))
		FNexusCapabilityRegistry::Get().Register(MakeShared<FNexusEditorBatchProbeCapability>());
	GNexusBatchProbeCalls = 0;
	auto First = MakeShared<FJsonObject>(); First->SetStringField(TEXT("Capability"), TEXT("GetEditorBatchProbe"));
	auto Second = MakeShared<FJsonObject>(); Second->SetStringField(TEXT("Capability"), TEXT("GetEditorSlate"));
	auto Args = MakeShared<FJsonObject>(); Args->SetArrayField(TEXT("Calls"), {MakeShared<FJsonValueObject>(First), MakeShared<FJsonValueObject>(Second)});
	auto Tool = FNexusMcpToolRegistry::Get().CreateTool(TEXT("CallCapability"));
	if (!TestTrue(TEXT("CallCapability exists"), Tool.IsValid())) return false;
	const auto Result = Tool->Execute(Args);
	TestTrue(TEXT("Non-batchable item rejects batch"), Result.bIsError);
	TestEqual(TEXT("Earlier item must not execute"), GNexusBatchProbeCalls, 0);
	return true;
}
