// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "SideScrollingAIController.generated.h"

class UStateTreeComponent;

/**
 *  A basic AI Controller capable of running StateTree
 */
UCLASS(abstract)
class ASideScrollingAIController : public AAIController
{
	GENERATED_BODY()
	
	/** StateTree Component（5.4+ 实际创建 UStateTreeAIComponent） */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "AI", meta = (AllowPrivateAccess = "true"))
	UStateTreeComponent* StateTreeAI;

public:

	/** Constructor */
	ASideScrollingAIController();
};
