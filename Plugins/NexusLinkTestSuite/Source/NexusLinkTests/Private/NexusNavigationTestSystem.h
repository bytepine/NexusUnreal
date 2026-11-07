// Copyright byteyang. All Rights Reserved.
#pragma once
#include "NavigationSystem.h"
#include "NavFilters/NavigationQueryFilter.h"
#include "NavAreas/NavArea_Default.h"
#include "NexusNavigationTestSystem.generated.h"

/** 仅为真实 Recast 测试提供固定边界，避免依赖编辑器刷子资产。 */
UCLASS()
class UNexusNavigationTestSystem : public UNavigationSystemV1
{
	GENERATED_BODY()
public:
	TArray<FNavigationBounds> TestBounds;
	void ConfigureTestAgents(const TArray<FNavDataConfig>& Agents)
	{
		SupportedAgents = Agents;
		SupportedAgentsMask.Empty();
		for (int32 AgentIndex = 0; AgentIndex < Agents.Num(); ++AgentIndex) SupportedAgentsMask.Set(AgentIndex);
		SupportedAgentsMask.MarkInitialized();
	}
	void AddTestBounds(const FNavigationBounds& Bounds) { TestBounds.Add(Bounds); AddNavigationBounds(Bounds); }
	virtual void GatherNavigationBounds() override
	{
		Super::GatherNavigationBounds();
		for (const FNavigationBounds& Bounds : TestBounds) AddNavigationBounds(Bounds);
	}
};

/** 排除默认行走区域，验证调用方传入的 FilterClass 确实改变路径查询。 */
UCLASS()
class UNexusNavigationRejectAllFilter : public UNavigationQueryFilter
{
	GENERATED_BODY()
public:
	UNexusNavigationRejectAllFilter()
	{
		FNavigationFilterArea Area;
		Area.AreaClass = UNavArea_Default::StaticClass();
		Area.bIsExcluded = true;
		Areas.Add(Area);
	}
};
