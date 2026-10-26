// Copyright byteyang. All Rights Reserved.
#pragma once

#include "CoreMinimal.h"
#include "AbilitySystemInterface.h"
#include "AbilitySystemComponent.h"
#include "AttributeSet.h"
#include "Abilities/GameplayAbility.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "NexusGasDiagnosticTypes.generated.h"

/** 独立诊断场景的可复制资源。 */
UCLASS()
class UNexusDiagnosticAttributes : public UAttributeSet
{
	GENERATED_BODY()
public:
	UNexusDiagnosticAttributes();
	UPROPERTY(ReplicatedUsing=OnRep_Mana)
	FGameplayAttributeData Mana;
	UFUNCTION()
	void OnRep_Mana(const FGameplayAttributeData& OldValue);
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
};

UCLASS()
class UNexusDiagnosticCost : public UGameplayEffect
{
	GENERATED_BODY()
public:
	UNexusDiagnosticCost();
};

UCLASS()
class UNexusDiagnosticCooldown : public UGameplayEffect
{
	GENERATED_BODY()
public:
	UNexusDiagnosticCooldown();
};

/** 预测客户端可激活，服务器可通过测试字段单独拒绝。 */
UCLASS()
class UNexusDiagnosticAbility : public UGameplayAbility
{
	GENERATED_BODY()
public:
	UNexusDiagnosticAbility();
	virtual bool CanActivateAbility(FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info,
		const FGameplayTagContainer* SourceTags = nullptr, const FGameplayTagContainer* TargetTags = nullptr,
		FGameplayTagContainer* RelevantTags = nullptr) const override;
	virtual bool CheckCost(FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info, FGameplayTagContainer* Tags = nullptr) const override;
	virtual bool CheckCooldown(FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info, FGameplayTagContainer* Tags = nullptr) const override;
	virtual void ActivateAbility(FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info,
		FGameplayAbilityActivationInfo ActivationInfo, const FGameplayEventData* EventData) override;
};

UCLASS()
class UNexusDiagnosticServerAbility : public UNexusDiagnosticAbility
{
	GENERATED_BODY()
public:
	UNexusDiagnosticServerAbility();
};

UCLASS()
class ANexusDiagnosticCharacter : public ACharacter, public IAbilitySystemInterface
{
	GENERATED_BODY()
public:
	ANexusDiagnosticCharacter();
	UPROPERTY(VisibleAnywhere)
	UAbilitySystemComponent* AbilitySystem;
	UPROPERTY()
	UNexusDiagnosticAttributes* Attributes;
	// 故意不复制：用于构造客户端预测通过、服务器拒绝的确定场景。
	UPROPERTY(EditAnywhere, Category="Diagnostics")
	bool bRejectActivation = false;
	UPROPERTY(Replicated)
	int32 CommitCount = 0;
	virtual UAbilitySystemComponent* GetAbilitySystemComponent() const override { return AbilitySystem; }
	virtual void PossessedBy(AController* NewController) override;
	virtual void OnRep_PlayerState() override;
	virtual void BeginPlay() override;
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
};

/** 显式使用 ?game=/Script/Nexus.NexusDiagnosticGameMode，不改默认关卡或模式。 */
UCLASS()
class ANexusDiagnosticGameMode : public AGameModeBase
{
	GENERATED_BODY()
public:
	ANexusDiagnosticGameMode();
};
