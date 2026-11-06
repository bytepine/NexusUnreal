// Copyright byteyang. All Rights Reserved.
#include "NexusNavigationTestData.h"
#include "NavigationSystemTypes.h"

ANexusNavigationTestData::ANexusNavigationTestData()
{
	FindPathImplementation = &ANexusNavigationTestData::FindTestPath;
}

FPathFindingResult ANexusNavigationTestData::FindTestPath(const FNavAgentProperties& Agent, const FPathFindingQuery& Query)
{
	const bool bPartial = Query.EndLocation.X > 500;
	FPathFindingResult Result(bPartial && !Query.bAllowPartialPaths ? ENavigationQueryResult::Fail : ENavigationQueryResult::Success);
	Result.Path = MakeShareable(new FNavigationPath({Query.StartLocation, Query.EndLocation}));
	Result.Path->SetIsPartial(bPartial);
	return Result;
}
