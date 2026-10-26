// Copyright byteyang. All Rights Reserved.
#include "Diagnostics/NexusBehaviorRetestTypes.h"
#include "AIController.h"
#include "BehaviorTree/BehaviorTree.h"
#include "BehaviorTree/BehaviorTreeComponent.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "BehaviorTree/BlackboardData.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Bool.h"
#include "BehaviorTree/Blackboard/BlackboardKeyType_Int.h"
#include "BehaviorTree/Composites/BTComposite_Selector.h"
#include "BehaviorTree/Composites/BTComposite_Sequence.h"
#include "BehaviorTree/Tasks/BTTask_Wait.h"
#include "BehaviorTree/Tasks/BTTask_RunBehavior.h"
#include "Engine/World.h"
#include "UObject/UnrealType.h"

bool UNexusRetestCondition::CalculateRawConditionValue(UBehaviorTreeComponent& Owner, uint8* Memory) const
{
	const ANexusBehaviorRetestPawn* Pawn = Owner.GetAIOwner() ? Cast<ANexusBehaviorRetestPawn>(Owner.GetAIOwner()->GetPawn()) : nullptr;
	return Pawn && !Pawn->bHoldBlocked && Owner.GetBlackboardComponent()->GetValueAsBool(TEXT("CanRun"));
}

void ANexusBehaviorRetestPawn::BeginPlay()
{
	Super::BeginPlay();
	if (!HasAuthority()) return;
	TestController = GetWorld()->SpawnActor<AAIController>();
	TestController->Possess(this);
	UBehaviorTree* Tree = NewObject<UBehaviorTree>(TestController, TEXT("RetestTree"));
	UBlackboardData* Parent = NewObject<UBlackboardData>(Tree, TEXT("ParentBlackboard"));
	FBlackboardEntry Condition;
	Condition.EntryName = TEXT("CanRun");
	Condition.KeyType = NewObject<UBlackboardKeyType_Bool>(Parent);
	Parent->Keys.Add(Condition);
	Parent->UpdateKeyIDs();
	UBlackboardData* Data = NewObject<UBlackboardData>(Tree, TEXT("Blackboard"));
	// New root data gets a persistent SelfActor key; inherit the parent's copy instead.
	Data->Keys.Reset();
	Data->Parent = Parent;
	FBlackboardEntry Local;
	Local.EntryName = TEXT("LocalCount");
	Local.KeyType = NewObject<UBlackboardKeyType_Int>(Data);
	Data->Keys.Add(Local);
	Data->UpdateKeyIDs();
	Tree->BlackboardAsset = Data;
	UBTComposite_Selector* Root = NewObject<UBTComposite_Selector>(Tree);
	Tree->RootNode = Root;
	for (int32 Index = 0; Index < 2; ++Index)
	{
		FBTCompositeChild Child;
		UBehaviorTree* NodeTree = Index == 0 ? NewObject<UBehaviorTree>(Tree, TEXT("AllowedSubtree")) : Tree;
		UBTTask_Wait* Wait = NewObject<UBTTask_Wait>(NodeTree);
		Wait->NodeName = Index == 0 ? TEXT("Allowed") : TEXT("Blocked");
		Wait->WaitTime = .05f;
		Wait->RandomDeviation = 0;
		Child.ChildTask = Wait;
		if (Index == 0)
		{
			NodeTree->BlackboardAsset = Data;
			UBTComposite_Sequence* SubRoot = NewObject<UBTComposite_Sequence>(NodeTree);
			NodeTree->RootNode = SubRoot;
			FBTCompositeChild SubChild;
			SubChild.ChildTask = Wait;
			SubRoot->Children.Add(SubChild);
			UBTTask_RunBehavior* RunSubtree = NewObject<UBTTask_RunBehavior>(Tree);
			FObjectPropertyBase* AssetProperty = FindFProperty<FObjectPropertyBase>(RunSubtree->GetClass(), TEXT("BehaviorAsset"));
			check(AssetProperty);
			AssetProperty->SetObjectPropertyValue_InContainer(RunSubtree, NodeTree);
			Child.ChildTask = RunSubtree;
			Child.Decorators.Add(NewObject<UNexusRetestCondition>(Tree));
		}
		Root->Children.Add(Child);
	}
	TestController->RunBehaviorTree(Tree);
}

void ANexusBehaviorRetestPawn::EndPlay(const EEndPlayReason::Type Reason)
{
	if (TestController) TestController->Destroy();
	Super::EndPlay(Reason);
}
