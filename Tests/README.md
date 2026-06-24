# NexusUnreal — pytest E2E 测试

本目录为 **NexusUnreal 私有工程**内的 NexusLink L2 回归测试实现。

通用说明（工具模型、过滤、约束）见 [NexusLink docs/testing.md](https://github.com/bytepine/NexusLink/blob/master/docs/testing.md)。

## 快速开始

```bash
pip install -r Tests/requirements.txt
```

### 模式 A：连现成的 UE Editor

```bash
pytest Tests --ue-url http://127.0.0.1:45000/stream
```

### 模式 B：Runner 拉 UEEditor-Cmd

```bash
pytest Tests \
    --ue-root "C:/Program Files/Epic Games/UE_5.4" \
    --uproject "Nexus.uproject"
```

或：

```bash
python Script/run_e2e.py --ue-url http://127.0.0.1:45000/stream
```

## 常用过滤

| 命令 | 用途 |
|------|------|
| `pytest Tests -m "not l4_runtime"` | 跳过 PIE 用例 |
| `pytest Tests -m "not lua"` | 跳过 UnLua |
| `pytest Tests -k blueprint` | 仅蓝图 |
| `pytest Tests --keep-artifacts` | 保留 `/Game/_McpTest/<ts>/` |

覆盖映射与新增 Capability 约定见 [docs/testing.md](https://github.com/bytepine/NexusLink/blob/master/docs/testing.md)。
