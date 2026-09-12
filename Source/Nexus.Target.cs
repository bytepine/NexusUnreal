// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;
using System.Collections.Generic;

public class NexusTarget : TargetRules
{
	public NexusTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
#if UE_5_8_OR_LATER
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
#elif UE_5_7_OR_LATER
		DefaultBuildSettings = BuildSettingsVersion.V6;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_7;
#elif UE_5_4_OR_LATER
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
#elif UE_5_3_OR_LATER
		DefaultBuildSettings = BuildSettingsVersion.V4;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
#elif UE_5_1_OR_LATER
		DefaultBuildSettings = BuildSettingsVersion.V2;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
#elif UE_5_0_OR_LATER
		DefaultBuildSettings = BuildSettingsVersion.V2;
#else
		DefaultBuildSettings = BuildSettingsVersion.V2;
#endif
		ExtraModuleNames.Add("Nexus");
#if UE_5_6_OR_LATER
		// 5.7 模板变体依赖 StateTree 5.6+ API（GetDescription 格式化、WeakExecutionContext）
		ExtraModuleNames.Add("NexusGameplay");
#elif !UE_5_0_OR_LATER
		ExtraModuleNames.Add("NexusInputStubs");
#endif
	}
}
