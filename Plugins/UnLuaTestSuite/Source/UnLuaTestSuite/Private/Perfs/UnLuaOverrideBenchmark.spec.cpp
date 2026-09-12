// 上游 Benchmark 覆盖属性读写与 UFunction 调用，不含 UE→Lua 覆写回调。
// 本 spec 补这一项，供 P0-3 魔数头改动前后对比。

#include "Tests/IssueOverridesTest.h"
#include "UnLua.h"
#include "UnLuaTestHelpers.h"
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUnLuaOverrideCallBenchmark,
                                 TEXT("UnLua.Perf.OverrideCall UE调用Lua覆写回调"),
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FUnLuaOverrideCallBenchmark::RunTest(const FString& Parameters)
{
    UnLua::Startup();
    const auto L = UnLua::GetState();
    if (!L)
    {
        UnLua::Shutdown();
        return false;
    }

    const auto Obj = NewObject<UIssueOverridesObject>();
    Obj->AddToRoot();

    constexpr int32 N = 1000000;
    for (int32 i = 0; i < 16; ++i)
        Obj->CollectInfo();

    const double StartTime = FPlatformTime::Seconds();
    int32 Acc = 0;
    for (int32 i = 0; i < N; ++i)
        Acc += Obj->CollectInfo();
    const double NsPerCall = (FPlatformTime::Seconds() - StartTime) * (1000000000.0 / N);

    UE_LOG(LogTemp, Display, TEXT("UnLua override callback ; %f ns  acc=%d"), NsPerCall, Acc);
    TestEqual(TEXT("CollectInfo Lua override"), Obj->CollectInfo(), 2);

    Obj->RemoveFromRoot();
    UnLua::Shutdown();
    return true;
}

#endif
