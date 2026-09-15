// Copyright byteyang. All Rights Reserved.

using UnrealBuildTool;

public class NexusLinkTests : ModuleRules
{
	public NexusLinkTests(ReadOnlyTargetRules Target) : base(Target)
	{
		ApplyCustomEngineCompatDefines(this);

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
				"Json",
				"JsonUtilities",
				"Projects",
			}
		);

		if (Target.bBuildEditor)
		{
			PrivateDependencyModuleNames.AddRange(
				new string[]
				{
					// NexusLinkEditor（Editor 模块）：192 个 EditorOnly cap / 编辑器 Utils 的测试用例需要
					"NexusLinkEditor",
					"UnrealEd",
					"BlueprintGraph",
					"KismetCompiler",
					"UMG",
					"UMGEditor",
					"MovieScene",
					"MovieSceneTracks",
					"AnimGraph",
					"AnimGraph",
				}
			);
		}
		else
		{
			// Game 目标不链接 NexusLinkEditor，WITH_STATETREE 等 13 个 Editor 域可选插件宏没有
			// 定义来源；测试文件里直接 #if WITH_STATETREE 检测（非 #ifdef），未定义时 MSVC 报
			// C4668。这里兜底置 0，语义等价于「Game 目标下这些 Editor 域能力必不存在」。
			foreach (var C in NexusLinkOptionalPlugins.BuildFullTable())
			{
				if (C.Define != "WITH_UNLUA" && C.Define != "WITH_GAS" && C.Define != "WITH_NIAGARA")
				{
					PublicDefinitions.Add(C.Define + "=0");
				}
			}
		}

		PrivateIncludePaths.AddRange(
			new string[]
			{
				// 与 NexusLink 分插件后，UBT 不再把对方 Source 当成本插件根；显式指向兄弟插件 Private（McpAuthTokenTests 需要 NexusMcpAuth.h）
				System.IO.Path.GetFullPath(System.IO.Path.Combine(ModuleDirectory, "..", "..", "..", "NexusLink", "Source", "NexusLink", "Private")),
				// NexusLink 双模块拆分：MakeSettingsGroupPath 等测试用例需要直接访问 NexusLinkEditor 的 Private 头
				System.IO.Path.GetFullPath(System.IO.Path.Combine(ModuleDirectory, "..", "..", "..", "NexusLink", "Source", "NexusLinkEditor", "Private")),
			}
		);
	}

	/// <summary>
	/// 与 NexusLink.Build.cs 同步：定制引擎 Build.h 要求 WITH_EDITOR_ENCRYPTION 时兜底为 0。
	/// </summary>
	private static void ApplyCustomEngineCompatDefines(ModuleRules Module)
	{
		if (ShouldDefineWithEditorEncryption(Module))
		{
			Module.PublicDefinitions.Add("WITH_EDITOR_ENCRYPTION=0");
		}
	}

	private static bool ShouldDefineWithEditorEncryption(ModuleRules Module)
	{
		foreach (string engineDir in ResolveEngineDirectoryCandidates(Module))
		{
			string buildH = System.IO.Path.Combine(engineDir, "Source", "Runtime", "Core", "Public", "Misc", "Build.h");
			if (!System.IO.File.Exists(buildH)) continue;

			try
			{
				if (System.IO.File.ReadAllText(buildH).Contains("WITH_EDITOR_ENCRYPTION"))
				{
					return true;
				}
			}
			catch (System.Exception) { }
		}

		return System.Environment.GetEnvironmentVariable("NEXUS_WITH_EDITOR_ENCRYPTION_FALLBACK") == "1";
	}

	private static System.Collections.Generic.List<string> ResolveEngineDirectoryCandidates(ModuleRules Module)
	{
		var seen = new System.Collections.Generic.HashSet<string>(System.StringComparer.OrdinalIgnoreCase);
		var list = new System.Collections.Generic.List<string>();

		// EngineDirectory 在 UE 5.8 改为 static 属性，用反射兼容 instance（UE4~5.7）和 static（UE5.8+）
		try
		{
			var Prop = typeof(ModuleRules).GetProperty("EngineDirectory",
				System.Reflection.BindingFlags.Public |
				System.Reflection.BindingFlags.Instance |
				System.Reflection.BindingFlags.Static);
			if (Prop != null)
			{
				bool IsStatic = Prop.GetGetMethod().IsStatic;
				string EngDir = IsStatic
					? Prop.GetValue(null) as string
					: Prop.GetValue(Module) as string;
				TryAddEngineDirectory(EngDir, seen, list);
			}
		}
		catch { /* 属性不存在或访问失败时继续 */ }

		try
		{
			// UE4 UBT：静态 UnrealBuildTool.EngineDirectory（自定义引擎 / 无 ModuleRules.EngineDirectory 时也能定位）
			var ubt = typeof(ModuleRules).Assembly.GetType("UnrealBuildTool.UnrealBuildTool");
			var f = ubt != null ? ubt.GetField("EngineDirectory",
				System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Static) : null;
			object v = f != null ? f.GetValue(null) : null;
			if (v != null)
			{
				var fn = v.GetType().GetProperty("FullName");
				TryAddEngineDirectory(fn != null ? fn.GetValue(v) as string : v.ToString(), seen, list);
			}
		}
		catch { }

		TryAddEngineDirectory(System.Environment.GetEnvironmentVariable("UE_ENGINE_DIRECTORY"), seen, list);
		TryAddEngineDirectory(System.Environment.GetEnvironmentVariable("UE4_ROOT"), seen, list);
		TryAddEngineDirectory(System.Environment.GetEnvironmentVariable("UNREAL_ENGINE_PATH"), seen, list);

		return list;
	}

	private static void TryAddEngineDirectory(
		string dir,
		System.Collections.Generic.HashSet<string> seen,
		System.Collections.Generic.List<string> list)
	{
		if (string.IsNullOrEmpty(dir)) return;

		try
		{
			dir = System.IO.Path.GetFullPath(dir);
			if (System.IO.Directory.Exists(dir) && seen.Add(dir))
			{
				list.Add(dir);
			}
		}
		catch (System.Exception)
		{
		}
	}
}
