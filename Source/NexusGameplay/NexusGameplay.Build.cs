// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class NexusGameplay : ModuleRules
{
	public NexusGameplay(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] {
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"AIModule",
			"UMG",
			"Slate",
			"Nexus"
		});
#if UE_5_1_OR_LATER
		PublicDependencyModuleNames.AddRange(new string[] {
			"StateTreeModule",
			"GameplayStateTreeModule"
		});
#endif

		PublicIncludePaths.AddRange(new string[] {
			"NexusGameplay",
			"NexusGameplay/Variant_Platforming",
			"NexusGameplay/Variant_Platforming/Animation",
			"NexusGameplay/Variant_Combat",
			"NexusGameplay/Variant_Combat/AI",
			"NexusGameplay/Variant_Combat/Animation",
			"NexusGameplay/Variant_Combat/Gameplay",
			"NexusGameplay/Variant_Combat/Interfaces",
			"NexusGameplay/Variant_Combat/UI",
			"NexusGameplay/Variant_SideScrolling",
			"NexusGameplay/Variant_SideScrolling/AI",
			"NexusGameplay/Variant_SideScrolling/Gameplay",
			"NexusGameplay/Variant_SideScrolling/Interfaces",
			"NexusGameplay/Variant_SideScrolling/UI"
		});
	}
}
