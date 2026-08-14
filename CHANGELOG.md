# Changelog — NexusUnreal（示例工程）

> **NexusLink 插件**变更记录在公开仓 [NexusLink CHANGELOG](https://github.com/bytepine/NexusLink/blob/master/CHANGELOG.md)。

---

## [Unreleased]

- test(e2e): 新领域 Capability — `test_108` StringTable/Font、`test_109` FoliageType、`test_110` Paper2D、`test_111` GeometryCollection、`test_112` Media、`test_113` CommonUI、`test_114` MoviePipeline；GAS 扩 CueNotify
- test(e2e): 钉写路径 — MF 写图、ABP Slot/Blend/IK/AimOffset、Niagara 空白 `add_emitter`+模块栈、WBP 动画绑定/`remove_key`、`test_98` Sequencer 绑定级 key
- fix(test): `test_bp_graph_connect_exec` 缺 BeginPlay 时经 `manage_asset_blueprint` 补 `K2Node_Event`
- fix(test): `test_anim_montage_create` 创建后 `add_segment`（Mannequin Idle）并 save——空白 Montage 时长为 0，后续 `play_montage` 恒失败
- fix(test): 全量 e2e 测试侧对齐——`skipif_ue_below` 移入 `pytest_runtest_setup`（避免 module fixture 先 ERROR）；用例统一 `cap_first` / `operations[]`；EQS 缺 cap 时 skip；audit 补 `unload`、期望数 176
- fix(test): `audit_capability_naming` 补齐动词 `unload`、期望 Capability 数 175→176（对齐 `unload_asset`）
- chore(test): `ue_launcher` 改用会话级 `-EnableNexusMcp` 开启 MCP，移除写 `EditorPerProjectUserSettings.ini` 与 `-ini:...bEnableMcpServer=True` 双路径
- chore(test): `build_test` Game 阶段兼容 `NexusLink.uplugin` 已为 `Type: Runtime`（不再强制要求源为 Editor）
- docs: 仓库改为公开，定位为 NexusLink 示例工程；README 移除私有表述
- docs: README 移除 NexusWork 相关说明
- chore(test): pytest / `run_e2e.py` 自动拉起 UE **默认改回 headless**（`UnrealEditor-Cmd -unattended -nullrhi -NoSplash -NoSound`），避免无窗口弹窗与对话框阻断；本地需观察编辑器时加 `--gui`
- chore(test): 新增 `_framework/test_cleanup.py`——测试前后自动清理 `Saved/Logs` 下 `UE-auto-launch*` / `TestReport.xml` / `Automation-*.stdout.log` 与 `Content/_McpTest/`；session 级 purge `/Game/_McpTest` 下全部 UE 资产（`--keep-artifacts` 时保留）
- fix(test): `Config/DefaultEditorPerProjectUserSettings.ini` 默认 `bEnableMcpServer=True`；`ue_launcher` 启动前写入 `Saved/Config/.../EditorPerProjectUserSettings.ini` 并追加 `-ini:...bEnableMcpServer=True`，headless 自动拉起可连 MCP
- feat(test): `capability_probe` + `asset_helpers`——SearchMode 下用 `search_capabilities` 替代 `tools/list` 门禁；资产搜索统一 `cap_first`，缺失时在 `test_ns` 内创建；`ue_launcher` 强制 `WITH_GAS=1`/`WITH_NIAGARA=1`；`Nexus.uproject` 启用 Niagara
- chore(test): headless/命令行会话（`--headless` 或 `--ue-root` 自动拉起）统一跳过 `l4_runtime`、`lua`、`requires_gui`；`run_e2e.py` 自动拉起时默认传 `--headless`
- test(e2e): 补缺口覆盖——`test_90` DataAsset get/manage、delete、export；`test_94` manage_asset_level 磁盘 spawn/remove；`test_96` GAS runtime ASC/apply_effect；`test_95` destroy/set_runtime_widget、Lua metatable/object；`test_10` get_asset_lua_binding
- fix(test): GUI/PIE 用例对齐 `spawn_runtime_actor` 单条 API、`control_pie` results[] 包装、`set_runtime_widget_property` 的 `updates[]`
- docs(test): 明确策略——新功能补测、默认 headless、命令行不可覆盖打标走 GUI、全量 `--gui`/`--full`
- fix(test): `exec_command` 用例避免 `help stat`（UE 会弹 `ConsoleHelp.html`），改用 `stat fps`
