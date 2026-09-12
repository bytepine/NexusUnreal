// Copyright Epic Games, Inc. All Rights Reserved.


#include "SideScrollingAIController.h"
#include "NexusGameplayVersionCompat.h"
#if NG_UE_HAS_STATETREE_AI_COMPONENT
#include "Components/StateTreeAIComponent.h"
#else
#include "Components/StateTreeComponent.h"
#endif

ASideScrollingAIController::ASideScrollingAIController()
{
	// create the StateTree AI Component
#if NG_UE_HAS_STATETREE_AI_COMPONENT
	StateTreeAI = CreateDefaultSubobject<UStateTreeAIComponent>(TEXT("StateTreeAI"));
#else
	StateTreeAI = CreateDefaultSubobject<UStateTreeComponent>(TEXT("StateTreeAI"));
#endif
	check(StateTreeAI);

	// ensure we start the StateTree when we possess the pawn
	bStartAILogicOnPossess = true;

	// ensure we're attached to the possessed character.
	// this is necessary for EnvQueries to work correctly
	bAttachToPawn = true;
}
