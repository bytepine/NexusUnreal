// Copyright byteyang. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DataTable.h"
#include "NexusReliabilityTestTypes.generated.h"

/** 含非平凡成员的测试行，用析构计数验证临时行在成功和失败路径均被释放。 */
USTRUCT()
struct FNexusReliabilityTestRow : public FTableRowBase
{
	GENERATED_BODY()

	UPROPERTY()
	FString Label;

	UPROPERTY()
	int32 Count = 7;

	UPROPERTY()
	bool bEnabled = false;

	UPROPERTY()
	TArray<int32> Values;

	static int32 DestructionCount;
	~FNexusReliabilityTestRow() { ++DestructionCount; }
};
