# NexusLink UE 测试清单（TestId 映射表）

> **�?v1.5.0 起本清单已不再人工勾�?*。全部测试用例迁移至两层自动化框架：
>
> - **L1 C++ Automation** (`Plugins/NexusLinkTestSuite/Source/NexusLinkTests/`)：工具函�?/ 插件加载 / 工具注册表冒烟，需手动 `UEEditor-Cmd <uproject> -ExecCmds="Automation RunTests NexusLink.; Quit" -unattended -nullrhi` 触发（已�?`build_test` 入口剥离）�?
> - **L2 pytest E2E** (`nexus-unreal/Tests/`)：MCP 工具端到端，�?`python nexus-unreal/Script/run_e2e.py` �?`pytest nexus-unreal/Tests` 触发�?
>
> 本文件只维护 **"�?CHECKLIST 条目 �?自动�?TestId"** 的映射，便于回溯旧工�?/ PR 描述引用�?
>
> 查看实时运行报告�?
>
> - `nexus-unreal/Saved/Logs/Build.Log`（仅编译汇总）
> - `nexus-unreal/Saved/Logs/TestReport.xml`（L2 pytest JUnit 报告�?

---

## 快速索引：阶段 �?pytest 文件

| CHECKLIST 阶段 | 覆盖目标 | pytest 文件 | L1 补充 |
|---|---|---|---|
| 一：基础探测 | tools/list 白名�?/ editor info / output log / 日志过滤 / `get_asset_slate_widget` 错误路径 | `test_00_smoke.py` | `NexusLink.Smoke.PluginAndRegistry` |
| 二：控制台命�?+ 截图 | `exec_command`、`capture_viewport` | `test_10_editor.py` | �?|
| 三：Struct + DataTable | `manage_struct_field` / `manage_asset_data_table` 批量（add/remove/set 错误路径�?| `test_20_struct_datatable.py` | `NexusLink.Utils.PinType.ParsePrimitives` |
| 四：Blueprint + Graph | 变量/组件/图表/连线批量 | `test_30_blueprint.py` | `NexusLink.Utils.PinType.ParsePrimitives` |
| 五：Widget Blueprint | `manage_widget` + `set_property(widgetName)` | `test_40_widget.py` | �?|
| 六：Material | `manage_material` / `manage_material_wires` / 两步�?| `test_50_material.py` | �?|
| 七：资产引用 | `get_asset_refs` 批量方向 | `test_60_asset_refs.py` | �?|
| 八：Gameplay Tags | `get_gameplay_tags` | `test_70_gameplay_tags.py` | �?|
| 九：AI + 动画资产 | BT / AnimBP / Montage + `get_actor_animation` 错误路径 | `test_80_ai_anim_assets.py` | �?|
| 十：资产管理 | `create_data_asset` / `delete_asset` / `rename_asset` / 批量 `get_asset` | `test_90_asset_mgmt.py` | `NexusLink.Utils.AssetUtils.FindClass` |
| 十一：PIE Runtime | Actor / Widget / Animation / Lua | `test_95_pie_runtime.py` | �?|
| 十二：清�?+ 日志健康 | `_McpTest` 命名空间清理 + `get_output_log` | `test_ns` fixture + `test_90_asset_mgmt.py::test_log_health_*` | �?|

---

## 条目级映�?

格式：`<�?CHECKLIST �?` �?pytest 文件 `::` 用例名（�?L1 Test 名）�?
多条目合并进单个用例的，用同一 TestId；`-` 表示已由 fixture / session 级别的前后置逻辑覆盖，无独立用例�?

### 阶段一：基础探测

| # | TestId |
|---|---|
| 1.0（新�?| `test_00_smoke.py::test_tools_list_nonempty`（tools/list �?40 �?+ 核心工具白名单必须在册） |
| 1.1 | `test_00_smoke.py::test_get_editor_info` |
| 1.2 | `test_00_smoke.py::test_get_output_log_basic` |
| 1.3 | `test_00_smoke.py::test_get_output_log_filtered_offset` |
| 1.4�?.6 | `test_00_smoke.py::test_set_log_capture_filter_roundtrip` |
| 1.7（新�?| `test_00_smoke.py::test_get_slate_widget_error_path`（`get_asset_slate_widget` 错误路径：传 `0x0` 地址验证工具级拒绝不 crash�?|

### 阶段二：控制台命�?

| # | TestId |
|---|---|
| 2.1 | `test_10_editor.py::test_exec_command_stat_fps` |
| 2.2 | `test_10_editor.py::test_capture_viewport_deferred`（按 Nexus 规范�?7 条不自动截图�?|

### 阶段三：Struct + DataTable

| # | TestId |
|---|---|
| 3.1 | fixture `struct_path` |
| 3.2 | `test_20_struct_datatable.py::test_struct_field_batch_init` |
| 3.3 | `test_20_struct_datatable.py::test_struct_fields_visible` |
| 3.4 | `test_20_struct_datatable.py::test_struct_field_rename_retype` |
| 3.5 | `test_20_struct_datatable.py::test_save_struct` |
| 3.6 | fixture `datatable_path` |
| 3.7 | （覆盖在 3.3 / 10.4 �?`get_asset` 多资产概览中�?|
| 3.8 | `test_20_struct_datatable.py::test_datatable_row_batch_add` |
| 3.9 | `test_20_struct_datatable.py::test_datatable_row_get_batch` |
| 3.10 | （由 3.8 + 3.11 间接覆盖；如需专项用例可补加） |
| 3.11 | `test_20_struct_datatable.py::test_datatable_row_remove` |
| 3.12 | `test_20_struct_datatable.py::test_save_datatable` |
| 3.13 | `test_20_struct_datatable.py::test_datatable_set_row_error_path`（`manage_asset_data_table` action=set 错误路径：不存在�?`rowName`+`fieldName` 验证批量契约 `totalCount/failCount/results[].error`�?|

### 阶段四：Blueprint + Graph

| # | TestId |
|---|---|
| 4.1 | fixture `bp_path` |
| 4.2 | `test_30_blueprint.py::test_bp_variable_batch_add` |
| 4.3 | `test_30_blueprint.py::test_bp_get_asset_all_section` |
| 4.4�?.5 | `test_30_blueprint.py::test_bp_defaults_read_write` |
| 4.6 | `test_30_blueprint.py::test_bp_get_defaults_section` |
| 4.7 | `test_30_blueprint.py::test_bp_component_batch_add_remove` |
| 4.8�?.12 | `test_30_blueprint.py::test_bp_graph_roundtrip` |
| 4.13 | `test_30_blueprint.py::test_bp_save` |

### 阶段五：Widget Blueprint

| # | TestId |
|---|---|
| 5.1 | fixture `wbp_path` |
| 5.2 | `test_40_widget.py::test_widget_tree_batch_build` |
| 5.3 | `test_40_widget.py::test_widget_tree_filter` |
| 5.4�?.5 | `test_40_widget.py::test_widget_set_text` |
| 5.6�?.7 | `test_40_widget.py::test_widget_remove_one` |
| 5.8�?.9 | `test_40_widget.py::test_widget_save` |

### 阶段六：Material

| # | TestId |
|---|---|
| 6.1 | fixture `mat_path` |
| 6.2 | `test_50_material.py::test_create_decal` |
| 6.3 | `test_50_material.py::test_material_overview` |
| 6.4�?.8 | `test_50_material.py::test_material_node_add_connect_remove` |
| 6.9�?.11 | `test_50_material.py::test_material_two_step_texture_param` |
| 6.12�?.15 | （仅当主机项目安装相应资产时生效；用例在 `test_50` �?skeleton fixture 样式跳过�?|
| 6.16 | `test_50_material.py::test_material_save_all` |

### 阶段七：资产引用

| # | TestId |
|---|---|
| 7.1 | `test_60_asset_refs.py::test_dependencies_batch` |
| 7.2 | `test_60_asset_refs.py::test_referencers` |
| 7.3 | `test_60_asset_refs.py::test_referencers_with_filter` |

### 阶段八：Gameplay Tags

| # | TestId |
|---|---|
| 8.1 | `test_70_gameplay_tags.py::test_tags_hierarchy` |
| 8.2 | （由 8.1 覆盖；嵌套层级数据在 hierarchy 返回中已校验�?|
| 8.3 | `test_70_gameplay_tags.py::test_tags_asset_read` |

### 阶段九：AI + 动画资产

| # | TestId |
|---|---|
| 9.1 | fixture `template_skeleton` |
| 9.2 | （由 `search_asset` 通用路径覆盖�?|
| 9.3 | `test_80_ai_anim_assets.py::test_behavior_tree_create` |
| 9.4 | `test_80_ai_anim_assets.py::test_behavior_tree_asset` |
| 9.5 | `test_80_ai_anim_assets.py::test_behavior_tree_blackboard` |
| 9.6�?.7 | `test_80_ai_anim_assets.py::test_anim_blueprint_create` |
| 9.8�?.9 | `test_80_ai_anim_assets.py::test_anim_montage_create` |
| 9.10 | `test_80_ai_anim_assets.py::test_save_all_anim_assets` |
| 9.11（新�?| `test_80_ai_anim_assets.py::test_get_actor_animation_error_path`（`get_actor_animation` 错误路径：不存在 Actor 验证 `totalCount/results[].error`�?|

### 阶段十：资产管理

| # | TestId |
|---|---|
| 10.1�?0.3 | `test_90_asset_mgmt.py::test_create_data_asset_rename_list` |
| 10.4 | `test_90_asset_mgmt.py::test_multi_asset_overview` |
| 10.5 | （`compile_blueprint` 已移除；结构变更由各 `manage_*` 路径内编�?+ `save_asset` 用例覆盖�?|
| 10.6 | （由�?save_asset 用例覆盖�?|

### 阶段十一：PIE Runtime

| # | TestId |
|---|---|
| 11.1 / 11.4 / 11.55 | `test_95_pie_runtime.py::test_pie_status_is_running`�? `pie` fixture 生命周期�?|
| 11.2 / 11.56 | fixture `set_log_capture_filter` / 1.4�?.6 已单�?|
| 11.3 / 11.54 | `pie` fixture teardown |
| 11.5 | `test_95_pie_runtime.py::test_pie_exec_slomo` |
| 11.6�?1.8 | `test_95_pie_runtime.py::test_list_actors_contains_spawned`�? fixture `spawned_actors`�?|
| 11.9�?1.12 | `test_95_pie_runtime.py::test_actor_property_batch_write` / `test_actor_property_multi_path` / `test_actor_property_multi_actor` |
| 11.13�?1.14 | `test_95_pie_runtime.py::test_actor_diagnose_transform` |
| 11.15 | （由 `get_property` 同功能覆盖，section=components�?|
| 11.16�?1.17 | `test_95_pie_runtime.py::test_diff_actors` |
| 11.18 | `test_95_pie_runtime.py::test_runtime_destroy_one` |
| 11.19�?1.25 | （动�?模板角色用例�?pytest 中按模板可用性跳过；UE Automation 中由 AssetUtils 测试间接覆盖类型解析链） |
| 11.26�?1.28 | `test_95_pie_runtime.py::test_spawn_and_interact_widget` |
| 11.29�?1.31 | `test_95_pie_runtime.py::test_runtime_widget_batch_read` |
| 11.32 | （BT 运行时需 AIController，本轮按需人工补加用例�?|
| 11.33 | `test_95_pie_runtime.py::test_lua_version`（`get_lua(value, _VERSION)`；需 UnLua，否�?skip�?|
| 11.34 | `test_95_pie_runtime.py::test_lua_eval`（`manage_lua(eval, "return 1+1")`；需 UnLua�?|
| 11.35 | `test_95_pie_runtime.py::test_lua_memory_gc`（`get_lua(memory) �?manage_lua(gc) �?get_lua(memory)`；需 UnLua�?|
| 11.36�?1.41 | （UnLua 其余 section：`env` / `metatable` / `loaded` / `stack` / `binding` / `object` �?`manage_lua` �?`dofile`/`set`/`hotreload` 按需补加�?|
| 11.42�?1.50 | （Lua 绑定分析用例�?UnLua 可用性跳过；有需要可在本文件�?`test_95` 追加�?|
| 11.51 | （按规范�?7 条不自动截图�?|
| 11.52 | （由阶段十二的日志健康用例覆盖） |
| 11.53 | fixture `spawned_actors` teardown + `test_runtime_destroy_one` |

### 阶段十二：清�?+ 日志健康

| # | TestId |
|---|---|
| 12.1�?2.2 | `conftest.py::test_ns` session-level teardown（删�?`/Game/_McpTest/<ts>/` 下全部资产） |
| 12.3�?2.4 | （由人工白名单扫描；可作 future work 补作 pytest 用例�?|
| 12.5 | `test_90_asset_mgmt.py::test_log_health_ensure_failed_is_zero` |
| 12.6 | `test_90_asset_mgmt.py::test_log_health_no_crash` |

---

## 已知白名单（可忽略的日志�?

| 分类 | 日志特征 | 原因 |
|------|---------|------|
| `LogMagicLeap Warning` | `VR disabled because ZI is not enabled` | 无设备，启动期固定出�?|
| `LogNexusMcpDispatcher Warning` | `未知方法: prompts/list` / `resources/list` | MCP 客户端探测可选端点，正常 |
| `LogLinker Warning` | `未能加载 {FileName}` | UE 加载重试机制，最终成功无�?|
| `LogK2Compiler Warning` | `name XXX is already taken` | 变量命名冲突自动处理 |

---

## 新增 MCP 工具的测试规�?

1. �?`nexus-unreal/Tests/test_*.py` 中对应阶段文件下追加**至少一�?happy-path** 用例（`pytest Tests -k <tool_name>` 至少能命�?1 条）�?
2. 若工�?happy-path 依赖外部产物（UI 交互拿地址、PIE 运行中的 Actor、模板骨骼等）不便稳定复现，追加**错误路径用例**（传不存在的 `actorName`/`functionName`/`rowName`/`fieldName`/非法 hex 地址等），断言契约�?
   - 批量工具必须返回 `{totalCount, failCount, results:[{error}]}` 三要素（不是 top-level `MCPError`）；参�?`test_datatable_set_row_error_path` / `test_get_actor_animation_error_path`�?
   - 非批量工具（�?`get_asset_slate_widget`）允�?`MCPError` �?payload �?`error`/`invalid`/`not found`/`null` 两种拒绝形态；参�?`test_get_slate_widget_error_path`�?
3. 若该工具有非 MCP 依赖的纯 C++ 工具函数（类型解析、字符串匹配、数学等），同步�?`Plugins/NexusLinkTestSuite/Source/NexusLinkTests/Private/Tests/` �?`IMPLEMENT_SIMPLE_AUTOMATION_TEST`�?
4. 工具调用参数变化或新�?section 时，更新本文件对应行�?TestId 注释，保持旧 PR 引用可追溯�?
