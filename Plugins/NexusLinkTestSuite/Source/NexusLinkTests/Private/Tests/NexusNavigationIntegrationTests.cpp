// Copyright byteyang. All Rights Reserved.
#include "Misc/AutomationTest.h"
#if WITH_EDITOR && WITH_RECAST
#include "NexusCapabilityRegistry.h"
#include "NexusNavigationTestSystem.h"
#include "Utils/NexusJsonUtils.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/Character.h"
#include "AIController.h"
#include "NavigationSystem.h"
#include "NavigationData.h"
#include "NavMesh/RecastNavMesh.h"
#include "Misc/ScopeExit.h"

static FCapabilityResult NavigationIntegrationCall(const TCHAR* Name, const TSharedPtr<FJsonObject>& Args)
{
	const FCapRecord* Record = FNexusCapabilityRegistry::Get().FindRecordByName(Name);
	return Record ? Record->Instance->Run(Args) : FCapabilityResult::MakeFatal(TEXT("Missing capability"));
}
static TSharedPtr<FJsonObject> NavigationIntegrationPoint(double X, double Y = 0, double Z = 30)
{
	auto Point = MakeShared<FJsonObject>(); Point->SetNumberField(TEXT("X"), X); Point->SetNumberField(TEXT("Y"), Y); Point->SetNumberField(TEXT("Z"), Z); return Point;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusRealNavigationTest, "NexusLink.EditorRelated.RecastAndAI", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FNexusRealNavigationTest::RunTest(const FString& Parameters)
{
	UWorld* World = UWorld::CreateWorld(EWorldType::Editor, false);
	GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
	ON_SCOPE_EXIT { GEngine->DestroyWorldContext(World); World->GetOutermost()->SetDirtyFlag(false); World->DestroyWorld(false); };
	UNexusNavigationTestSystem* Navigation = NewObject<UNexusNavigationTestSystem>(World);
	World->SetNavigationSystem(Navigation);
	FNavDataConfig Small, Large;
	Small.Name = TEXT("Small"); Small.AgentRadius = 20; Small.AgentHeight = 100; Small.SetNavDataClass(ARecastNavMesh::StaticClass());
	Large.Name = TEXT("Large"); Large.AgentRadius = 80; Large.AgentHeight = 180; Large.SetNavDataClass(ARecastNavMesh::StaticClass());
	Navigation->OnWorldInitDone(FNavigationSystemRunMode::EditorMode);
	Navigation->ConfigureTestAgents({Small, Large});
	FNavigationBounds Bounds;
	Bounds.UniqueID = World->GetUniqueID(); Bounds.AreaBox = FBox(FVector(-1200,-1200,-150), FVector(1200,1200,500)); Bounds.Level = World->PersistentLevel; Bounds.SupportedAgents.MarkInitialized();
	Navigation->AddTestBounds(Bounds);
	AStaticMeshActor* Floor = World->SpawnActor<AStaticMeshActor>();
	UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
	if (!TestNotNull(TEXT("Engine cube fixture"), Cube) || !TestNotNull(TEXT("Floor fixture"), Floor)) return false;
	Floor->GetStaticMeshComponent()->SetStaticMesh(Cube);
	Floor->SetActorScale3D(FVector(20,20,1)); Floor->SetActorLocation(FVector(0,0,-50));
	Floor->GetStaticMeshComponent()->SetCanEverAffectNavigation(true);
	UNavigationSystemV1::OnActorRegistered(Floor);
	Navigation->Tick(0.01f);
	Navigation->Build();
	World->WorldType = EWorldType::Game;
	const FTransform Before = Floor->GetActorTransform();
	auto Args = MakeShared<FJsonObject>(); Args->SetStringField(TEXT("World"), TEXT("Play")); Args->SetStringField(TEXT("WorldName"), World->GetName());
	Args->SetObjectField(TEXT("Start"), NavigationIntegrationPoint(-400)); Args->SetObjectField(TEXT("End"), NavigationIntegrationPoint(400));
	Args->SetBoolField(TEXT("bProjectStart"), true); Args->SetBoolField(TEXT("bProjectEnd"), true); Args->SetNumberField(TEXT("AgentRadius"), 20); Args->SetNumberField(TEXT("AgentHeight"), 100);
	const auto SmallPath = NavigationIntegrationCall(TEXT("GetNavigationPath"), Args);
	if (!TestFalse(TEXT("Small agent query"), SmallPath.HasErrors())) return false;
	const auto Path = SmallPath.Entries[0]->AsObject();
	if (!TestTrue(TEXT("Real Recast path found"), Path->GetBoolField(TEXT("bPathFound")))) { AddInfo(FNexusJsonUtils::SerializeCondensed(Path)); return false; }
	const FString SmallData = Path->GetStringField(TEXT("NavData"));
	Args->SetNumberField(TEXT("AgentRadius"), 80); Args->SetNumberField(TEXT("AgentHeight"), 180);
	const auto LargePath = NavigationIntegrationCall(TEXT("GetNavigationPath"), Args);
	if (!TestFalse(TEXT("Large agent query"), LargePath.HasErrors())) return false;
	TestTrue(TEXT("Large agent can navigate"), LargePath.Entries[0]->AsObject()->GetBoolField(TEXT("bPathFound")));
	TestTrue(TEXT("Agent-specific nav data chosen"), SmallData != LargePath.Entries[0]->AsObject()->GetStringField(TEXT("NavData")));
	Args->SetObjectField(TEXT("End"), NavigationIntegrationPoint(20000));
	TestFalse(TEXT("Off-mesh destination rejected"), NavigationIntegrationCall(TEXT("GetNavigationPath"), Args).Entries[0]->AsObject()->GetBoolField(TEXT("bPathFound")));
	auto Projection = MakeShared<FJsonObject>(); Projection->SetStringField(TEXT("World"), TEXT("Play")); Projection->SetStringField(TEXT("WorldName"), World->GetName()); Projection->SetObjectField(TEXT("Point"), NavigationIntegrationPoint(0,0,150));
	const auto Projected = NavigationIntegrationCall(TEXT("GetNavigationPoint"), Projection);
	if (TestFalse(TEXT("Point projection query"), Projected.HasErrors())) TestTrue(TEXT("Point projected to real navmesh"), Projected.Entries[0]->AsObject()->GetBoolField(TEXT("bProjected")));
	TestTrue(TEXT("Queries never move floor"), Floor->GetActorTransform().Equals(Before));
	ACharacter* Pawn = World->SpawnActor<ACharacter>(FVector(0,0,96), FRotator::ZeroRotator);
	AAIController* Controller = World->SpawnActor<AAIController>();
	if (!TestNotNull(TEXT("AI pawn"), Pawn) || !TestNotNull(TEXT("AI controller"), Controller)) return false;
	Controller->Possess(Pawn);
	const FVector AgentLocation = Pawn->GetNavAgentLocation();
	auto Move = MakeShared<FJsonObject>(); Move->SetStringField(TEXT("ActorName"), Pawn->GetName()); Move->SetStringField(TEXT("Action"), TEXT("MoveTo")); Move->SetNumberField(TEXT("X"), AgentLocation.X); Move->SetNumberField(TEXT("Y"), AgentLocation.Y); Move->SetNumberField(TEXT("Z"), AgentLocation.Z); Move->SetBoolField(TEXT("bProjectEnd"), false);
	const auto AlreadyThere = NavigationIntegrationCall(TEXT("InteractRuntimeActorAI"), Move);
	if (!TestFalse(TEXT("Move request accepted"), AlreadyThere.HasErrors())) return false;
	TestEqual(TEXT("Already at goal is explicit"), AlreadyThere.Entries[0]->AsObject()->GetStringField(TEXT("Outcome")), FString(TEXT("AlreadyAtGoal")));
	Move->SetNumberField(TEXT("X"), 500); Move->SetNumberField(TEXT("Z"), 0); Move->SetBoolField(TEXT("bProjectEnd"), true);
	const auto InProgress = NavigationIntegrationCall(TEXT("InteractRuntimeActorAI"), Move);
	if (!TestFalse(TEXT("Longer move request"), InProgress.HasErrors())) return false;
	TestEqual(TEXT("Acceptance is pending, not arrival"), InProgress.Entries[0]->AsObject()->GetStringField(TEXT("Outcome")), FString(TEXT("Pending")));
	Move->SetStringField(TEXT("Action"), TEXT("Stop"));
	TestFalse(TEXT("Stop command"), NavigationIntegrationCall(TEXT("InteractRuntimeActorAI"), Move).HasErrors());
	auto StatusArgs = MakeShared<FJsonObject>(); StatusArgs->SetStringField(TEXT("ActorName"), Pawn->GetName());
	const auto Status = NavigationIntegrationCall(TEXT("GetRuntimeActorAI"), StatusArgs);
	if (TestFalse(TEXT("Read AI state"), Status.HasErrors()))
	{
		TestEqual(TEXT("Stopped movement is Idle"), Status.Entries[0]->AsObject()->GetStringField(TEXT("MoveStatus")), FString(TEXT("Idle")));
		TestEqual(TEXT("Stop completion is captured"), Status.Entries[0]->AsObject()->GetStringField(TEXT("Outcome")), FString(TEXT("Aborted")));
	}
	return true;
}
#endif
