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
		TEXT("eval_runtime_lua"),
		TEXT("dofile_runtime_lua"),
		TEXT("gc_runtime_lua"),
		TEXT("hotreload_runtime_lua"),
		TEXT("set_runtime_lua"),
		TEXT("get_runtime_lua_env"),
		TEXT("get_runtime_lua_value"),
		TEXT("get_runtime_lua_loaded"),
		TEXT("get_runtime_lua_stack"),
		TEXT("get_runtime_lua_metatable"),
		TEXT("get_runtime_lua_object"),
		TEXT("get_runtime_lua_memory"),
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
		TEXT("eval_runtime_lua"),
		TEXT("dofile_runtime_lua"),
	};
	for (const TCHAR* Name : DangerousNames)
	{
		if (const FCapRecord* Rec = FNexusCapabilityRegistry::Get().FindRecordByName(Name))
		{
			TestTrue(FString::Printf(TEXT("%s dangerous"), Name), Rec->Def.HasTag(FNexusMcpTags::Dangerous));
		}
	}
#if WITH_EDITOR
	Expect(TEXT("get_asset_lua_binding"), true);
	Expect(TEXT("manage_asset_lua_binding"), true);
	TArray<FString> Actions;
	TestTrue(TEXT("manage_asset_lua_binding actions"),
		FNexusCapabilityRegistry::CollectOperationActions(TEXT("manage_asset_lua_binding"), Actions));
	TestTrue(TEXT("bind"), Actions.Contains(TEXT("bind")));
	TestTrue(TEXT("unbind"), Actions.Contains(TEXT("unbind")));
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
