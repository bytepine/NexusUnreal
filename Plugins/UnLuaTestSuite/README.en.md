# UnLuaTestSuite

[中文](README.md) | English

This regression test plugin is extracted from the [Tencent/UnLua](https://github.com/Tencent/UnLua) v2.3.6 sample project. It lives in this sample project and is **not** included in the UnLua plugin repository.

Its Lua scripts live in the project's `Content/Script/Tests/`; UnLua loads from `Content/Script/?.lua` by default.

## Project adaptations

- `UnLuaTestSuite.Build.cs` adds the `LevelEditor` dependency for Editor targets, as required by `TestCommands.cpp`.
- UE 5.5+: `UNLUA_TEST_APP_CONTEXT` (EditorContext) centralizes `ApplicationContextMask`; `UnLuaTestEqual` converts `TestEqual(const char*)` arguments to `FString` to remove overload ambiguity.
- The initial port excludes two cases that depend on `/Game` assets from the TPS sample project, renaming their sources to `.cpp.disabled`:
  - `LuaLib_Class.spec.cpp` (`/Game/Core/Blueprints/BP_Game`).
  - `Issue288Test.cpp` (`/Game/FPWeapon/Textures/UE4_LOGO_CARD`).
- Upstream benchmarks do not cover UE→Lua override callbacks; `UnLua.Perf.OverrideCall` adds that coverage.

## Run tests

In the editor: Session Frontend → Automation → `UnLua`.

Command-line example:

```text
UnrealEditor-Cmd Nexus.uproject -unattended -NullRHI -ExecCmds="Automation RunTests UnLua;Quit"
```
