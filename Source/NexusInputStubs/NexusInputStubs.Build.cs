// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class NexusInputStubs : ModuleRules
{
	public NexusInputStubs(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject" });
		PublicIncludePaths.Add(ModuleDirectory);
	}
}
