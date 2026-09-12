# UnLuaTestSuite

从 [Tencent/UnLua](https://github.com/Tencent/UnLua) v2.3.6 示例工程提取的回归测试插件，放在本示例工程侧，**不**进入 UnLua 插件仓。

对应的 Lua 脚本在工程 `Content/Script/Tests/`（UnLua 默认从 `Content/Script/?.lua` 加载）。

## 本工程适配

- `UnLuaTestSuite.Build.cs` 在 Editor 目标补了 `LevelEditor` 依赖（`TestCommands.cpp` 需要）
- UE 5.5+：`ApplicationContextMask` 收口为 `UNLUA_TEST_APP_CONTEXT`（EditorContext）；`TestEqual(const char*)` 经 `UnLuaTestEqual` 转 `FString` 消除重载歧义
- 首轮排除了两个依赖 TPS 示例工程 `/Game` 资产的用例（源文件改名为 `.cpp.disabled`）：
  - `LuaLib_Class.spec.cpp`（`/Game/Core/Blueprints/BP_Game`）
  - `Issue288Test.cpp`（`/Game/FPWeapon/Textures/UE4_LOGO_CARD`）
- 上游 Benchmark 不含 UE→Lua 覆写回调，补 `UnLua.Perf.OverrideCall`

## 跑测

编辑器：Session Frontend → Automation → `UnLua`

命令行示例：

```text
UnrealEditor-Cmd Nexus.uproject -unattended -NullRHI -ExecCmds="Automation RunTests UnLua;Quit"
```
