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
				"Json",
				"NexusLink",
				"NexusLinkExt",
			}
		);

		// 直接测试 Lua 工具，补链 UnLua；门控宏仍由 NexusLinkExt 传入。
		string ProjectRoot = NexusLinkOptionalPlugins.FindProjectRoot(ModuleDirectory);
		var SearchDirs = NexusLinkOptionalPlugins.CollectPluginSearchDirs(ProjectRoot, this);
		var UnLua = NexusLinkOptionalPlugins.Opt(
			new[] { "UnLua.uplugin" }, "WITH_UNLUA", "WITH_UNLUA",
			rt: new[] { "UnLua", "Lua" }, noDisable: true);
		NexusLinkOptionalPlugins.Apply(
			this, Target, UnLua, SearchDirs, ProjectRoot,
			bAllowEditorModules: false, bDefineMacro: false);

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
