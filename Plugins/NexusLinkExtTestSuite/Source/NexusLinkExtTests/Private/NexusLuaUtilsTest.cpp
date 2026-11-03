// Copyright byteyang. All Rights Reserved.

#include "CoreMinimal.h"

#if WITH_DEV_AUTOMATION_TESTS && WITH_UNLUA

#include "Misc/AutomationTest.h"
#include "Utils/NexusLuaUtils.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNexusLuaValueToJsonStackTest,
	"NexusLinkExt.Lua.ValueToJsonStackBalance",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FNexusLuaValueToJsonStackTest::RunTest(const FString& Parameters)
{
	lua_State* L = luaL_newstate();
	if (!TestNotNull(TEXT("Isolated Lua state"), L)) return false;

	for (int32 EntryCount : {0, 1, 49, 50, 51, 120})
	{
		for (bool bNested : {false, true})
		{
			for (bool bPositiveIndex : {false, true})
			{
				lua_settop(L, 0);
				lua_pushliteral(L, "sentinel");
				lua_newtable(L);
				if (bNested) lua_newtable(L);
				for (int32 EntryIndex = 1; EntryIndex <= EntryCount; ++EntryIndex)
				{
					lua_pushinteger(L, EntryIndex);
					lua_rawseti(L, -2, EntryIndex);
				}
				if (bNested)
				{
					lua_setfield(L, -2, "RootAttr");
					lua_pushboolean(L, true);
					lua_setfield(L, -2, "sibling");
				}

				const FString Context = FString::Printf(TEXT("entries=%d nested=%d positiveIndex=%d"),
					EntryCount, bNested, bPositiveIndex);
				TSharedPtr<FJsonValue> Value = FNexusLuaUtils::LuaValueToJson(L, bPositiveIndex ? 2 : -1);
				TestEqual(Context + TEXT(" preserves stack height"), lua_gettop(L), 2);
				TestEqual(Context + TEXT(" preserves input table"), lua_type(L, 2), LUA_TTABLE);
				TestEqual(Context + TEXT(" preserves prior values"), FString(UTF8_TO_TCHAR(lua_tostring(L, 1))), FString(TEXT("sentinel")));
				if (!TestTrue(Context + TEXT(" returns JSON object"), Value.IsValid() && Value->Type == EJson::Object)) continue;
				TSharedPtr<FJsonObject> Object = Value->AsObject();
				if (bNested)
				{
					TestTrue(Context + TEXT(" serializes sibling"), Object->GetBoolField(TEXT("sibling")));
					Object = Object->GetObjectField(TEXT("RootAttr"));
				}
				TestEqual(Context + TEXT(" limits serialized fields"), Object->Values.Num(),
					FMath::Min(EntryCount, 50) + (EntryCount >= 50 ? 1 : 0));
			}
		}
	}

	lua_settop(L, 0);
	lua_newtable(L);
	lua_pushvalue(L, -1);
	lua_setfield(L, -2, "self");
	TSharedPtr<FJsonValue> Cycle = FNexusLuaUtils::LuaValueToJson(L, -1);
	TestEqual(TEXT("Cyclic table preserves stack height"), lua_gettop(L), 1);
	TestEqual(TEXT("Cyclic table stops at depth limit"),
		Cycle->AsObject()->GetObjectField(TEXT("self"))->GetStringField(TEXT("self")), FString(TEXT("<table>")));
	lua_close(L);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS && WITH_UNLUA
