// Copyright byteyang. All Rights Reserved.

using UnrealBuildTool;

public class NexusLinkExtTests : ModuleRules
{
	public NexusLinkExtTests(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(
			new string[]
			{
				"Core",
				"CoreUObject",
				"Engine",
			}
		);

		PrivateDependencyModuleNames.AddRange(
			new string[]
			{
				"NexusLink",
				"NexusLinkExt",
			}
		);

		if (Target.bBuildEditor)
		{
			PrivateDependencyModuleNames.AddRange(
				new string[]
				{
					"NexusLinkExtEditor",
					"UnrealEd",
				}
			);
		}
	}
}
