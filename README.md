# NexusUnreal — 私有 UE 游戏工程

内部 ThirdPerson 示例工程，用于玩法开发与 NexusLink MCP 回归测试。

> **NexusLink 插件文档**不在本仓维护，见公开仓 [bytepine/NexusLink](https://github.com/bytepine/NexusLink)。

---

## 模块与路径

| 用途 | 路径 |
|------|------|
| 默认关卡 | `/Game/ThirdPersonBP/Maps/ThirdPersonExampleMap` |
| 蓝图 / GameMode | `/Game/ThirdPersonBP/` |
| UnLua 脚本 | `Content/Script/` |
| 游戏 C++ | `Source/Nexus/` |
| **NexusLink 插件**（子模块） | `Plugins/Developer/NexusLink/` |

插件版本：`Plugins/Developer/NexusLink/VERSION`（当前 [v1.13.1](https://github.com/bytepine/NexusLink/releases/tag/nexus-link-v1.13.1)）

---

## MCP 接入

1. 启用 NexusLink：**Editor Preferences → Plugins → NexusLink → 启用 MCP 服务器**（默认关）
2. Cursor：经 `nexus-vscode` 代理（`:6900`）或直连 UE（`:45000`）
3. 完整安装与配置：[NexusLink 使用指南](https://github.com/bytepine/NexusLink/blob/master/docs/usage-guide.md)

---

## 测试

| 层级 | 说明 |
|------|------|
| L1 C++ | `Plugins/Developer/NexusLink/Source/NexusLinkTests/` |
| L2 pytest | 本仓 `Tests/` — 见 [Tests/README.md](Tests/README.md) |

```bash
pip install -r Tests/requirements.txt
python Script/run_e2e.py --ue-url http://127.0.0.1:45000/stream
```

---

## License

游戏内容与私有资产仅内部使用。NexusLink 插件为 [MIT](Plugins/Developer/NexusLink/LICENSE)。
