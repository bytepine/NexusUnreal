# NexusLink UE test checklist (TestId map)

[中文](TEST_CHECKLIST.md) | English

> **Since v1.5.0, this checklist is no longer checked off manually.** All cases have moved to a two-layer automated framework:
>
> - **L1 C++ Automation** (`Plugins/NexusLinkTestSuite/Source/NexusLinkTests/`): utility functions / plugin loading / registry smoke tests. Run manually with `UEEditor-Cmd <uproject> -ExecCmds="Automation RunTests NexusLink.; Quit" -unattended -nullrhi`; these tests have been separated from `build_test`.
> - **L2 pytest E2E** (`nexus-unreal/Tests/`): end-to-end MCP tools, run through `python nexus-unreal/Script/run_e2e.py` or `pytest nexus-unreal/Tests`.
>
> This file only maintains the **old CHECKLIST entry → automated TestId** map so references in earlier tickets / PR descriptions remain traceable.
>
> Current execution reports:
>
> - `nexus-unreal/Saved/Logs/Build.Log` (build summary only).
> - `nexus-unreal/Saved/Logs/TestReport.xml` (L2 pytest JUnit report).

---

## Quick index: stage → pytest file

| CHECKLIST stage | Coverage | pytest file | Additional L1 |
|---|---|---|---|
| 1: basic probes | tools/list allowlist / editor info / output log / log filtering / `get_asset_slate_widget` error path | `test_00_smoke.py` | `NexusLink.Smoke.PluginAndRegistry` |
| 2: console + capture | `ExecCommand`, `CaptureViewport` | `test_10_editor.py` | — |
| 3: Struct + DataTable | `manage_struct_field` / `ManageAssetDataTable` batch add/remove/set error paths | `test_20_struct_datatable.py` | `NexusLink.Utils.PinType.ParsePrimitives` |
| 4: Blueprint + Graph | Batch variables/components/graphs/connections | `test_30_blueprint.py` | `NexusLink.Utils.PinType.ParsePrimitives` |
| 5: Widget Blueprint | `manage_widget` + `SetProperty(WidgetName)` | `test_40_widget.py` | — |
| 6: Material | `manage_material` / `manage_material_wires` / two-step workflow | `test_50_material.py` | — |
| 7: asset references | `GetAssetRefs` batch directions | `test_60_asset_refs.py` | — |
| 8: Gameplay Tags | `GetGameplayTags` | `test_70_gameplay_tags.py` | — |
| 9: AI + animation assets | BT / AnimBP / Montage + `get_actor_animation` error path | `test_80_ai_anim_assets.py` | — |
| 10: asset management | `create_data_asset` / `DeleteAsset` / `RenameAsset` / batch `GetAsset` | `test_90_asset_mgmt.py` | `NexusLink.Utils.AssetUtils.FindClass` |
| 11: PIE Runtime | Actor / Widget / Animation / Lua | `test_95_pie_runtime.py` | — |
| 12: cleanup + log health | `_McpTest` namespace cleanup + `GetOutputLog` | `test_ns` fixture + `test_90_asset_mgmt.py::test_log_health_*` | — |

---

## Entry-level map

Format: `<old CHECKLIST number>` → pytest file `::` case name (or L1 test name).
Multiple entries merged into one case share its TestId. `-` means fixture/session setup and teardown already cover the entry, without a separate case.

### Stage 1: basic probes

| # | TestId |
|---|---|
| 1.0 (new) | `test_00_smoke.py::test_tools_list_nonempty` (tools/list ≥ 40 and core-tool allowlist must be registered) |
| 1.1 | `test_00_smoke.py::test_get_editor_info` |
| 1.2 | `test_00_smoke.py::test_get_output_log_basic` |
| 1.3 | `test_00_smoke.py::test_get_output_log_filtered_offset` |
| 1.4–1.6 | `test_00_smoke.py::test_set_log_capture_filter_roundtrip` |
| 1.7 (new) | `test_00_smoke.py::test_get_slate_widget_error_path` (`get_asset_slate_widget`: address `0x0` must be rejected at tool level without crashing) |

### Stage 2: console commands

| # | TestId |
|---|---|
| 2.1 | `test_10_editor.py::test_exec_command_stat_fps` |
| 2.2 | `test_10_editor.py::test_capture_viewport_deferred` (no automatic screenshots under Nexus convention 7) |

### Stage 3: Struct + DataTable

| # | TestId |
|---|---|
| 3.1 | fixture `struct_path` |
| 3.2 | `test_20_struct_datatable.py::test_struct_field_batch_init` |
| 3.3 | `test_20_struct_datatable.py::test_struct_fields_visible` |
| 3.4 | `test_20_struct_datatable.py::test_struct_field_rename_retype` |
| 3.5 | `test_20_struct_datatable.py::test_save_struct` |
| 3.6 | fixture `datatable_path` |
| 3.7 | Covered by multi-asset `GetAsset` overviews in 3.3 / 10.4 |
| 3.8 | `test_20_struct_datatable.py::test_datatable_row_batch_add` |
| 3.9 | `test_20_struct_datatable.py::test_datatable_row_get_batch` |
| 3.10 | Indirectly covered by 3.8 + 3.11; add dedicated cases if needed |
| 3.11 | `test_20_struct_datatable.py::test_datatable_row_remove` |
| 3.12 | `test_20_struct_datatable.py::test_save_datatable` |
| 3.13 | `test_20_struct_datatable.py::test_datatable_set_row_error_path` (`ManageAssetDataTable` Action=set with missing `RowName`+`FieldName` checks batch `TotalCount/failCount/results[].error`) |

### Stage 4: Blueprint + Graph

| # | TestId |
|---|---|
| 4.1 | fixture `bp_path` |
| 4.2 | `test_30_blueprint.py::test_bp_variable_batch_add` |
| 4.3 | `test_30_blueprint.py::test_bp_get_asset_all_section` |
| 4.4–4.5 | `test_30_blueprint.py::test_bp_defaults_read_write` |
| 4.6 | `test_30_blueprint.py::test_bp_get_defaults_section` |
| 4.7 | `test_30_blueprint.py::test_bp_component_batch_add_remove` |
| 4.8–4.12 | `test_30_blueprint.py::test_bp_graph_roundtrip` |
| 4.13 | `test_30_blueprint.py::test_bp_save` |

### Stage 5: Widget Blueprint

| # | TestId |
|---|---|
| 5.1 | fixture `wbp_path` |
| 5.2 | `test_40_widget.py::test_widget_tree_batch_build` |
| 5.3 | `test_40_widget.py::test_widget_tree_filter` |
| 5.4–5.5 | `test_40_widget.py::test_widget_set_text` |
| 5.6–5.7 | `test_40_widget.py::test_widget_remove_one` |
| 5.8–5.9 | `test_40_widget.py::test_widget_save` |

### Stage 6: Material

| # | TestId |
|---|---|
| 6.1 | fixture `mat_path` |
| 6.2 | `test_50_material.py::test_create_decal` |
| 6.3 | `test_50_material.py::test_material_overview` |
| 6.4–6.8 | `test_50_material.py::test_material_node_add_connect_remove` |
| 6.9–6.11 | `test_50_material.py::test_material_two_step_texture_param` |
| 6.12–6.15 | Requires matching assets installed in the host project; `test_50` skips through skeleton-style fixtures |
| 6.16 | `test_50_material.py::test_material_save_all` |

### Stage 7: asset references

| # | TestId |
|---|---|
| 7.1 | `test_60_asset_refs.py::test_dependencies_batch` |
| 7.2 | `test_60_asset_refs.py::test_referencers` |
| 7.3 | `test_60_asset_refs.py::test_referencers_with_filter` |

### Stage 8: Gameplay Tags

| # | TestId |
|---|---|
| 8.1 | `test_70_gameplay_tags.py::test_tags_hierarchy` |
| 8.2 | Covered by 8.1, which validates nested hierarchy data in the hierarchy response |
| 8.3 | `test_70_gameplay_tags.py::test_tags_asset_read` |

### Stage 9: AI + animation assets

| # | TestId |
|---|---|
| 9.1 | fixture `template_skeleton` |
| 9.2 | Covered by the generic `SearchAsset` path |
| 9.3 | `test_80_ai_anim_assets.py::test_behavior_tree_create` |
| 9.4 | `test_80_ai_anim_assets.py::test_behavior_tree_asset` |
| 9.5 | `test_80_ai_anim_assets.py::test_behavior_tree_blackboard` |
| 9.6–9.7 | `test_80_ai_anim_assets.py::test_anim_blueprint_create` |
| 9.8–9.9 | `test_80_ai_anim_assets.py::test_anim_montage_create` |
| 9.10 | `test_80_ai_anim_assets.py::test_save_all_anim_assets` |
| 9.11 (new) | `test_80_ai_anim_assets.py::test_get_actor_animation_error_path` (`get_actor_animation` with a missing Actor verifies `TotalCount/results[].error`) |

### Stage 10: asset management

| # | TestId |
|---|---|
| 10.1–10.3 | `test_90_asset_mgmt.py::test_create_data_asset_rename_list` |
| 10.4 | `test_90_asset_mgmt.py::test_multi_asset_overview` |
| 10.5 | `CompileBlueprint` was removed; structural compilation is covered inside `manage_*` paths and by `SaveAsset` cases |
| 10.6 | Covered by the `SaveAsset` cases |

### Stage 11: PIE Runtime

| # | TestId |
|---|---|
| 11.1 / 11.4 / 11.55 | `test_95_pie_runtime.py::test_pie_status_is_running` (`pie` fixture lifecycle) |
| 11.2 / 11.56 | fixture `SetLogCaptureFilter` / 1.4–1.6 already tested separately |
| 11.3 / 11.54 | `pie` fixture teardown |
| 11.5 | `test_95_pie_runtime.py::test_pie_exec_slomo` |
| 11.6–11.8 | `test_95_pie_runtime.py::test_list_actors_contains_spawned` (fixture `spawned_actors`) |
| 11.9–11.12 | `test_95_pie_runtime.py::test_actor_property_batch_write` / `test_actor_property_multi_path` / `test_actor_property_multi_actor` |
| 11.13–11.14 | `test_95_pie_runtime.py::test_actor_diagnose_transform` |
| 11.15 | Equivalent coverage through `get_property`, Section=components |
| 11.16–11.17 | `test_95_pie_runtime.py::test_diff_actors` |
| 11.18 | `test_95_pie_runtime.py::test_runtime_destroy_one` |
| 11.19–11.25 | Animation-template character cases skip according to template availability in pytest; UE Automation AssetUtils tests indirectly cover the type-resolution chain |
| 11.26–11.28 | `test_95_pie_runtime.py::test_spawn_and_interact_widget` |
| 11.29–11.31 | `test_95_pie_runtime.py::test_runtime_widget_batch_read` |
| 11.32 | Behavior-tree runtime requires AIController; add cases manually as needed |
| 11.33 | `test_95_pie_runtime.py::test_lua_version` (`get_lua(value, _VERSION)`; requires UnLua, otherwise skips) |
| 11.34 | `test_95_pie_runtime.py::test_lua_eval` (`manage_lua(eval, "return 1+1")`; requires UnLua) |
| 11.35 | `test_95_pie_runtime.py::test_lua_memory_gc` (`get_lua(memory) → manage_lua(gc) → get_lua(memory)`; requires UnLua) |
| 11.36–11.41 | Add remaining UnLua `env` / `metatable` / `loaded` / `stack` / `binding` / `object` sections and `manage_lua` `dofile`/`set`/`hotreload` cases as needed |
| 11.42–11.50 | Lua-binding analysis cases skip according to UnLua availability; add entries here or in `test_95` as needed |
| 11.51 | No automatic screenshots under convention 7 |
| 11.52 | Covered by stage 12 log-health cases |
| 11.53 | fixture `spawned_actors` teardown + `test_runtime_destroy_one` |

### Stage 12: cleanup + log health

| # | TestId |
|---|---|
| 12.1–12.2 | `conftest.py::test_ns` session-level teardown deletes all assets under `/Game/_McpTest/<ts>/` |
| 12.3–12.4 | Manual allowlist scan; future pytest cases may be added |
| 12.5 | `test_90_asset_mgmt.py::test_log_health_ensure_failed_is_zero` |
| 12.6 | `test_90_asset_mgmt.py::test_log_health_no_crash` |

---

## Known allowlist (ignorable logs)

| Category | Log signature | Reason |
|------|---------|------|
| `LogMagicLeap Warning` | `VR disabled because ZI is not enabled` | No device; consistently appears during startup |
| `LogNexusMcpDispatcher Warning` | `未知方法: prompts/list` / `resources/list` | Normal MCP-client probing of optional endpoints |
| `LogLinker Warning` | `未能加载 {FileName}` | UE retries loading; harmless if it ultimately succeeds |
| `LogK2Compiler Warning` | `name XXX is already taken` | Automatic resolution of variable-name conflicts |

---

## Test conventions for new MCP tools

1. Add **at least one happy-path** case to the matching stage file in `nexus-unreal/Tests/test_*.py`; `pytest Tests -k <tool_name>` must match at least one case.
2. If the happy path depends on external artifacts that are difficult to reproduce reliably (UI-derived addresses, PIE Actors, template skeletons), add an **error-path case** with nonexistent `ActorName`/`FunctionName`/`RowName`/`FieldName`, invalid hex addresses, etc., asserting the contract:
   - Batch tools must return all three elements `{TotalCount, failCount, results:[{error}]}`, rather than a top-level `MCPError`. See `test_datatable_set_row_error_path` / `test_get_actor_animation_error_path`.
   - Nonbatch tools such as `get_asset_slate_widget` may reject with either `MCPError` or payload `error`/`invalid`/`not found`/`null`. See `test_get_slate_widget_error_path`.
3. If the tool has pure C++ helpers independent of MCP (type parsing, string matching, mathematics, etc.), also add `IMPLEMENT_SIMPLE_AUTOMATION_TEST` in `Plugins/NexusLinkTestSuite/Source/NexusLinkTests/Private/Tests/`.
4. When call parameters change or sections are added, update the corresponding row/TestId comments here so old PR references remain traceable.
