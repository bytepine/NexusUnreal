// Copyright byteyang. All Rights Reserved.
#pragma once
#include "NavigationData.h"
#include "NexusNavigationTestData.generated.h"

/** 通过真实 NavigationSystem 派发的确定性导航数据，无需构建 Recast 网格。 */
UCLASS()
class ANexusNavigationTestData : public ANavigationData
{
	GENERATED_BODY()
public:
	ANexusNavigationTestData();
	virtual FBox GetBounds() const override { return FBox(FVector(-2000), FVector(2000)); }
private:
	static FPathFindingResult FindTestPath(const FNavAgentProperties& Agent, const FPathFindingQuery& Query);
};
