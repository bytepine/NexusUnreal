// Copyright byteyang. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DataTable.h"
#include "UObject/Interface.h"
#include "GameFramework/Actor.h"
#include "NexusReliabilityTestTypes.generated.h"

/** 带返回值的接口函数生成独立实现图，覆盖结构副本的接口图保留。 */
UINTERFACE(Blueprintable)
class UNexusPreviewTestInterface : public UInterface
{
	GENERATED_BODY()
};

class INexusPreviewTestInterface
{
	GENERATED_BODY()
public:
	UFUNCTION(BlueprintImplementableEvent, Category="NexusTest")
	int32 GetPreviewValue() const;
};

UENUM()
enum class ENexusPreviewTestEnum : uint8 { First, Second };

/** 记录真实按钮委托，验证定位失败不会触发任何点击。 */
UCLASS()
class UNexusWidgetClickRecorder : public UObject
{
	GENERATED_BODY()
public:
	int32 ClickCount = 0;
	UFUNCTION() void RecordClick() { ++ClickCount; }
};

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

	UPROPERTY() float Weight = 1.f;
	UPROPERTY() FName Key;
	UPROPERTY() FText Text;
	UPROPERTY() ENexusPreviewTestEnum Choice = ENexusPreviewTestEnum::First;

	static int32 DestructionCount;
	~FNexusReliabilityTestRow() { ++DestructionCount; }
};

/** CDO 引用为空、实例才创建的所属对象，覆盖属性 Schema 的实例发现。 */
UCLASS(EditInlineNew)
class UNexusOwnedSettingsTestObject : public UObject
{
	GENERATED_BODY()
public:
	UPROPERTY(EditAnywhere, Category="NexusTest") int32 Threshold = 7;
};

UCLASS()
class ANexusOwnedSettingsTestActor : public AActor
{
	GENERATED_BODY()
public:
	UPROPERTY(EditAnywhere, Instanced, Category="NexusTest") UNexusOwnedSettingsTestObject* Settings = nullptr;
};
