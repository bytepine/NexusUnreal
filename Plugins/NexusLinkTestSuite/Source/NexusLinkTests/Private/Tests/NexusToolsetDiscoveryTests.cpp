// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS && WITH_EDITOR
#include "NexusCapabilityRegistry.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusIndependentDiscoveryTest, "NexusLink.Independent.DiscoveryContract", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusIndependentDiscoveryTest::RunTest(const FString&)
{
    const FCapRecord* Capability=FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("GetProjectToolsets"));
    if (!TestNotNull(TEXT("Independent discovery is registered"),Capability)) return false;
    auto Args=MakeShared<FJsonObject>(); Args->SetArrayField(TEXT("Sections"),{MakeShared<FJsonValueString>(TEXT("Toolsets"))});
    auto Listed=Capability->Instance->Run(Args);
    if (!TestFalse(TEXT("Groups can be discovered without an external registry"),Listed.HasErrors()) || !Listed.Entries.Num()) return false;
    const auto& Groups=Listed.Entries[0]->AsObject()->GetArrayField(TEXT("Toolsets"));
    if (!TestTrue(TEXT("At least one independent group exists"),Groups.Num()>0)) return false;
    const FString Group=Groups[0]->AsObject()->GetStringField(TEXT("Name"));
    TestTrue(TEXT("Group belongs to NexusLink"),Group.StartsWith(TEXT("NexusLink.")));
    Args->SetArrayField(TEXT("Sections"),{MakeShared<FJsonValueString>(TEXT("Tools"))}); Args->SetStringField(TEXT("ToolsetName"),Group);
    auto Tools=Capability->Instance->Run(Args);
    if (!TestFalse(TEXT("Group tools can be read"),Tools.HasErrors()) || !Tools.Entries.Num()) return false;
    const auto& Rows=Tools.Entries[0]->AsObject()->GetArrayField(TEXT("Tools"));
    if (!TestTrue(TEXT("Discovered group has tools"),Rows.Num()>0)) return false;
    const FString Name=Rows[0]->AsObject()->GetStringField(TEXT("Name"));
    Args->SetArrayField(TEXT("Sections"),{MakeShared<FJsonValueString>(TEXT("Schema"))}); Args->SetStringField(TEXT("ToolName"),Name);
    auto Schema=Capability->Instance->Run(Args);
    if (!TestFalse(TEXT("Discovered schema can be read"),Schema.HasErrors()) || !Schema.Entries.Num()) return false;
    TestEqual(TEXT("Schema names its capability"),Schema.Entries[0]->AsObject()->GetObjectField(TEXT("Schema"))->GetStringField(TEXT("Name")),Name);
    Args->SetStringField(TEXT("ToolName"),TEXT("MissingCapability"));
    TestTrue(TEXT("Unknown schema is rejected"),Capability->Instance->Run(Args).HasErrors());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusIndependentSettingsTest, "NexusLink.Independent.SettingsAndPlugins", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusIndependentSettingsTest::RunTest(const FString&)
{
    for (const FString& Name : {TEXT("GetProjectSettings"),TEXT("GetProjectPlugins")}) {
        const FCapRecord* Capability=FNexusCapabilityRegistry::Get().FindRecordByName(Name);
        if (!TestNotNull(Name,Capability)) return false;
        auto Args=MakeShared<FJsonObject>(); Args->SetArrayField(TEXT("Sections"),{MakeShared<FJsonValueString>(Name==TEXT("GetProjectSettings")?TEXT("Containers"):TEXT("Plugins"))});
        auto Result=Capability->Instance->Run(Args);
        if (!TestFalse(Name+TEXT(" succeeds synchronously"),Result.HasErrors()) || !Result.Entries.Num()) return false;
        TestEqual(TEXT("Independent backend"),Result.Entries[0]->AsObject()->GetStringField(TEXT("Backend")),FString(TEXT("Independent")));
        TestFalse(TEXT("Synchronous reads do not create async operations"),Result.Entries[0]->AsObject()->HasField(TEXT("OperationId")));
    }
    return true;
}
#endif
