# NexusUnreal — pytest E2E 测试

行为树验收：编译后运行 `python Script/bt_retest_acceptance.py --ue-root <UE-directory> --output <new-output-directory>`。独立 GameModeBase 服务器显式生成测试 Pawn/AIController 和继承 Blackboard，验证失败/恢复、末次快照、清理、基线、停止树及销毁目标。配套 UE Automation 前缀为 `NexusLink.AI.Blackboard`，不改项目默认 GameMode。

性能对比验收：先运行 UE Automation `NexusLink.Trace.GetTrace` 与 `NexusLink.Trace.Statistics`，再运行 `python Script/trace_compare_acceptance.py --ue-root <UE-directory> --output <new-output-directory>`。脚本启动隔离 Editor，通过显式端点读取 Automation 生成并已停录的 Trace，验证导出和离线零差值报告，结束后关闭本次进程。

`test_00_smoke.py::test_proxy_discovery_status` 检查真实 HTTP `/status` 的既有发现协议字段（含 `server`、`wsPort`、`authRequired`），避免 Capability 命名迁移破坏 Desktop / Rider / VSCode 的实例扫描。

## 动画、Niagara 与 Toolset 回归

`test_19_remaining_toolsets.py` 覆盖 Sequencer 分段及 float/bool 关键帧、Control Rig 四帧烘焙与控件键读回、Niagara 系统/渲染器/用户变量及嵌套动态输入写入、Game Features 生命周期和自定义 Toolset 注册/注销。Registry 过滤与禁用还通过 `NexusLink.Toolsets.DiscoveryFilters` Automation 验证。

动画、Niagara 深层接口与自定义 Toolset 发现需 UE 5.8，并在宿主启用相应官方插件；Game Features 需 UE 5.7+ 的 `GameFeatures`。用例可在 headless 执行，Control Rig 场景另需示例 Mannequin 网格与 Body Rig 内容。

生命周期用例仅使用环境变量 `NEXUS_GAME_FEATURE_FIXTURE` 明确指定的专用空 Feature 插件：须已被编辑器发现、允许内容且位于引擎认可的 Game Features 目录。缺少该配置时跳过；配置后验证缺少 GameFeatureData 的失败、创建测试 DataAsset、激活到 `Active`、停用到 `Loaded`。只在隔离测试宿主配置此变量，不指向业务 Feature 插件。

## 完整工程启动验收

修改公共 C++ 结构或基类布局后，关闭编辑器并完整重编所有引用模块，包括 NexusLink、编辑器模块、扩展及测试插件；Live Coding 不能替代这一步。不要把旧 `Intermediate` 的目标文件与新源码重新链接。`Script/build_test.py` 默认在干净目录构建完整示例工程；自行保留隔离目录作增量测试时，也必须确保依赖重编。

如果编辑器在 MCP 就绪前报告 DLL `GetLastError=1114`，应定位加载阶段的首个异常；卸载后的类注册回调崩溃可能是连带结果。编译通过不代表启动通过：完整工程验收还须以对应引擎启动 GUI，再运行 `test_00_smoke.py`、`test_15_editor_operations.py` 和本次涉及的运行测试。跨版本验收使用独立的内容及配置副本，避免测试写入原工程。 `test_02_asset_edit_preview.py` 的磁盘校验遵循 `--uproject`，读取当前被测工程的资产文件。 PIE 夹具按测试模块启动与停止，避免 Automation 等编辑器操作结束 PIE 后，后续模块沿用已失效的会话。 Runtime 压缩用例显式请求 PIE；Slate 截图使用窗口查询返回的 `Ref`，不依赖此前 PIE 窗口的焦点。

MVVM 删除负例使用完整可编译的绑定，验证删除失败后保留原绑定，避免空绑定触发编译弹窗并阻塞后续 PIE。Slate 截图回归按日志序号检查截图期间不产生 ensure。

## GAS 诊断与联机复测

通用工程接入验收：编译后运行 `python Script/gas_generic_retest.py --ue-root <UE-directory>`。启动隔离的 `GameModeBase` 服务器，显式生成三个独立测试目标（普通 Actor、Pawn、PlayerState ASC），验证 GenericActivation 的预检、真实失败标签、恢复条件、再次执行及基线比较。输出在 `Saved/GenericGasRetest`，输出目录已有基线时拒绝覆盖，请用 `--output` 指定新目录。该场景不使用 `NexusDiagnosticGameMode`；未修改默认游戏配置。

`test_120_gas_diagnostics.py` 在 PIE 验证诊断只读、已有技能激活、事件捕获与停止；标记 `l4_runtime`，用 `py Script/run_e2e.py --gui -k gas_diagnostics` 执行。测试依赖示例工程原生诊断类和 `Config/DefaultGameplayTags.ini`，不以 skip 代替功能通过。

先编译 UE 5.7 的 NexusEditor，再运行：

```sh
py Script/gas_network_retest.py --ue-root <UE_5.7-directory> --repeat 10
```

首次体验可加 `--quickstart`（固定一轮 `PredictionRejected` → `Success`）。脚本先只读检查角色绑定及必需技能，再复现拒绝并恢复条件，打开输出目录的 `index.html` 比较两次报告。每个场景包含 `case.json`、`report.html`、`results.json` 与 `junit.xml`；预检报告在 `startup/`。不加此参数时保留原八场景回归。

工具启动隐藏的独立 `-server` / `-game` / `-game` 进程，使用 Engine Entry 地图和显式 `NexusDiagnosticGameMode`，不改默认 GameMode；可用 `--uproject` 指向其他已编译的示例工程副本。结束时只关闭本次创建的进程。日志、生成的用例、证据和 JUnit 默认保存在 `Saved/GasRetest/`。

覆盖：未授予、缺少必需标签、阻止标签、冷却、消耗不足、预测客户端激活但服务器拒绝，以及恢复条件后的 LocalPredicted / ServerOnly 成功。观察客户端检查复制的提交计数，不要求它能看到其他玩家的技能列表。能力文档与 JSON 用例格式见 [GAS replay](../Plugins/NexusLink/docs/gas-retest.md)。

### 固定用例自动回归与归档

已编译诊断工程后运行：

```sh
py Script/gas_regression.py --ue-root <UE_5.7-directory>
```

固定运行 `PredictionRejected`、`Success`，复用同一套一服两客户端隔离流程。全部基线在启动 UE 前校验：必须是通过的完整复测，包含匹配当前用例的签名。`Tests/GasRetest/baselines/` 保存已验证结果；缺失、旧签名或用例变化会失败，不会拿本次运行自动生成/覆盖基线。

每次生成新的 `Saved/GasRegression/<UTC-time>/`，也可用 `--output <new-directory>` 指定；已有目录会被拒绝，避免旧结果混入。支持 `--baselines <directory>` 和 `--uproject <built-project>`。输出包含：

- `index.html` / `report.html`：固定用例状态与逐项对比入口。
- `results.json` / `junit.xml`：汇总结果与每个固定用例的门禁状态；断言或缺失检查为失败，运行错误和未执行用例为错误，不以 skip 代替执行。
- `current/`：启动预检、每个已执行用例的 HTML / JSON / JUnit、生成的用例和各端日志。
- `comparisons/`：基线与本次的对比，保留前后完整证据；事件变化单独展示，不自动当成回归。
- `run.log` / `reports.zip`：执行日志及全部报告归档，成功、断言失败、基线/配置/运行错误均尝试归档。

退出码 `0`：所有固定用例及基线检查通过；`1`：断言或基线检查失败；`2`：基线/配置/运行错误、未执行用例或归档失败。联机脚本遇到失败会清理进程并停止后续场景；自动回归会明确标记余下用例未执行。写操作不重试。

基线更新须人工审查：先用插件工具的 `--save-baseline` 保存到一个新文件，检查断言、权威端事件和用例签名，再替换对应受版本控制的文件，与用例变更一起提交。汇总报告不能替代单个场景基线。无需 UE 的门禁/归档回归：`py -m unittest discover -s Script/tests -p 'test_gas*.py'`。

[GAS Tools Checks 工作流](../.github/workflows/gas-regression.yml) 仅在 GitHub 提供的 Ubuntu 机器上执行无需 UE 的工具检查。UE 编译和联机复测由用户手动启动，不通过 GitHub 调度本机，也不安装后台 Runner。

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
| MVVM | `test_118_mvvm.py`（UE 5.5+）：上下文/嵌套路径、五种方向、单输入转换、编译保存读回与无效配置不新增绑定 |
| PCG Graph | `test_119_pcg.py`（UE 5.4+） |

## Trace L1（UE 4.26+）

过滤前缀为 `NexusLink.Trace.`。Readback 优先使用 `-NexusTraceTestPath` 提供的已关闭录制文件，避免旧版引擎进程内停录时的写线程错误；UE5 未提供文件时仍可自行短录制。先在独立 Editor-Cmd 进程中运行 `NexusLink.Trace.RecordProbe`，启动参数加 `-trace=cpu,frame,bookmark -tracefile=<absolute-path>`，并用 `-TestExit="Automation Test Queue Empty"` 在完成后退出并关闭文件。第二个进程运行 `NexusLink.Trace.`，传 `-NexusTraceTestPath=<absolute-path>`。两次均可用 `-unattended -nullrhi -nosplash -nosound`。

跨版本运行使用隔离测试宿主：低于 UE 5.6 的副本不声明 Target 原本就不编译的 `NexusGameplay` 模板模块，并用 `-ini:EditorPerProjectUserSettings:[/Script/UnrealEd.EditorLoadingSavingSettings]:LoadLevelAtStartup=None` 禁止加载高版本默认关卡；不修改原工程。

UE4 的 Store 用例在独立临时目录启动自动分配端口的 Store，不依赖用户已有的 Insights 会话；检查无路径列表、TraceId 流回读及会话复用。快照流测试覆盖读取上限和提前断流。测试用的 Store 端口仅通过 C++ 内部入口传递，不增加 MCP 参数。

### 编辑器长操作回归

`test_15_editor_operations.py` 覆盖错误操作 ID、Slate 只读与截图（GUI）、本地 Automation 发现及完整名称运行。所有状态经 `GetEditorOperation` 查询，不从代理缓存读取。

C++ `NexusLink.EditorOperations` 覆盖操作归属、最终压缩输出 Schema、批次预检和 GUI 中文输入、点击、按键、禁用/隐藏/失效 Ref。GUI 探针需要会话明确启用危险能力。隔离工程加 `-NexusEditorOperationFailureProbe` 后，`NexusLink.EditorOperations.Probe.Outcome` 会故意失败，用于检查适配层逐项失败结果；普通测试不启用该参数。`Probe.Latent` 用于进度、有限等待和停止边界验证。

自动启动等待就绪时按本次编辑器 PID 的实例注册文件绑定端口；多个编辑器同时启动不会因先监听的端口而连接到另一个工程。

## UE 5.8 领域与图片回归

`test_16_project_discovery.py` 覆盖设置注册树、明确属性读取、插件依赖与挂载归属。`test_17_native_toolsets.py` 在启用对应官方 Toolset 的 UE 5.8 宿主验证 AgentSkill 列表/详情、带类型的语义查询、PCG 创建实例→执行→节点采样和 Niagara 诊断；语义索引/提供器未就绪时保留明确跳过原因。

`test_40_widget.py` 的 5.8 用例验证移动/重排、包裹/单子项还原/模板替换、循环拒绝及继承命名槽的编译、填充、占用拒绝和移除。`NexusLink.EditorOperations.SlateInput` 通过临时窗口验证替换、可见等待、表单预检、复选框/组合框、同名误点防护、拖拽和失效 Ref，使用 GUI 执行。

`test_18_mcp_images.py` 验证真实 PNG/JPEG 字节、仅路径模式、异步及批量图片；`NexusLink.Protocol.ImageContent` 验证可信附件、数量/字节上限、去重和保留文本元数据。GUI 截图使用 Windows 查询返回的有效 Ref；断言先合并通用压缩输出的 `_defaults` 再检查字段。

`test_19_native_followups.py` 覆盖 PCG 参数/子图/实例覆盖及读回、PhysicsAsset 创建和精细编辑、Tag INI 生命周期，以及 DataRegistry 真实表行/缓存缺失。Tag 写入回归必须使用独立 Config 副本，避免引擎重命名 Redirect 写回用户配置；DataRegistry 使用临时内存夹具并只注销本用例对象。
