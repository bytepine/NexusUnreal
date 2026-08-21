# Changelog — NexusUnreal（示例工程）

> **NexusLink 插件**变更记录在公开仓 [NexusLink CHANGELOG](https://github.com/bytepine/NexusLink/blob/master/CHANGELOG.md)。

---

## [Unreleased]

### Added

- test(e2e): 新领域与写路径——`test_108` StringTable/Font、`test_109` FoliageType、`test_110` Paper2D、`test_111` GeometryCollection、`test_112` Media、`test_113` CommonUI、`test_114` MoviePipeline；GAS 扩 CueNotify；钉写 MF 写图、ABP Slot/Blend/IK/AimOffset、Niagara 空白 `add_emitter`+模块栈、WBP 动画绑定/`remove_key`、`test_98` Sequencer 绑定级 key；缺口 `test_90` DataAsset、`test_94` manage_asset_level spawn/remove、`test_96` GAS runtime、`test_95` widget/Lua、`test_10` get_asset_lua_binding
- feat(test): `capability_probe` + `asset_helpers`——SearchMode 下用 `search_capabilities` 替代 `tools/list` 门禁；资产搜索统一 `cap_first`，缺失时在 `test_ns` 内创建；`ue_launcher` 强制 `WITH_GAS=1`/`WITH_NIAGARA=1`；`Nexus.uproject` 启用 Niagara

### Changed

- chore(test): 新增 `_framework/test_cleanup.py`——测试前后清理 `Saved/Logs` 下 `UE-auto-launch*` / `TestReport.xml` / `Automation-*.stdout.log` 与 `Content/_McpTest/`；session 级 purge `/Game/_McpTest`（`--keep-artifacts` 时保留）
- chore(test): pytest / `run_e2e.py` 自动拉起 UE **默认 headless**（`UnrealEditor-Cmd -unattended -nullrhi -NoSplash -NoSound`）；headless/命令行会话跳过 `l4_runtime`/`lua`/`requires_gui`；本地观察编辑器加 `--gui`；全量 `--gui`/`--full`
- chore(test): `ue_launcher` 会话级 `-EnableNexusMcp` 开启 MCP；`Config/DefaultEditorPerProjectUserSettings.ini` 默认 `bEnableMcpServer=True`（不再写 Saved ini / `-ini:...` 双路径）
- chore(test): `build_test` Game 阶段将 `UncookedOnly`/`Editor` 临时改写为 `Runtime` 做 `WITH_EDITOR=0` 编译探针
- docs: 仓库改为公开（NexusLink 示例工程）；README 移除私有/NexusWork 表述；测试策略——新功能补测、默认 headless、命令行不可覆盖打标走 GUI
- chore(test): `legacy_map` 与插件 C++ 旧名表对齐（补 `get_behavior_tree`，去掉恒等 `list_runtime_widgets`）

### Fixed

- fix(test): 全量 e2e 对齐——`skipif_ue_below` 移入 `pytest_runtest_setup`；用例统一 `cap_first` / `operations[]`；EQS 缺 cap 时 skip；`audit_capability_naming` 补 `unload`、期望数 176；GUI/PIE 对齐 `spawn_runtime_actor` 单条、`control_pie` results[]、`set_runtime_widget_property` 的 `updates[]`
- fix(test): `test_bp_graph_connect_exec` 缺 BeginPlay 时经 `manage_asset_blueprint` 补 `K2Node_Event`；`test_anim_montage_create` 创建后 `add_segment`（Mannequin Idle）并 save；`exec_command` 改用 `stat fps`（避免 `help stat` 弹 `ConsoleHelp.html`）
