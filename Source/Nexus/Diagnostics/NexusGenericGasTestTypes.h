// Copyright byteyang. All Rights Reserved.
#pragma once
#include "CoreMinimal.h"
#include "Abilities/GameplayAbility.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Pawn.h"
#include "NexusGenericGasTestTypes.generated.h"

// 独立测试夹具：由测试显式 Spawn，不依赖诊断 GameMode 或默认关卡。
UCLASS()
class UNexusGenericGasTestAbility : public UGameplayAbility
{
	GENERATED_BODY()
public:
	UNexusGenericGasTestAbility();
	virtual bool CanActivateAbility(FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info,
		const FGameplayTagContainer* Source = nullptr, const FGameplayTagContainer* Target = nullptr,
		FGameplayTagContainer* Failure = nullptr) const override;
	virtual void ActivateAbility(FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info,
		FGameplayAbilityActivationInfo Activation, const FGameplayEventData* Event) override;
};

UCLASS()
class ANexusGenericGasTestActor : public AActor
{
	GENERATED_BODY()
public:
	ANexusGenericGasTestActor();
	UPROPERTY(EditAnywhere) bool bRejectActivation = false;
	virtual void BeginPlay() override;
};

UCLASS()
class ANexusGenericGasTestPawn : public APawn
{
	GENERATED_BODY()
public:
	ANexusGenericGasTestPawn();
	UPROPERTY(EditAnywhere) bool bRejectActivation = false;
	virtual void BeginPlay() override;
};

UCLASS()
class ANexusGenericGasTestStatePawn : public APawn
{
	GENERATED_BODY()
public:
	UPROPERTY(EditAnywhere) bool bRejectActivation = false;
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
};
