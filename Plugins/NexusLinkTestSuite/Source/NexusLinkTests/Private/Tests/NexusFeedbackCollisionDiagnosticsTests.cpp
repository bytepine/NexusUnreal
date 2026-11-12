// Copyright byteyang. All Rights Reserved.
#include "CoreMinimal.h"
#include "Misc/AutomationTest.h"
#if WITH_EDITOR
#include "NexusCapabilityRegistry.h"
#include "Editor.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Components/StaticMeshComponent.h"
#include "PhysicsEngine/BodySetup.h"
#include "Utils/NexusAssetUtils.h"
#include "Misc/Guid.h"
#include "Misc/ScopeExit.h"
#include "Dom/JsonValue.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusFeedbackLiveCollisionTest, "NexusLink.FeedbackNov12.LiveCollision", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusFeedbackLiveCollisionTest::RunTest(const FString& Parameters)
{
	UWorld* World=GEditor?GEditor->GetEditorWorldContext().World():nullptr;
	UStaticMesh* Source=LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube"));
	const auto* Manage=FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("ManageAssetStaticMesh"));
	const auto* Scene=FNexusCapabilityRegistry::Get().FindRecordByName(TEXT("GetEditorScene"));
	if (!TestTrue(TEXT("Fixture dependencies"),World && Source && Manage && Scene)) return false;
	UPackage* Package=CreatePackage(*(TEXT("/Game/_McpTest/LiveCollision_")+FGuid::NewGuid().ToString(EGuidFormats::Digits)));
	UStaticMesh* Mesh=DuplicateObject<UStaticMesh>(Source,Package,TEXT("Mesh"));
	if (!TestNotNull(TEXT("Mesh copy"),Mesh)) return false;
	const bool bWasDirty=World->GetOutermost()->IsDirty();
	AStaticMeshActor* Actor=World->SpawnActor<AStaticMeshActor>(FVector(100000,100000,100000),FRotator::ZeroRotator);
	if (!TestNotNull(TEXT("Live actor"),Actor)) return false;
	ON_SCOPE_EXIT { World->EditorDestroyActor(Actor,true); World->GetOutermost()->SetDirtyFlag(bWasDirty); Package->SetDirtyFlag(false); };
	UStaticMeshComponent* Component=Actor->GetStaticMeshComponent(); Component->SetStaticMesh(Mesh);
	auto Args=MakeShared<FJsonObject>(); Args->SetStringField(TEXT("AssetPath"),Mesh->GetPathName());
	auto Op=MakeShared<FJsonObject>(); Op->SetStringField(TEXT("Action"),TEXT("SetCollisionTraceFlag")); Op->SetStringField(TEXT("CollisionTraceFlag"),TEXT("UseComplexAsSimple"));
	Args->SetArrayField(TEXT("Operations"),{MakeShared<FJsonValueObject>(Op)});
	const auto Changed=Manage->Instance->Run(Args);
	if (!TestFalse(TEXT("Collision setter succeeds"),Changed.HasErrors()) || !Changed.Entries.Num()) return false;
	TestTrue(TEXT("Existing registered component was refreshed"),Changed.Entries[0]->AsObject()->GetNumberField(TEXT("RefreshedComponentCount"))>=1);
	const UBodySetup* Body=FNexusAssetUtils::GetStaticMeshBodySetup(Mesh);
	TestTrue(TEXT("Instance uses recooked body setup"),Body && Component->GetBodySetup()==Body && Body->CollisionTraceFlag==CTF_UseComplexAsSimple);
	Args=MakeShared<FJsonObject>(); Args->SetStringField(TEXT("Action"),TEXT("Collision")); Args->SetStringField(TEXT("ComponentPath"),Component->GetPathName());
	const auto Read=Scene->Instance->Run(Args);
	if (!TestFalse(TEXT("Component physics diagnostics"),Read.HasErrors()) || !Read.Entries.Num()) return false;
	const auto Item=Read.Entries[0]->AsObject()->GetObjectField(TEXT("Result"))->GetObjectField(TEXT("CompatibilityResult"))->GetArrayField(TEXT("Items"))[0]->AsObject();
	TestTrue(TEXT("Exact component identity"),Item->GetStringField(TEXT("ComponentPath"))==Component->GetPathName());
	TestEqual(TEXT("Physics state reflects component"),Item->GetBoolField(TEXT("bPhysicsStateCreated")),Component->IsPhysicsStateCreated());
	return true;
}
#endif
