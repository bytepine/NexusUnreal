# Changelog — NexusUnreal（示例工程）

> **NexusLink 插件**变更记录在公开仓 [NexusLink CHANGELOG](https://github.com/bytepine/NexusLink/blob/master/CHANGELOG.md)。

---

## [Unreleased]

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
