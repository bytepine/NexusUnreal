# NexusUnreal

**私有** UE 4.26 游戏工程：ThirdPerson 示例玩法、UnLua 脚本、游戏 C++ 模块，以及 NexusLink MCP 插件挂载与回归测试宿主。

> **NexusLink 插件文档与发版**不在本仓维护，见公开仓 [bytepine/NexusLink](https://github.com/bytepine/NexusLink)。

---

## 克隆

本仓通常作为 [NexusWork](https://github.com/bytepine/NexusWork) 的 `nexus-unreal` 子模块使用：

```bash
# 在 NexusWork 根目录
git submodule update --init nexus-unreal
git submodule update --init Plugins/Developer/NexusLink   # 在 nexus-unreal 目录内
```

单独克隆（须同时拉 NexusLink 子模块）：

```bash
git clone --recurse-submodules https://github.com/bytepine/NexusUnreal.git
```

引擎：`Nexus.uproject` → `EngineAssociation: 4.26`

---

## 模块与路径

| 用途 | 路径 |
|------|------|
| 默认关卡 | `/Game/ThirdPersonBP/Maps/ThirdPersonExampleMap` |
| 蓝图 / GameMode | `/Game/ThirdPersonBP/` |
| 角色动画 | `/Game/Mannequin/` |
| UnLua 脚本 | `Content/Script/` |
| 游戏 C++ | `Source/Nexus/` |
| **NexusLink 插件**（子模块） | `Plugins/Developer/NexusLink/` |

插件版本：`Plugins/Developer/NexusLink/VERSION`（当前 [v1.13.1](https://github.com/bytepine/NexusLink/releases/tag/nexus-link-v1.13.1)）

---

## MCP 接入

1. 安装 NexusLink：从 [NexusLink Releases](https://github.com/bytepine/NexusLink/releases) 下载 zip，或确保子模块 `Plugins/Developer/NexusLink` 已初始化
2. 启用：**Editor Preferences → Plugins → NexusLink → 启用 MCP 服务器**（默认关）→ HTTP `:45000` / WS `:55000`
3. IDE 代理：[NexusVSCode](https://github.com/bytepine/NexusVSCode)（`:6900`）或 [NexusRider](https://github.com/bytepine/NexusRider)（`:6800`）
4. 完整配置：[NexusLink 使用指南](https://github.com/bytepine/NexusLink/blob/master/docs/usage-guide.md)

---

## 编译与测试

| 任务 | 命令 |
|------|------|
| 游戏 C++ 编译 | `py Script/build_test_game.py --versions UE_4.26` |
| 跨版本插件编译 | `build_test.bat`（见 NexusLink 文档） |
| L2 MCP 回归 | `pip install -r Tests/requirements.txt` → `py Script/run_e2e.py` |

| 层级 | 说明 |
|------|------|
| L1 C++ | `Plugins/Developer/NexusLink/Source/NexusLinkTests/` |
| L2 pytest | 本仓 `Tests/` — 见 [Tests/README.md](Tests/README.md) |

---

## 相关仓库

| 仓库 | 可见性 | 关系 |
|------|--------|------|
| [NexusWork](https://github.com/bytepine/NexusWork) | 私有 | 工作区根目录，聚合本仓与 IDE 子模块 |
| [NexusLink](https://github.com/bytepine/NexusLink) | 公开 | UE MCP 插件（本仓子模块） |
| [NexusRider](https://github.com/bytepine/NexusRider) | 公开 | Rider MCP 代理 |
| [NexusVSCode](https://github.com/bytepine/NexusVSCode) | 公开 | VSCode / Cursor MCP 扩展 |

---

## License

本仓源码与文档：[MIT](LICENSE) © byteyang

游戏内容、`.uasset` 等私有资产仅内部使用。NexusLink 插件许可见 [Plugins/Developer/NexusLink/LICENSE](Plugins/Developer/NexusLink/LICENSE)（MIT）。
