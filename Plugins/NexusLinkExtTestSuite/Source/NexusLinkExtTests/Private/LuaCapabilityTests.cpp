// Copyright byteyang. All Rights Reserved.

#include "Misc/AutomationTest.h"
#include "NexusCapabilityRegistry.h"
#include "NexusMcpTool.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FNexusLinkExtLuaCapsRegistered,
	"NexusLinkExt.Smoke.LuaCaps",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusLinkExtLuaCapsRegistered::RunTest(const FString& Parameters)
{
	const TCHAR* RuntimeNames[] = {
		TEXT("EvalRuntimeLua"),
		TEXT("DofileRuntimeLua"),
		TEXT("GcRuntimeLua"),
		TEXT("HotReloadRuntimeLua"),
		TEXT("SetRuntimeLua"),
		TEXT("GetRuntimeLuaEnv"),
		TEXT("GetRuntimeLuaValue"),
		TEXT("GetRuntimeLuaLoaded"),
		TEXT("GetRuntimeLuaStack"),
		TEXT("GetRuntimeLuaMetatable"),
		TEXT("GetRuntimeLuaObject"),
		TEXT("GetRuntimeLuaMemory"),
	};

	auto Expect = [this](const TCHAR* Name, bool bExpect)
	{
		const FCapRecord* Rec = FNexusCapabilityRegistry::Get().FindRecordByName(Name);
		if (bExpect)
		{
			TestNotNull(Name, Rec);
		}
		else
		{
			TestNull(FString::Printf(TEXT("%s absent"), Name), Rec);
		}
	};

#if WITH_UNLUA
	for (const TCHAR* Name : RuntimeNames)
	{
		Expect(Name, true);
	}
	const TCHAR* DangerousNames[] = {
		TEXT("EvalRuntimeLua"),
		TEXT("DofileRuntimeLua"),
	};
	for (const TCHAR* Name : DangerousNames)
	{
		if (const FCapRecord* Rec = FNexusCapabilityRegistry::Get().FindRecordByName(Name))
		{
			TestTrue(FString::Printf(TEXT("%s dangerous"), Name), Rec->Def.HasTag(FNexusMcpTags::Dangerous));
		}
	}
#if WITH_EDITOR
	Expect(TEXT("GetAssetLuaBinding"), true);
	Expect(TEXT("ManageAssetLuaBinding"), true);
	TArray<FString> Actions;
	TestTrue(TEXT("manage_asset_lua_binding actions"),
		FNexusCapabilityRegistry::CollectOperationActions(TEXT("ManageAssetLuaBinding"), Actions));
	TestTrue(TEXT("Bind"), Actions.Contains(TEXT("Bind")));
	TestTrue(TEXT("Unbind"), Actions.Contains(TEXT("Unbind")));
#endif
#else
	for (const TCHAR* Name : RuntimeNames)
	{
		Expect(Name, false);
	}
#endif
	return true;
}

#endif
