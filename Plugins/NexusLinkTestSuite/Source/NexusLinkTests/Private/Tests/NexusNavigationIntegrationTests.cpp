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
#include "GameFramework/WorldSettings.h"
#include "Engine/EngineBaseTypes.h"
#include "Components/StaticMeshComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "AIController.h"
#include "Navigation/PathFollowingComponent.h"
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
	ON_SCOPE_EXIT
	{
#if ENGINE_MAJOR_VERSION > 5 || (ENGINE_MAJOR_VERSION == 5 && ENGINE_MINOR_VERSION >= 5)
		World->EndPlay(EEndPlayReason::Quit);
#else
		World->BeginTearingDown();
#endif
		GEngine->DestroyWorldContext(World); World->GetOutermost()->SetDirtyFlag(false); World->DestroyWorld(false);
	};
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
	Args->SetStringField(TEXT("FilterClass"), UNexusNavigationRejectAllFilter::StaticClass()->GetPathName());
	const auto Filtered = NavigationIntegrationCall(TEXT("GetNavigationPath"), Args);
	if (!TestFalse(TEXT("Custom filter query"), Filtered.HasErrors())) return false;
	TestFalse(TEXT("Excluded walkable area changes path result"), Filtered.Entries[0]->AsObject()->GetBoolField(TEXT("bPathFound")));
	Args->RemoveField(TEXT("FilterClass"));
	UWorld* OtherWorld = UWorld::CreateWorld(EWorldType::Game, false, FName(*World->GetName()));
	GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(OtherWorld);
	bool bOtherContextAlive = true;
	ON_SCOPE_EXIT { if (bOtherContextAlive) GEngine->DestroyWorldContext(OtherWorld); OtherWorld->GetOutermost()->SetDirtyFlag(false); OtherWorld->DestroyWorld(false); };
	Args->SetStringField(TEXT("WorldName"), World->GetName());
	TestTrue(TEXT("Duplicate world names are rejected"), NavigationIntegrationCall(TEXT("GetNavigationPath"), Args).HasErrors());
	OtherWorld->Rename(TEXT("NexusOtherNavigationWorld"), nullptr, REN_DontCreateRedirectors);
	Args->SetStringField(TEXT("WorldName"), OtherWorld->GetName());
	const auto OtherPath = NavigationIntegrationCall(TEXT("GetNavigationPath"), Args);
	if (TestFalse(TEXT("Exact second world selected"), OtherPath.HasErrors())) TestFalse(TEXT("Second world has no navigation"), OtherPath.Entries[0]->AsObject()->GetBoolField(TEXT("bNavigationAvailable")));
	Args->SetStringField(TEXT("WorldName"), World->GetName());
	const auto SelectedPath = NavigationIntegrationCall(TEXT("GetNavigationPath"), Args);
	if (!TestFalse(TEXT("WorldName selects the navigable world"), SelectedPath.HasErrors())) return false;
	TestTrue(TEXT("Selected world still has its path"), SelectedPath.Entries[0]->AsObject()->GetBoolField(TEXT("bPathFound")));
	// AI 的运行时世界解析也要求唯一；完成只读多世界验证后注销额外世界上下文。
	GEngine->DestroyWorldContext(OtherWorld);
	bOtherContextAlive = false;
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
	World->InitializeActorsForPlay(FURL());
	World->GetWorldSettings()->NotifyBeginPlay();
	World->BeginPlay();
	const FVector AgentLocation = Pawn->GetNavAgentLocation();
	auto Move = MakeShared<FJsonObject>(); Move->SetStringField(TEXT("ActorName"), Pawn->GetName()); Move->SetStringField(TEXT("Action"), TEXT("MoveTo")); Move->SetNumberField(TEXT("X"), AgentLocation.X); Move->SetNumberField(TEXT("Y"), AgentLocation.Y); Move->SetNumberField(TEXT("Z"), AgentLocation.Z); Move->SetBoolField(TEXT("bProjectEnd"), false);
	const auto AlreadyThere = NavigationIntegrationCall(TEXT("InteractRuntimeActorAI"), Move);
	if (!TestFalse(TEXT("Move request accepted"), AlreadyThere.HasErrors())) return false;
	TestEqual(TEXT("Already at goal is explicit"), AlreadyThere.Entries[0]->AsObject()->GetStringField(TEXT("Outcome")), FString(TEXT("AlreadyAtGoal")));
	Move->SetNumberField(TEXT("X"), 500); Move->SetNumberField(TEXT("Z"), 0); Move->SetBoolField(TEXT("bProjectEnd"), true);
	const auto InProgress = NavigationIntegrationCall(TEXT("InteractRuntimeActorAI"), Move);
	if (!TestFalse(TEXT("Longer move request"), InProgress.HasErrors())) return false;
	TestEqual(TEXT("Acceptance is pending, not arrival"), InProgress.Entries[0]->AsObject()->GetStringField(TEXT("Outcome")), FString(TEXT("Pending")));
	const FAIRequestID FirstId = Controller->GetCurrentMoveRequestID();
	Move->SetNumberField(TEXT("X"), 700);
	const auto Second = NavigationIntegrationCall(TEXT("InteractRuntimeActorAI"), Move);
	if (!TestFalse(TEXT("Consecutive move accepted"), Second.HasErrors())) return false;
	const FAIRequestID SecondId = Controller->GetCurrentMoveRequestID();
	TestTrue(TEXT("New move has a distinct request ID"), FirstId != SecondId);
	Controller->GetPathFollowingComponent()->OnRequestFinished.Broadcast(FirstId, FPathFollowingResult(EPathFollowingResult::Aborted));
	auto StatusArgs = MakeShared<FJsonObject>(); StatusArgs->SetStringField(TEXT("ActorName"), Pawn->GetName());
	const auto AfterOldCompletion = NavigationIntegrationCall(TEXT("GetRuntimeActorAI"), StatusArgs);
	TestEqual(TEXT("Old request completion cannot finish the new request"), AfterOldCompletion.Entries[0]->AsObject()->GetStringField(TEXT("Outcome")), FString(TEXT("Pending")));
	TestEqual(TEXT("Tracked ID stays on the second request"), static_cast<uint32>(AfterOldCompletion.Entries[0]->AsObject()->GetNumberField(TEXT("TrackedRequestId"))), static_cast<uint32>(SecondId));
	// 同步 Automation 的引擎帧号不递增；显式运行真实组件，避免 TickTaskManager 同帧去重。
	for (int32 Frame = 0; Frame < 500 && Controller->GetMoveStatus() != EPathFollowingStatus::Idle; ++Frame)
	{
		World->Tick(LEVELTICK_All, 0.02f);
		Controller->GetPathFollowingComponent()->TickComponent(0.02f, LEVELTICK_All, nullptr);
		Pawn->GetCharacterMovement()->TickComponent(0.02f, LEVELTICK_All, nullptr);
	}
	const auto Arrived = NavigationIntegrationCall(TEXT("GetRuntimeActorAI"), StatusArgs);
	AddInfo(FString::Printf(TEXT("Arrival: position=%s velocity=%s initialized=%d begun=%d result=%s"), *Pawn->GetActorLocation().ToString(), *Pawn->GetVelocity().ToString(), World->AreActorsInitialized(), World->HasBegunPlay(), *FNexusJsonUtils::SerializeCondensed(Arrived.Entries[0]->AsObject())));
	TestEqual(TEXT("Real movement finishes successfully"), Arrived.Entries[0]->AsObject()->GetStringField(TEXT("Outcome")), FString(TEXT("Success")));
	TestTrue(TEXT("Pawn actually approaches requested goal"), FVector::Dist2D(Pawn->GetActorLocation(), FVector(700,0,0)) < 100);
	Move->SetNumberField(TEXT("X"), 20000); Move->SetBoolField(TEXT("bAllowPartialPath"), false);
	const auto Rejected = NavigationIntegrationCall(TEXT("InteractRuntimeActorAI"), Move);
	if (!TestFalse(TEXT("Rejected navigation request returns structured outcome"), Rejected.HasErrors())) return false;
	TestEqual(TEXT("Off-mesh move is rejected"), Rejected.Entries[0]->AsObject()->GetStringField(TEXT("Outcome")), FString(TEXT("Rejected")));
	Move->SetNumberField(TEXT("X"), -500);
	TestFalse(TEXT("Start a move to stop"), NavigationIntegrationCall(TEXT("InteractRuntimeActorAI"), Move).HasErrors());
	Move->SetStringField(TEXT("Action"), TEXT("Stop"));
	TestFalse(TEXT("Stop command"), NavigationIntegrationCall(TEXT("InteractRuntimeActorAI"), Move).HasErrors());
	const auto Status = NavigationIntegrationCall(TEXT("GetRuntimeActorAI"), StatusArgs);
	if (TestFalse(TEXT("Read AI state"), Status.HasErrors()))
	{
		TestEqual(TEXT("Stopped movement is Idle"), Status.Entries[0]->AsObject()->GetStringField(TEXT("MoveStatus")), FString(TEXT("Idle")));
		TestEqual(TEXT("Stop completion is captured"), Status.Entries[0]->AsObject()->GetStringField(TEXT("Outcome")), FString(TEXT("Aborted")));
	}
	return true;
}
#endif
