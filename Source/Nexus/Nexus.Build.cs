// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class Nexus : ModuleRules
{
	public Nexus(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] {
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"AIModule",
			"UMG",
			"Slate"
		});
#if UE_5_0_OR_LATER
		PublicDependencyModuleNames.Add("EnhancedInput");
#else
		PublicDependencyModuleNames.Add("NexusInputStubs");
#endif

		PrivateDependencyModuleNames.AddRange(new string[] { });

		PublicIncludePaths.Add("Nexus");
	}
}
