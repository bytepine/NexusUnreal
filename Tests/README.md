# NexusUnreal — pytest E2E 测试

## GAS 诊断与联机复测

`test_120_gas_diagnostics.py` 在 PIE 验证诊断只读、已有技能激活、事件捕获与停止；标记 `l4_runtime`，用 `py Script/run_e2e.py --gui -k gas_diagnostics` 执行。测试依赖示例工程原生诊断类和 `Config/DefaultGameplayTags.ini`，不以 skip 代替功能通过。

先编译 UE 5.7 的 NexusEditor，再运行：

```sh
py Script/gas_network_retest.py --ue-root <UE_5.7-directory> --repeat 10
```

工具启动隐藏的独立 `-server` / `-game` / `-game` 进程，使用 Engine Entry 地图和显式 `NexusDiagnosticGameMode`，不改默认 GameMode；可用 `--uproject` 指向其他已编译的示例工程副本。结束时只关闭本次创建的进程。日志、生成的用例、证据和 JUnit 默认保存在 `Saved/GasRetest/`。

覆盖：未授予、缺少必需标签、阻止标签、冷却、消耗不足、预测客户端激活但服务器拒绝，以及恢复条件后的 LocalPredicted / ServerOnly 成功。观察客户端检查复制的提交计数，不要求它能看到其他玩家的技能列表。能力文档与 JSON 用例格式见 [GAS replay](../Plugins/NexusLink/docs/gas-retest.md)。

本目录为 **NexusUnreal 示例工程**内的 NexusLink L2 回归测试实现。

批量调用中只要有失败就返回 `isError=true`；预期失败用 `assert_tool_error(mcp.try_call(...))` 同时校验错误标记和 `structuredContent`，再检查 `FailureCount`、`bRolledBack` 与逐项结果。不要以请求未抛异常代替验证回滚状态。蓝图 CDO 或运行时控件依赖编译后的类，写入后先编译；网格、纹理与动画写入使用 `test_ns` 内的副本。

通用说明（工具模型、过滤）见 [NexusLink docs/testing.md](https://github.com/bytepine/NexusLink/blob/master/docs/testing.md)。

## 测试策略（必遵）

| 场景 | 做法 |
|------|------|
| **新功能 / 新 Capability** | 在对应 `test_*.py` 覆盖该 cap 的 **每个 manage `operations[].action`** 与 MultiSection get 的 **每个 named section**；写入走 `test_ns`（`/Game/_McpTest/<ts>/`）；session 结束会 purge `_McpTest` 与历史 `_NexusTest` |
| **覆盖门禁** | `py Script/audit_e2e_coverage.py`（扫描 NexusLink / NexusLinkExt 的 Runtime 与 Editor 模块，对照 C++ `RegisterActions` / `GetSectionNames` 与 Python 实际调用参数；缺项或空扫描 exit 1，不启动 UE） |
| **日常 / CI / 开发自测** | **默认命令行 headless**：`py Script/run_e2e.py`（`UEEditor-Cmd -nullrhi`，快、无窗口） |
| **命令行无法覆盖** | 用例打标 `l4_runtime` / `lua` / `requires_gui`；headless 自动 skip，须在 **GUI** 下验证 |
| **全量回归 / 全覆盖验证** | **必须 GUI**：`py Script/run_e2e.py --gui` 或 `--full`（含 PIE、UnLua、视口/RHI 等） |
| **发版验证（NexusLink）** | **按本次变更选**（不改日常默认）：仅编辑器资产 / manage-get / schema → headless；含 PIE / UnLua / 视口 / `l4_runtime`/`lua`/`requires_gui` / `interact_runtime_*` → `--gui`；混合或不清 → `--gui` |

覆盖审计使用 Python AST 静态关联每次调用的 `Operations[].Action` 与 `Sections`，支持局部列表、append/extend/insert/`+=`、循环和参数化用例（含 `pytest.param`，忽略 `id` / `marks` 元数据）。追加后的参数表保持行配对，容器别名和循环迭代值正确保留，不同用例的变更相互隔离；无法静态展开的参数行仍扫描不依赖参数的固定调用。未传入调用的字面量不计入覆盖；它只证明源码中存在调用，不证明该分支执行、没有 skip 或断言通过，运行覆盖仍须执行 E2E。审计器自身的回归无需 UE：`py -m unittest discover -s Script/tests -p test_audit_e2e_coverage.py`。

### Marker 选用

| Marker | 何时打 |
|--------|--------|
| （无） | 编辑器资产读写、只读探测、可在 headless 跑通 |
| `l4_runtime` | 依赖 PIE：`spawn_runtime_*`、`control_pie`、`interact_runtime_*` 等 |
| `lua` | 依赖 UnLua + PIE |
| `requires_gui` | 需要完整 RHI / 视口 / Slate（如 `capture_viewport` 实图、`get_asset_texture` 像素） |

**原则**：能写在 headless 里的用例不要强依赖 GUI；确实离不开 PIE/视口再打标，并保证 `--gui` 全量能跑到。

**参数约定（与 NexusLink Breaking 对齐）**：Capability 单目标（`assetPath`/`actorName`/`widgetName`）；跨目标用多次调用或 `call_capability.calls[]`；manage 用 `operations[]`；get 用 `propertyPaths[]`；spawn 用 `assetPath`（非 `blueprintPath`）；duplicate/rename 用 `destAssetPath`（非 `newPath`）。旧键不兼容。

**`exec_command` 勿用 `help *`**：UE 会在系统浏览器打开 `ConsoleHelp.html`（GUI/headless 均可能）。

E2E 连 MCP 须带 Bearer（`NEXUS_MCP_TOKEN`、`{Temp}/NexusLink/{PID}.json`，或本机共享 `%LOCALAPPDATA%/NexusLink/mcp-auth-token`）。自动拉起会加 `-EnableNexusMcp` 与 `-NexusEnableDangerousCaps`（会话级打开 `exec_command` / `exec_python` / Lua eval/dofile）。手动 `--ue-url` 时需已开 MCP，危险 cap 需在设置里打开或带同样 CLI。

## 快速开始

```bash
pip install -r Tests/requirements.txt
```

### 默认：命令行 headless（推荐日常）

```bash
py Script/run_e2e.py
# 等价：自动探测或拉起 UEEditor-Cmd，跳过 l4_runtime / lua / requires_gui
# 自动拉起时跳过启动前已在听的 MCP 端口（本机已有 Editor 占 :45000 时连新实例）
```

### 全量：GUI Editor

```bash
py Script/run_e2e.py --gui
# 或
py Script/run_e2e.py --full
```

### 连现成 Editor

```bash
py Script/run_e2e.py --ue-url http://127.0.0.1:45000/stream
# 连 GUI Editor 且未加 --headless → 跑全量（含 runtime）
# 连 GUI Editor 且 pytest 带 --headless → 仍跳过 runtime 类用例
```

### 直接 pytest

```bash
pytest Tests --ue-root "E:/EpicGames/UE_5.7" --uproject Nexus.uproject          # headless 拉起
pytest Tests --ue-root "E:/EpicGames/UE_5.7" --uproject Nexus.uproject --gui  # GUI 全量
pytest Tests --ue-url http://127.0.0.1:45000/stream
```

## 常用过滤

| 命令 | 用途 |
|------|------|
| `py Script/audit_e2e_coverage.py` | 对照 C++ 注册表，缺 action/section 则失败（不启动 UE） |
| `pytest Tests -m "not l4_runtime"` | 手动跳过 PIE（headless 已自动跳过） |
| `pytest Tests -m "not lua"` | 跳过 UnLua |
| `pytest Tests --headless` | 显式命令行模式（跳过 `l4_runtime` / `lua` / `requires_gui`） |
| `pytest Tests -k blueprint` | 关键字过滤 |
| `pytest Tests --keep-artifacts` | 保留 `/Game/_McpTest/<ts>/` 与历史 `/Game/_NexusTest` |

## 用例文件映射

| 阶段 | 文件 |
|------|------|
| 探测 + 编辑器 | `test_00_smoke.py`、`test_10_editor.py` |
| Struct / DataTable | `test_20_struct_datatable.py` |
| Blueprint | `test_30_blueprint.py` |
| Widget | `test_40_widget.py` |
| Material | `test_50_material.py` |
| 资产引用 | `test_60_asset_refs.py` |
| Gameplay Tags | `test_70_gameplay_tags.py` |
| AI / 动画资产 | `test_80_ai_anim_assets.py` |
| GAS 资产 | `test_85_gas_assets.py` |
| 资产管理 | `test_90_asset_mgmt.py` |
| Mesh / Texture | `test_91_asset_mesh_texture.py` |
| 动画 / 网格只读 | `test_92_anim_mesh_assets.py` |
| Sound / Niagara | `test_93_sound_niagara.py` |
| 关卡 | `test_94_level.py` |
| PIE Runtime + Lua | `test_95_pie_runtime.py` |
| GAS Runtime | `test_96_gas_runtime.py` |
| StateTree | `test_97_statetree_manage.py`（UE 5.5+） |
| Sequencer / Physics / EQS | `test_98_sequencer_physics_eqs.py` |
| 响应压缩 | `test_99_response_compact.py` |
| BlendSpace / AnimSequence 关键帧 | `test_100_blendspace_animkeys.py` |
| MetaSound / PCG / PoseSearch | `test_101_metasound_pcg_posesearch.py` |
| Curve / UserDefinedEnum | `test_102_curve_enum.py` |
| AnimComposite / PhysicalMaterial / RenderTarget | `test_103_anim_phys_rt.py` |
| SoundClass / Submix | `test_104_audio_system.py` |
| MetaSoundPatch | `test_105_metasound_patch.py` |
| DataLayer | `test_106_data_layer.py` |
| ControlRig | `test_107_control_rig.py` |
| StringTable / Font | `test_108_string_table_font.py` |
| FoliageType | `test_109_foliage.py` |
| Paper2D | `test_110_paper2d.py` |
| GeometryCollection | `test_111_geometry_collection.py` |
| FileMediaSource | `test_112_media.py` |
| CommonUI Style | `test_113_common_ui.py` |
| MoviePipeline | `test_114_movie_pipeline.py` |
| Enhanced Input | `test_115_enhanced_input.py` |
| 材质子类型 | `test_116_material_subtypes.py` |
| IKRig / IKRetargeter | `test_117_ik.py` |
| MVVM | `test_118_mvvm.py`（UE 5.5+） |
| PCG Graph | `test_119_pcg.py`（UE 5.4+） |

## Trace L1（UE 4.26+）

过滤前缀为 `NexusLink.Trace.`。Readback 优先使用 `-NexusTraceTestPath` 提供的已关闭录制文件，避免旧版引擎进程内停录时的写线程错误；UE5 未提供文件时仍可自行短录制。先在独立 Editor-Cmd 进程中运行 `NexusLink.Trace.RecordProbe`，启动参数加 `-trace=cpu,frame,bookmark -tracefile=<absolute-path>`，并用 `-TestExit="Automation Test Queue Empty"` 在完成后退出并关闭文件。第二个进程运行 `NexusLink.Trace.`，传 `-NexusTraceTestPath=<absolute-path>`。两次均可用 `-unattended -nullrhi -nosplash -nosound`。

跨版本运行使用隔离测试宿主：低于 UE 5.6 的副本不声明 Target 原本就不编译的 `NexusGameplay` 模板模块，并用 `-ini:EditorPerProjectUserSettings:[/Script/UnrealEd.EditorLoadingSavingSettings]:LoadLevelAtStartup=None` 禁止加载高版本默认关卡；不修改原工程。

UE4 的 Store 用例在独立临时目录启动自动分配端口的 Store，不依赖用户已有的 Insights 会话；检查无路径列表、TraceId 流回读及会话复用。快照流测试覆盖读取上限和提前断流。测试用的 Store 端口仅通过 C++ 内部入口传递，不增加 MCP 参数。
