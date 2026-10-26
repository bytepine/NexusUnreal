// Copyright byteyang. All Rights Reserved.
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "BehaviorTree/BTDecorator.h"
#include "NexusBehaviorRetestTypes.generated.h"

UCLASS()
class UNexusRetestCondition : public UBTDecorator
{
	GENERATED_BODY()
	virtual bool CalculateRawConditionValue(UBehaviorTreeComponent& Owner, uint8* Memory) const override;
};

/** Opt-in, standalone BT fixture. No project GameMode configuration is needed. */
UCLASS()
class ANexusBehaviorRetestPawn : public APawn
{
	GENERATED_BODY()
public:
	UPROPERTY(EditAnywhere, Category="Retest") bool bHoldBlocked = false;
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
	UPROPERTY() class AAIController* TestController;
};
