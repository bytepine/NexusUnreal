// Copyright byteyang. All Rights Reserved.

#include "Misc/AutomationTest.h"

#if WITH_EDITOR
#include "NexusCapabilityRegistry.h"
#include "Dom/JsonObject.h"
#include "Editor.h"
#include "Engine/Level.h"
#include "Engine/Selection.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Misc/PackageName.h"
#include "Misc/ScopeExit.h"
#include "UObject/Package.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusEditorContextSelectionTest,
	"NexusLink.EditorContext.SelectionActorsSublevel",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusEditorContextSelectionTest::RunTest(const FString& Parameters)
{
	UWorld* EditorWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
	USelection* Selection = GEditor ? GEditor->GetSelectedActors() : nullptr;
	if (!TestNotNull(TEXT("Editor world"), EditorWorld) || !TestNotNull(TEXT("Actor selection"), Selection)) return false;
	const bool bOriginalDirty = EditorWorld->GetOutermost()->IsDirty();
	TArray<UObject*> OriginalSelection;
	Selection->GetSelectedObjects(OriginalSelection);
	const FString PackagePath = TEXT("/Game/_McpTest/Selection_") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
	UPackage* Package = CreatePackage(*PackagePath);
	UWorld* ChildWorld = UWorld::CreateWorld(EWorldType::Editor, false, TEXT("Selection"), Package);
	if (!TestNotNull(TEXT("Child world"), ChildWorld)) return false;
	ULevel* ChildLevel = ChildWorld->PersistentLevel;
	EditorWorld->AddLevel(ChildLevel);
	ChildLevel->OwningWorld = EditorWorld;
	ON_SCOPE_EXIT
	{
		Selection->DeselectAll();
		for (UObject* Original : OriginalSelection) Selection->Select(Original);
		EditorWorld->RemoveLevel(ChildLevel);
		ChildLevel->OwningWorld = ChildWorld;
		Package->SetDirtyFlag(false);
		ChildWorld->DestroyWorld(false);
		EditorWorld->GetOutermost()->SetDirtyFlag(bOriginalDirty);
	};
	FActorSpawnParameters SpawnParams;
	SpawnParams.OverrideLevel = ChildLevel;
	AActor* Actor = EditorWorld->SpawnActor<AActor>(FVector::ZeroVector, FRotator::ZeroRotator, SpawnParams);
	if (!TestNotNull(TEXT("Child actor"), Actor)) return false;
	Selection->DeselectAll();
	Selection->Select(Actor);
	const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("GetEditorContext"));
	if (!TestNotNull(TEXT("GetEditorContext registered"), Record)) return false;
	auto Args = MakeShared<FJsonObject>();
	Args->SetArrayField(TEXT("Sections"), {MakeShared<FJsonValueString>(TEXT("SelectionActors"))});
	Args->SetNumberField(TEXT("Limit"), 1);
	const FCapabilityResult Read = Record->Instance->Run(Args);
	if (!TestFalse(TEXT("Read selection"), Read.HasErrors()) || !TestEqual(TEXT("One section"), Read.Entries.Num(), 1)) return false;
	const TArray<TSharedPtr<FJsonValue>>& Actors = Read.Entries[0]->AsObject()->GetArrayField(TEXT("Actors"));
	if (!TestEqual(TEXT("One selected actor"), Actors.Num(), 1)) return false;
	TestTrue(TEXT("Fixture actor shares the editor world"), Actor->GetWorld() == EditorWorld);
	TestEqual(TEXT("Selection reports owning level package short name"), Actors[0]->AsObject()->GetStringField(TEXT("Level")), FPackageName::GetShortName(PackagePath));
	return true;
}
#endif
