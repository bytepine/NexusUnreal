# NexusUnreal — pytest E2E 测试

本目录为 **NexusUnreal 示例工程**内的 NexusLink L2 回归测试实现。

通用说明（工具模型、过滤）见 [NexusLink docs/testing.md](https://github.com/bytepine/NexusLink/blob/master/docs/testing.md)。

## 测试策略（必遵）

| 场景 | 做法 |
|------|------|
| **新功能 / 新 Capability** | 在对应 `test_*.py` 覆盖该 cap 的 **每个 manage `operations[].action`** 与 MultiSection get 的 **每个 named section**；写入走 `test_ns`（`/Game/_McpTest/<ts>/`） |
| **覆盖门禁** | `py Script/audit_e2e_coverage.py`（对照 C++ `RegisterActions` / `GetSectionNames`，缺项 exit 1，不启动 UE） |
| **日常 / CI / 开发自测** | **默认命令行 headless**：`py Script/run_e2e.py`（`UEEditor-Cmd -nullrhi`，快、无窗口） |
| **命令行无法覆盖** | 用例打标 `l4_runtime` / `lua` / `requires_gui`；headless 自动 skip，须在 **GUI** 下验证 |
| **全量回归 / 全覆盖验证** | **必须 GUI**：`py Script/run_e2e.py --gui` 或 `--full`（含 PIE、UnLua、视口/RHI 等） |
| **发版验证（NexusLink）** | **按本次变更选**（不改日常默认）：仅编辑器资产 / manage-get / schema → headless；含 PIE / UnLua / 视口 / `l4_runtime`/`lua`/`requires_gui` / `interact_runtime_*` → `--gui`；混合或不清 → `--gui` |

### Marker 选用

| Marker | 何时打 |
|--------|--------|
| （无） | 编辑器资产读写、只读探测、可在 headless 跑通 |
| `l4_runtime` | 依赖 PIE：`spawn_runtime_*`、`control_pie`、`interact_runtime_*` 等 |
| `lua` | 依赖 UnLua + PIE |
| `requires_gui` | 需要完整 RHI / 视口 / Slate（如 `capture_viewport` 实图、`get_asset_texture` 像素） |

**原则**：能写在 headless 里的用例不要强依赖 GUI；确实离不开 PIE/视口再打标，并保证 `--gui` 全量能跑到。

**参数契约（与 NexusLink Breaking 对齐）**：Capability 单目标（`assetPath`/`actorName`/`widgetName`）；跨目标用多次调用或 `call_capability.calls[]`；manage 用 `operations[]`；get 用 `propertyPaths[]`；spawn 用 `assetPath`（非 `blueprintPath`）；duplicate/rename 用 `destAssetPath`（非 `newPath`）。旧键不兼容。

**`exec_command` 勿用 `help *`**：UE 会在系统浏览器打开 `ConsoleHelp.html`（GUI/headless 均可能）。

E2E 连 MCP 须带 Bearer（`NEXUS_MCP_TOKEN`、`{Temp}/NexusLink/{PID}.json`，或本机共享 `%LOCALAPPDATA%/NexusLink/mcp-auth-token`）。自动拉起会加 `-EnableNexusMcp` 与 `-NexusEnableDangerousCaps`（会话级打开 `exec_command` / Lua eval/dofile）。手动 `--ue-url` 时需已开 MCP，危险 cap 需在设置里打开或带同样 CLI。

## 快速开始

```bash
pip install -r Tests/requirements.txt
```

### 默认：命令行 headless（推荐日常）

```bash
py Script/run_e2e.py
# 等价：自动探测或拉起 UEEditor-Cmd，跳过 l4_runtime / lua / requires_gui
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
pytest Tests --ue-root "E:/EpicGames/UE_4.26" --uproject Nexus.uproject          # headless 拉起
pytest Tests --ue-root "E:/EpicGames/UE_4.26" --uproject Nexus.uproject --gui  # GUI 全量
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
| `pytest Tests --keep-artifacts` | 保留 `/Game/_McpTest/<ts>/` |

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
| StateTree | `test_97_statetree_manage.py`（UE 5.5+，4.26 skip） |
| Sequencer / Physics / EQS | `test_98_sequencer_physics_eqs.py` |
| 响应压缩 | `test_99_response_compact.py` |
| StringTable / Font | `test_108_string_table_font.py` |
| FoliageType | `test_109_foliage.py` |
| Paper2D | `test_110_paper2d.py` |
| GeometryCollection | `test_111_geometry_collection.py` |
| FileMediaSource | `test_112_media.py` |
| CommonUI Style | `test_113_common_ui.py` |
| MoviePipeline | `test_114_movie_pipeline.py` |
