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
			"EnhancedInput",
			"AIModule",
			"StateTreeModule",
			"GameplayStateTreeModule",
			"UMG",
			"Slate"
		});

		PrivateDependencyModuleNames.AddRange(new string[] { });

		PublicIncludePaths.AddRange(new string[] {
			"Nexus",
			"Nexus/Variant_Platforming",
			"Nexus/Variant_Platforming/Animation",
			"Nexus/Variant_Combat",
			"Nexus/Variant_Combat/AI",
			"Nexus/Variant_Combat/Animation",
			"Nexus/Variant_Combat/Gameplay",
			"Nexus/Variant_Combat/Interfaces",
			"Nexus/Variant_Combat/UI",
			"Nexus/Variant_SideScrolling",
			"Nexus/Variant_SideScrolling/AI",
			"Nexus/Variant_SideScrolling/Gameplay",
			"Nexus/Variant_SideScrolling/Interfaces",
			"Nexus/Variant_SideScrolling/UI"
		});

		// Uncomment if you are using Slate UI
		// PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });

		// Uncomment if you are using online features
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");

		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
