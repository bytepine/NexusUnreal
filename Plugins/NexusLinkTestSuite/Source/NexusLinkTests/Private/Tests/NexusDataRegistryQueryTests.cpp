// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS && WITH_NEXUS_TEST_DATA_REGISTRY
#include "NexusCapabilityRegistry.h"
#include "NexusReliabilityTestTypes.h"
#include "Utils/NexusJsonUtils.h"
#include "DataRegistry.h"
#include "DataRegistrySubsystem.h"
#include "DataRegistrySource_DataTable.h"
#include "UObject/UnrealType.h"
#include "Engine/DataTable.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusDataRegistryQueryTest, "NexusLink.DataRegistry.Query", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusDataRegistryQueryTest::RunTest(const FString&)
{
    UDataRegistrySubsystem* Subsystem = UDataRegistrySubsystem::Get();
    const FCapRecord* Capability = FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("GetProjectDataRegistry"));
    if (!Subsystem || !Capability) { AddError(TEXT("DataRegistry capability/subsystem missing")); return false; }
    UDataRegistry* Registry = NewObject<UDataRegistry>(GetTransientPackage(), MakeUniqueObjectName(GetTransientPackage(), UDataRegistry::StaticClass(), TEXT("NexusTestRegistry")));
    UDataTable* Table = NewObject<UDataTable>(); Table->RowStruct = FNexusReliabilityTestRow::StaticStruct();
    FNexusReliabilityTestRow Row; Row.Count = 42; Row.Label = TEXT("Nexus registry row"); Table->AddRow(TEXT("EntryA"), Row);
    // 只构造本用例自己的内存 Registry，不重置现有系统或改扫描配置。
    auto TypeProperty = FindFProperty<FNameProperty>(Registry->GetClass(), TEXT("RegistryType"));
    auto StructProperty = FindFProperty<FObjectPropertyBase>(Registry->GetClass(), TEXT("ItemStruct"));
    auto SourceProperty = FindFProperty<FArrayProperty>(Registry->GetClass(), TEXT("DataSources"));
    if (!TypeProperty || !StructProperty || !SourceProperty) { AddError(TEXT("Registry fixture properties missing")); return false; }
    const FName RegistryName(*Registry->GetName()); TypeProperty->SetPropertyValue_InContainer(Registry, RegistryName);
    StructProperty->SetObjectPropertyValue_InContainer(Registry, FNexusReliabilityTestRow::StaticStruct());
    UDataRegistrySource_DataTable* Source = NewObject<UDataRegistrySource_DataTable>(Registry); Source->SourceTable = Table;
    FScriptArrayHelper Sources(SourceProperty, SourceProperty->ContainerPtrToValuePtr<void>(Registry)); const int32 SourceIndex = Sources.AddValue();
    CastFieldChecked<FObjectPropertyBase>(SourceProperty->Inner)->SetObjectPropertyValue(Sources.GetRawPtr(SourceIndex), Source);
    const FSoftObjectPath Path(Registry); Subsystem->LoadRegistryPath(Path);
    TestTrue(TEXT("Fixture registered"), Subsystem->GetRegistryForType(RegistryName) == Registry);
    for (const FString& Section : {TEXT("Registries"), TEXT("Info"), TEXT("Schema"), TEXT("Items"), TEXT("DataSources"), TEXT("RuntimeSources"), TEXT("Values")}) {
        auto Args = MakeShared<FJsonObject>(); Args->SetStringField(TEXT("RegistryName"), RegistryName.ToString());
        Args->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(Section)});
        Args->SetArrayField(TEXT("ItemNames"), {MakeShared<FJsonValueString>(TEXT("EntryA")), MakeShared<FJsonValueString>(TEXT("Missing"))});
        FCapabilityResult Result = Capability->Instance->Run(Args); TestFalse(Section + TEXT(" has no errors"), Result.HasErrors());
        if (!Result.Entries.Num()) { AddError(TEXT("No registry result")); continue; }
        auto Detail = Result.Entries[0]->AsObject();
        if (Section == TEXT("Items")) TestTrue(TEXT("Entry IDs read back"), FNexusJsonUtils::SerializeCondensed(Detail).Contains(TEXT("EntryA")));
        if (Section == TEXT("Values")) {
            const auto& Values = Detail->GetArrayField(TEXT("Values"));
            TestEqual(TEXT("Both requested entries returned"), Values.Num(), 2);
            auto Present = Values[0]->AsObject(); TestTrue(TEXT("Precached table row available"), Present->GetBoolField(TEXT("bCached")));
            TestTrue(TEXT("Cached value is actual source value"), FNexusJsonUtils::SerializeCondensed(Present).Contains(TEXT("42")));
            TestFalse(TEXT("Missing is explicitly uncached"), Values[1]->AsObject()->GetBoolField(TEXT("bCached")));
        }
    }
    Subsystem->IgnoreRegistryPath(Path); Registry->Deinitialize(); return true;
}
#endif
