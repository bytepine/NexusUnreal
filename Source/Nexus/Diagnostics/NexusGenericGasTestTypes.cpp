// Copyright byteyang. All Rights Reserved.
#include "Diagnostics/NexusGenericGasTestTypes.h"
#include "AbilitySystemComponent.h"
#include "GameFramework/PlayerState.h"
#include "Engine/World.h"
#include "UObject/UnrealType.h"

namespace
{
	void InitTestAsc(AActor* Owner, AActor* Avatar)
	{
		UAbilitySystemComponent* Asc = Owner->FindComponentByClass<UAbilitySystemComponent>();
		Asc->InitAbilityActorInfo(Owner, Avatar);
		if (Owner->HasAuthority()) Asc->GiveAbility(FGameplayAbilitySpec(UNexusGenericGasTestAbility::StaticClass()));
	}
}

UNexusGenericGasTestAbility::UNexusGenericGasTestAbility()
{
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;
	NetExecutionPolicy = EGameplayAbilityNetExecutionPolicy::ServerOnly;
}

bool UNexusGenericGasTestAbility::CanActivateAbility(FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info,
	const FGameplayTagContainer* Source, const FGameplayTagContainer* Target, FGameplayTagContainer* Failure) const
{
	AActor* Avatar = Info ? Info->AvatarActor.Get() : nullptr;
	FBoolProperty* Reject = Avatar ? FindFProperty<FBoolProperty>(Avatar->GetClass(), TEXT("bRejectActivation")) : nullptr;
	if (Reject && Reject->GetPropertyValue_InContainer(Avatar))
	{
		if (Failure) Failure->AddTag(FGameplayTag::RequestGameplayTag(TEXT("Nexus.Diagnostics.Rejected")));
		return false;
	}
	return Super::CanActivateAbility(Handle, Info, Source, Target, Failure);
}

void UNexusGenericGasTestAbility::ActivateAbility(FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info,
	FGameplayAbilityActivationInfo Activation, const FGameplayEventData* Event)
{
	const bool bCommitted = CommitAbility(Handle, Info, Activation);
	EndAbility(Handle, Info, Activation, true, !bCommitted);
}

ANexusGenericGasTestActor::ANexusGenericGasTestActor() { CreateDefaultSubobject<UAbilitySystemComponent>(TEXT("AbilitySystem")); }
void ANexusGenericGasTestActor::BeginPlay() { Super::BeginPlay(); InitTestAsc(this, this); }
ANexusGenericGasTestPawn::ANexusGenericGasTestPawn() { CreateDefaultSubobject<UAbilitySystemComponent>(TEXT("AbilitySystem")); }
void ANexusGenericGasTestPawn::BeginPlay() { Super::BeginPlay(); InitTestAsc(this, this); }

void ANexusGenericGasTestStatePawn::BeginPlay()
{
	Super::BeginPlay();
	SetPlayerState(GetWorld()->SpawnActor<APlayerState>());
	UAbilitySystemComponent* Asc = NewObject<UAbilitySystemComponent>(GetPlayerState(), TEXT("AbilitySystem"));
	GetPlayerState()->AddInstanceComponent(Asc);
	Asc->RegisterComponent();
	InitTestAsc(GetPlayerState(), this);
}

void ANexusGenericGasTestStatePawn::EndPlay(const EEndPlayReason::Type Reason)
{
	if (GetPlayerState()) GetPlayerState()->Destroy();
	Super::EndPlay(Reason);
}
