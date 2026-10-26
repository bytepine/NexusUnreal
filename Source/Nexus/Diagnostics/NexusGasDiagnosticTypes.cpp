// Copyright byteyang. All Rights Reserved.
#include "Diagnostics/NexusGasDiagnosticTypes.h"
#include "Net/UnrealNetwork.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "UObject/UnrealType.h"
#if ENGINE_MAJOR_VERSION == 5 && ENGINE_MINOR_VERSION >= 3
#include "GameplayEffectComponents/TargetTagsGameplayEffectComponent.h"
#endif

UNexusDiagnosticAttributes::UNexusDiagnosticAttributes() { Mana.SetBaseValue(100.f); Mana.SetCurrentValue(100.f); }

void UNexusDiagnosticAttributes::OnRep_Mana(const FGameplayAttributeData& OldValue)
{
	GAMEPLAYATTRIBUTE_REPNOTIFY(UNexusDiagnosticAttributes, Mana, OldValue);
}

void UNexusDiagnosticAttributes::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME_CONDITION_NOTIFY(UNexusDiagnosticAttributes, Mana, COND_None, REPNOTIFY_Always);
}

UNexusDiagnosticCost::UNexusDiagnosticCost()
{
	DurationPolicy = EGameplayEffectDurationType::Instant;
	FGameplayModifierInfo Modifier;
	Modifier.Attribute = FGameplayAttribute(FindFProperty<FProperty>(UNexusDiagnosticAttributes::StaticClass(), TEXT("Mana")));
	Modifier.ModifierOp = EGameplayModOp::Additive;
	Modifier.ModifierMagnitude = FScalableFloat(-10.f);
	Modifiers.Add(Modifier);
}

UNexusDiagnosticCooldown::UNexusDiagnosticCooldown()
{
	DurationPolicy = EGameplayEffectDurationType::HasDuration;
	DurationMagnitude = FScalableFloat(30.f);
	FInheritedTagContainer Tags;
	Tags.AddTag(FGameplayTag::RequestGameplayTag(TEXT("Nexus.Diagnostics.Cooldown")));
#if ENGINE_MAJOR_VERSION == 5 && ENGINE_MINOR_VERSION >= 3
	UTargetTagsGameplayEffectComponent* TargetTags = CreateDefaultSubobject<UTargetTagsGameplayEffectComponent>(TEXT("CooldownTags"));
	GEComponents.Add(TargetTags);
	TargetTags->SetAndApplyTargetTagChanges(Tags);
#else
	InheritableOwnedTagsContainer = Tags;
#endif
}

UNexusDiagnosticAbility::UNexusDiagnosticAbility()
{
	InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;
	NetExecutionPolicy = EGameplayAbilityNetExecutionPolicy::LocalPredicted;
	ActivationRequiredTags.AddTag(FGameplayTag::RequestGameplayTag(TEXT("Nexus.Diagnostics.Required")));
	ActivationBlockedTags.AddTag(FGameplayTag::RequestGameplayTag(TEXT("Nexus.Diagnostics.Blocked")));
	CostGameplayEffectClass = UNexusDiagnosticCost::StaticClass();
	CooldownGameplayEffectClass = UNexusDiagnosticCooldown::StaticClass();
}

bool UNexusDiagnosticAbility::CanActivateAbility(FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info,
	const FGameplayTagContainer* SourceTags, const FGameplayTagContainer* TargetTags, FGameplayTagContainer* RelevantTags) const
{
	const ANexusDiagnosticCharacter* Character = Info ? Cast<ANexusDiagnosticCharacter>(Info->AvatarActor.Get()) : nullptr;
	if (Character && Character->bRejectActivation)
	{
		if (RelevantTags) RelevantTags->AddTag(FGameplayTag::RequestGameplayTag(TEXT("Nexus.Diagnostics.Rejected")));
		return false;
	}
	return Super::CanActivateAbility(Handle, Info, SourceTags, TargetTags, RelevantTags);
}

bool UNexusDiagnosticAbility::CheckCost(FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info, FGameplayTagContainer* Tags) const
{
	const bool bAllowed = Super::CheckCost(Handle, Info, Tags);
	if (!bAllowed && Tags) Tags->AddTag(FGameplayTag::RequestGameplayTag(TEXT("Nexus.Diagnostics.Cost")));
	return bAllowed;
}

bool UNexusDiagnosticAbility::CheckCooldown(FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info, FGameplayTagContainer* Tags) const
{
	const bool bAllowed = Super::CheckCooldown(Handle, Info, Tags);
	if (!bAllowed && Tags) Tags->AddTag(FGameplayTag::RequestGameplayTag(TEXT("Nexus.Diagnostics.Cooldown")));
	return bAllowed;
}

void UNexusDiagnosticAbility::ActivateAbility(FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info,
	FGameplayAbilityActivationInfo ActivationInfo, const FGameplayEventData* EventData)
{
	const bool bCommitted = CommitAbility(Handle, Info, ActivationInfo);
	if (bCommitted && Info && Info->IsNetAuthority())
		if (ANexusDiagnosticCharacter* Character = Cast<ANexusDiagnosticCharacter>(Info->AvatarActor.Get()))
			++Character->CommitCount;
	EndAbility(Handle, Info, ActivationInfo, true, !bCommitted);
}

UNexusDiagnosticServerAbility::UNexusDiagnosticServerAbility() { NetExecutionPolicy = EGameplayAbilityNetExecutionPolicy::ServerOnly; }

ANexusDiagnosticCharacter::ANexusDiagnosticCharacter()
{
	bReplicates = true;
	GetCharacterMovement()->GravityScale = 0.f;
	AbilitySystem = CreateDefaultSubobject<UAbilitySystemComponent>(TEXT("AbilitySystem"));
	AbilitySystem->SetIsReplicated(true);
	Attributes = CreateDefaultSubobject<UNexusDiagnosticAttributes>(TEXT("Attributes"));
}

void ANexusDiagnosticCharacter::BeginPlay()
{
	Super::BeginPlay();
	AbilitySystem->InitAbilityActorInfo(this, this);
	AbilitySystem->AddAttributeSetSubobject(Attributes);
	// 每端初始条件相同，失败用例可独立改变服务器或客户端的本地标签。
	AbilitySystem->AddLooseGameplayTag(FGameplayTag::RequestGameplayTag(TEXT("Nexus.Diagnostics.Required")));
	if (HasAuthority())
	{
		AbilitySystem->GiveAbility(FGameplayAbilitySpec(UNexusDiagnosticAbility::StaticClass()));
		AbilitySystem->GiveAbility(FGameplayAbilitySpec(UNexusDiagnosticServerAbility::StaticClass()));
	}
}

void ANexusDiagnosticCharacter::PossessedBy(AController* NewController)
{
	Super::PossessedBy(NewController);
	AbilitySystem->InitAbilityActorInfo(this, this);
}

void ANexusDiagnosticCharacter::OnRep_PlayerState()
{
	Super::OnRep_PlayerState();
	AbilitySystem->InitAbilityActorInfo(this, this);
}

void ANexusDiagnosticCharacter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ANexusDiagnosticCharacter, CommitCount);
}

ANexusDiagnosticGameMode::ANexusDiagnosticGameMode() { DefaultPawnClass = ANexusDiagnosticCharacter::StaticClass(); }
