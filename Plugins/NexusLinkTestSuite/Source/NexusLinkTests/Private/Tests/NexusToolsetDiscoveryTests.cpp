// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS && WITH_NEXUS_TEST_TOOLSETS
#include "NexusCapabilityRegistry.h"
#include "ToolsetRegistry/ToolsetRegistrySubsystem.h"
#include "ToolsetRegistry/ToolsetRegistry.h"

/** 仅注册本用例的内存 Handler；不改 Registry 全局过滤或工程设置。 */
class FNexusDiscoveryFixtureToolset final : public UE::ToolsetRegistry::FToolset
{
public:
    virtual FString GetToolsetName() const override { return TEXT("NexusFixture.CustomDiscovery"); }
    virtual FString GetToolsetVersion() const override { return TEXT("1"); }
    virtual FString GetToolsetDescription() const override { return TEXT("Read-only discovery fixture"); }
protected:
    virtual TFuture<TValueOrError<FString, FString>> ExecuteToolInternal(const FString&, const FString&) override { return {}; }
    virtual FString GetJsonSchemaInternal() const override
    {
        return TEXT(R"({"name":"NexusFixture.CustomDiscovery","version":"1","description":"Fixture","tools":[{"name":"NexusFixture.CustomDiscovery.Visible","description":"Visible fixture","inputSchema":{"type":"object"}},{"name":"NexusFixture.CustomDiscovery.Hidden","description":"Hidden fixture","inputSchema":{"type":"object"}}]})");
    }
};
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusToolsetDiscoveryTest, "NexusLink.Toolsets.DiscoveryFilters", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusToolsetDiscoveryTest::RunTest(const FString&)
{
    auto Subsystem = UToolsetRegistrySubsystem::Get();
    const FCapRecord* Capability = FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("GetProjectToolsets"));
    if (Subsystem.HasError() || !Capability) { AddError(TEXT("Discovery capability/Registry unavailable")); return false; }
    auto& Registry = Subsystem.GetValue()->ToolsetRegistry; auto Fixture = MakeShared<FNexusDiscoveryFixtureToolset>();
    if (!Registry.RegisterToolset(Fixture)) { AddError(TEXT("Fixture registration failed")); return false; }
    auto Query = [&](const FString& Section, const FString& ToolName = FString())
    {
        auto Args = MakeShared<FJsonObject>(); Args->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(Section)});
        Args->SetStringField(TEXT("ToolsetName"), Fixture->GetToolsetName()); Args->SetStringField(TEXT("ToolName"), ToolName); Args->SetStringField(TEXT("NameFilter"), Fixture->GetToolsetName());
        return Capability->Instance->Run(Args);
    };
    auto Listed = Query(TEXT("Tools"));
    TestFalse(TEXT("Initial listing succeeds"), Listed.HasErrors());
    if (Listed.Entries.Num()) TestEqual(TEXT("Both fixture tools initially visible"), Listed.Entries[0]->AsObject()->GetArrayField(TEXT("Tools")).Num(), 2);
    Fixture->SetNameFilters({TEXT("NexusFixture.CustomDiscovery.Hidden")}, {});
    Listed = Query(TEXT("Tools"));
    TestFalse(TEXT("Filtered listing succeeds"), Listed.HasErrors());
    if (Listed.Entries.Num()) TestEqual(TEXT("Blocked tool is hidden"), Listed.Entries[0]->AsObject()->GetArrayField(TEXT("Tools")).Num(), 1);
    TestTrue(TEXT("Blocked schema cannot be read"), Query(TEXT("Schema"), TEXT("NexusFixture.CustomDiscovery.Hidden")).HasErrors());
    TestFalse(TEXT("Allowed schema remains readable"), Query(TEXT("Schema"), TEXT("NexusFixture.CustomDiscovery.Visible")).HasErrors());
    Fixture->SetEnabled(false); TestTrue(TEXT("Disabled toolset cannot be queried"), Query(TEXT("Tools")).HasErrors());
    Listed = Query(TEXT("Toolsets"));
    if (Listed.Entries.Num()) TestEqual(TEXT("Disabled toolset not discovered"), Listed.Entries[0]->AsObject()->GetArrayField(TEXT("Toolsets")).Num(), 0);
    Registry.UnregisterToolset(Fixture);
    TestTrue(TEXT("Unregistered schema cannot be read"), Query(TEXT("Schema"), TEXT("NexusFixture.CustomDiscovery.Visible")).HasErrors());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusToolsetLegacySyncTest, "NexusLink.Toolsets.LegacySync", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusToolsetLegacySyncTest::RunTest(const FString&)
{
    auto Subsystem = UToolsetRegistrySubsystem::Get();
    const FCapRecord* Capability = FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("GetProjectPlugins"));
    if (Subsystem.HasError() || !Capability) { AddError(TEXT("Native registry/capability unavailable")); return false; }
    auto& Registry = Subsystem.GetValue()->ToolsetRegistry;
    if (!Registry.Find(TEXT("PluginToolset.PluginToolset")).IsValid()) { AddWarning(TEXT("PluginToolset not enabled; native sync test skipped")); return true; }
    auto Args = MakeShared<FJsonObject>(); Args->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("Plugins"))});
    auto Before = Capability->Instance->Run(Args); TestFalse(TEXT("Synchronous native listing succeeds"), Before.HasErrors());
    if (Before.Entries.Num()) TestEqual(TEXT("Native backend is reported"), Before.Entries[0]->AsObject()->GetStringField(TEXT("Backend")), FString(TEXT("OfficialToolset")));
    const FString Pattern = TEXT("PluginToolset.PluginToolset.ListDiscoveredPlugins");
    const bool bPreviouslyBlocked = Registry.GetBlockedNames().Contains(Pattern);
    if (!bPreviouslyBlocked) Registry.AddBlockedName(Pattern);
    auto Blocked = Capability->Instance->Run(Args);
    if (!bPreviouslyBlocked) Registry.RemoveBlockedName(Pattern);
    TestTrue(TEXT("Native filtering fails without compatibility retry"), Blocked.HasErrors());
    auto After = Capability->Instance->Run(Args); TestFalse(TEXT("Native listing recovers after filter restore"), After.HasErrors());
    return true;
}
#endif
