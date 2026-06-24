# NexusUnreal — pytest E2E 测试

本目录为 **NexusUnreal 私有工程**内的 NexusLink L2 回归测试实现。

通用说明（工具模型、过滤）见 [NexusLink docs/testing.md](https://github.com/bytepine/NexusLink/blob/master/docs/testing.md)。

## 测试策略（必遵）

| 场景 | 做法 |
|------|------|
| **新功能 / 新 Capability** | 在对应 `test_*.py` 至少补 **1 条 happy-path**；写入走 `test_ns`（`/Game/_McpTest/<ts>/`） |
| **日常 / CI / 开发自测** | **默认命令行 headless**：`py Script/run_e2e.py`（`UEEditor-Cmd -nullrhi`，快、无窗口） |
| **命令行无法覆盖** | 用例打标 `l4_runtime` / `lua` / `requires_gui`；headless 自动 skip，须在 **GUI** 下验证 |
| **全量回归** | **必须 GUI**：`py Script/run_e2e.py --gui` 或 `--full`（含 PIE、UnLua、视口/RHI 等） |

### Marker 选用

| Marker | 何时打 |
|--------|--------|
| （无） | 编辑器资产读写、只读探测、可在 headless 跑通 |
| `l4_runtime` | 依赖 PIE：`spawn_runtime_*`、`control_pie`、`interact_runtime_*` 等 |
| `lua` | 依赖 UnLua + PIE |
| `requires_gui` | 需要完整 RHI / 视口 / Slate（如 `capture_viewport` 实图、`get_asset_texture` 像素） |

**原则**：能写在 headless 里的用例不要强依赖 GUI；确实离不开 PIE/视口再打标，并保证 `--gui` 全量能跑到。

**`exec_command` 勿用 `help *`**：UE 会在系统浏览器打开 `ConsoleHelp.html`（GUI/headless 均可能）。

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
| 响应压缩 | `test_99_response_compact.py` |
