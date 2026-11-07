// Copyright byteyang. All Rights Reserved.
#pragma once
#include "Engine/DataAsset.h"
#include "NexusRelatedDataAsset.generated.h"

UCLASS(BlueprintType)
class UNexusRelatedDataAsset : public UDataAsset
{
	GENERATED_BODY()
public:
	UPROPERTY(EditAnywhere) FString Label = TEXT("before");
	UPROPERTY(EditAnywhere) FVector Location = FVector::ZeroVector;
	UPROPERTY(EditAnywhere) TMap<FString, int32> Values;
};
