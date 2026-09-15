# Changelog — NexusUnreal（示例工程）

> **NexusLink 插件**变更记录在公开仓 [NexusLink CHANGELOG](https://github.com/bytepine/NexusLink/blob/master/CHANGELOG.md)。

---

## [Unreleased]

### Added

- test(plugin): 将 NexusLink L1 Automation 抽成工程侧独立插件 `Plugins/NexusLinkTestSuite`（仿 UnLuaTestSuite；模块名仍为 `NexusLinkTests`；跨插件访问 `NexusMcpAuth.h` 走兄弟插件 Private 路径）
- chore(deps): 以 git submodule 引入 UnLua（`Plugins/UnLua` → [bytepine/UnLua](https://github.com/bytepine/UnLua)）；`Nexus.uproject` 启用 UnLua
- test(unlua): 引入上游 UnLuaTestSuite（工程侧 `Plugins/UnLuaTestSuite`）及 `Content/Script/Tests/` Lua 脚本；Editor 补 `LevelEditor` 依赖；排除依赖 TPS `/Game` 资产的 `LuaLib_Class.spec.cpp` / `Issue288Test.cpp`；补覆写回调 benchmark spec
- test(e2e): 新领域与写路径——`test_108` StringTable/Font、`test_109` FoliageType、`test_110` Paper2D、`test_111` GeometryCollection、`test_112` Media、`test_113` CommonUI、`test_114` MoviePipeline；GAS 扩 CueNotify；钉写 MF 写图、ABP Slot/Blend/IK/AimOffset、Niagara 空白 `add_emitter`+模块栈、WBP 动画绑定/`remove_key`、`test_98` Sequencer 绑定级 key；缺口 `test_90` DataAsset、`test_94` manage_asset_level spawn/remove、`test_96` GAS runtime、`test_95` widget/Lua、`test_10` get_asset_lua_binding；**manage 每个 action + get 每个 named section** 均有 happy-path；`Script/audit_e2e_coverage.py` 对照 C++ 注册表门禁
- feat(test): `capability_probe` + `asset_helpers`——SearchMode 下用 `search_capabilities` 替代 `tools/list` 门禁；资产搜索统一 `cap_first`，缺失时在 `test_ns` 内创建；`ue_launcher` 强制 `WITH_GAS=1`/`WITH_NIAGARA=1`；`Nexus.uproject` 启用 Niagara
- test(e2e): `test_10` 补 Python 用例——`exec_python` eval/traceback 与 `file` 模式路径校验（越界、非 `.py` 均须 `arg_invalid`）；`undoRecorded` 的两条写路径差异（纯读须为 `false`；`obj.modify(False)` 只入事务缓冲、不把包标脏，其返回值即引擎自己的答案，用来交叉验证该字段不是假阳性）；`get_python_api` 内省、`target`/`query` 白名单注入拒绝（白名单是该 cap 敢默认开启的唯一依据，此前无覆盖）、`offset` 分页不重叠、`searchDoc` 按 docstring 检索、缺失 API 仍回 `engineVersion`/`pythonVersion`；`Nexus.uproject` 启用 PythonScriptPlugin（未启用时用例按 `require_tools` 自动 skip）

### Changed

- chore(plugin): NexusLink 子模块从 `Plugins/Developer/NexusLink` 迁到 `Plugins/NexusLink`；`Nexus.uproject` 启用 NexusLink / NexusLinkTestSuite
- chore(test): 新增 `_framework/test_cleanup.py`——测试前后清理 `Saved/Logs` 下 `UE-auto-launch*` / `TestReport.xml` / `Automation-*.stdout.log`、`Content/_McpTest/`、历史 `Content/_NexusTest/` 与 `Content/__nexus_*__.uasset`；session 级 purge `/Game/_McpTest` 与 `/Game/_NexusTest`（`--keep-artifacts` 时保留）；`test_103`/`104`/`105`/`106` 写入改走 `test_ns`；`.gitignore` 忽略 `Content/_NexusTest/`
- chore(test): pytest / `run_e2e.py` 自动拉起 UE **默认 headless**（`UnrealEditor-Cmd -unattended -nullrhi -NoSplash -NoSound`）；headless/命令行会话跳过 `l4_runtime`/`lua`/`requires_gui`；本地观察编辑器加 `--gui`；全量 `--gui`/`--full`
- chore(test): `ue_launcher` 会话级 `-EnableNexusMcp` 开启 MCP；示例 `bEnableMcpServer=False`，E2E 不依赖 ini
- chore(test): `build_test` 改为对本机已装的每套引擎编整个 `Nexus.uproject`（Editor=`NexusEditor`，Game=`Nexus` / WITH_EDITOR=0）；不再 `BuildPlugin` 只编 NexusLink，也不再临时改写 UncookedOnly→Runtime；隔离目录改到工程 `Saved/NexusBuildTest`（避开 `%TEMP%` 下 Rules DLL 被应用控制策略拦截 0x800711C7）；`Source` 真实拷贝、Content/Config 仍 junction；开跑前清残留 UBT / 调用 UBT 的 `dotnet` / 相关 MSBuild / VBCSCompiler；5.1 补引擎自带 dotnet 到 PATH；仅 VS2026 时按引擎 preferred 传 `-2022 -CompilerVersion=`（5.2/5.3→14.34，5.4–5.6→14.38），不要求另装 VS2022；WARNINGS 只计自有代码（跳过引擎树 C4996 与 VS2026 `not a preferred version`）；自动发现除 `LauncherInstalled.dat` 外再扫已发现引擎的兄弟目录与常见 `Epic Games` 根（补上启动器未登记的磁盘安装）
- docs: 仓库改为公开（NexusLink 示例工程）；README 移除私有/NexusWork 表述；测试策略——新功能补 **manage 每 action / get 每 named section**、默认 headless、全覆盖验证走 `--gui`；NexusLink 发版按本次变更选 headless 或 `--gui`
- chore(test): `legacy_map` 与插件 C++ 旧名表对齐（补 `get_behavior_tree`，去掉恒等 `list_runtime_widgets`）
- chore(script): 插件维护脚本迁入 NexusLink `scripts/`（`audit_capability_naming` / `audit_doc_sync`）；删除会把 AI 可见文案改回中文的 `apply_*_zh`、一次性迁移脚本（`migrate_execute_phase3` / `wrap_with_editor_caps` / `register_capabilities`）及配套 `schema_descs_zh.json`；`run_e2e` 改调插件仓审计脚本；NexusLinkTestSuite 注释同步改路径
- chore(unreal): 示例工程替换为 UE 5.7 第三人称模板（含 Combat/Platforming/SideScrolling 变体）；`EngineAssociation: 5.7`；默认关卡 `/Game/ThirdPerson/Lvl_ThirdPerson`；日常编译/E2E 跟 Association；`Nexus.uproject` 启用 ModelViewViewModel / PCG / PoseSearch / CommonUI / MoviePipeline——插件对这几个可选插件的 cap 已链接成功，不启用会让 DLL 缺 import 导致 NexusLink 加载失败
- chore(test): 跟随 NexusLink 双模块拆分（`NexusLink` Runtime + `NexusLinkEditor` Editor）——`NexusLinkTests.Build.cs` 新增 `NexusLinkEditor` 模块依赖与对应 `PrivateIncludePaths`；`CapabilityTests.cpp` 补一条 `Source/NexusLinkEditor/...` 路径的 `MakeSettingsGroupPath` 用例；`Plugins/NexusLink/scripts/audit_capability_naming.py`/`audit_doc_sync.py`/`build_tool_reference.py` 的 cap 根路径改为同时扫描两个模块目录，`audit_capability_params.py` 增加基类与模块一致性断言

### Security

- 示例工程默认关 MCP；`mcp_client` 带 Bearer；E2E 会话级 `-NexusEnableDangerousCaps`

### Fixed

- fix(test): GUI e2e 启动加 `-LiveCoding=false`，避免 `save_asset` 被 Live Coding 降级为 deferred
- fix(test): `manage_asset_lua_binding` 未知 action 由 schema enum 拦下，断言改为 `MCPError`
- fix(unlua): UnLuaTestSuite 在 UE 5.4+ 用 `SetBegunPlay` 替代直接写 `bBegunPlay`（5.8 起为 private，5.4–5.7 直接写会 C4996）
- fix(unreal): 跨版本 Target/模块——`V2`（UE4 / 5.0–5.2）/`V4`（5.3）/`V5`（5.4–5.6）/`V6`+`Unreal5_7`（5.7）/`V7`+`Unreal5_8`（5.8）；玩法变体 `NexusGameplay` ExtraModuleNames 5.6+（5.3+ 仍会因 uproject Modules 编进该模块）；AI 控制器 UPROPERTY 用基类 `UStateTreeComponent*`，5.5+ 才创建 `UStateTreeAIComponent`（5.4 无 MODULE_API 导出）；编辑器 `GetDescription` 仅 5.5+；`MakeWeakExecutionContext` 仅 5.6+；`SetBodySimulatePhysics` 仅 5.4+；冲动量去掉 `Units=cm/s`；`InputAction.h` 不再写 `EnhancedInput/Public/` 前缀；4.26 用 `NexusInputStubs`；uproject 将 StateTree/MVVM/PCG 等标为 Optional；`UEnvQueryContext_Danger` 改 `NEXUSGAMEPLAY_API`；`LogNexus` 导出 `NEXUS_API`；StateTree 实例数据宏走 `NexusGameplayVersionCompat.h`（`NG_UE_HAS_*`）
- fix(test): 全量 e2e 对齐——`skipif_ue_below` 移入 `pytest_runtest_setup`；用例统一 `cap_first` / `operations[]`；EQS 缺 cap 时 skip；`audit_capability_naming` 补 `unload`、期望数 176；GUI/PIE 对齐 `spawn_runtime_actor` 单条、`control_pie` results[]、`set_runtime_widget_property` 的 `updates[]`；补覆盖用例参数对齐真实 Schema（`rootMotion`/`anchorMin*`/`attribute`/`startFrame`/`halfHeight`/`updates[].actorName`），schema 校验失败 skip 而非 fail
- fix(test): `test_bp_graph_connect_exec` 缺 BeginPlay 时经 `manage_asset_blueprint` 补 `K2Node_Event`；`test_anim_montage_create` 创建后 `add_segment`（Mannequin Idle）并 save；`exec_command` 改用 `stat fps`（避免 `help stat` 弹 `ConsoleHelp.html`）
- fix(test): `ue_launcher` 自动拉起时跳过启动前已在听的 MCP 端口，避免本机已有 Editor 占着 `:45000` 时把 headless 新实例误接到旧进程
- fix(test): 用例与真实 Schema 对齐（此前这些 cap 因可选插件未启用而从未真跑过）——MetaSound 用 `classID`/`nodeID`/`fromNodeID`；MVVM `add_binding` 不吃参数、`remove_binding` 只认 `bindingIndex`；InputAction `remove_trigger`/`remove_modifier` 按 `className` 而非 `index`、`set_flags` 用 `consumesInput`；`not_a_real_action` 负例统一接受 schema 层 `MCPError`（IKRig / MVVM / PCG / ControlRig）
- fix(test): `test_101` 的 `f"/Game/{test_ns}"` 把已带前缀的 ns 再拼一次，拼出 `/Game//Game/...`；`test_108` 的 StringTable 与 `test_97_statetree_manage` 撞同一个 `{test_ns}/ST_Created`，先跑的占位导致 StateTree 整组 not found，改名 `StrTable_Created`；IMC 单条结果响应被压平后 `results` 为空，改走 `or [cap_first(...)]`
