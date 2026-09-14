# NexusUnreal

**公开** UE 5.7 **示例工程**：演示如何在 ThirdPerson 模板项目中集成 [NexusLink](https://github.com/bytepine/NexusLink) MCP 插件。含 UnLua 脚本、游戏 C++ 模块与 MCP 回归测试宿主。

> 本仓**不包含** NexusLink、UnLua 插件本体（以 git 子模块挂载）；Fab / 商店用户请单独安装 NexusLink，或克隆时 `--recurse-submodules`。
>
> **NexusLink 插件文档与发版**见公开仓 [bytepine/NexusLink](https://github.com/bytepine/NexusLink)。

---

## 克隆

**推荐**（同时拉取 NexusLink、UnLua 子模块）：

```bash
git clone --recurse-submodules https://github.com/bytepine/NexusUnreal.git
```

已克隆但未拉子模块时：

```bash
git submodule update --init --recursive
```

引擎：`Nexus.uproject` → `EngineAssociation: 5.7`

---

## 模块与路径

| 用途 | 路径 |
|------|------|
| 默认关卡 | `/Game/ThirdPerson/Lvl_ThirdPerson` |
| 蓝图 / GameMode | `/Game/ThirdPerson/` |
| 角色动画 | `/Game/Characters/Mannequins/` |
| UnLua 脚本 | `Content/Script/` |
| **UnLua 插件**（子模块） | `Plugins/UnLua/` |
| **UnLuaTestSuite** | `Plugins/UnLuaTestSuite/` |
| 游戏 C++ | `Source/Nexus/` |
| **NexusLink 插件**（子模块） | `Plugins/NexusLink/` |
| **NexusLinkTestSuite** | `Plugins/NexusLinkTestSuite/` |

插件版本：见 `Plugins/NexusLink/VERSION` 或 [NexusLink Releases](https://github.com/bytepine/NexusLink/releases)

---

## MCP 接入

1. 确保 NexusLink 子模块已初始化，或从 [NexusLink Releases](https://github.com/bytepine/NexusLink/releases) 下载 zip 放入 `Plugins/NexusLink`
2. 启用：**Editor Preferences → Plugins → NexusLink → 启用 MCP 服务器**（默认关）→ HTTP `:45000` / WS `:55000`
3. IDE 代理：[NexusVSCode](https://github.com/bytepine/NexusVSCode)（`:6900`）或 [NexusRider](https://github.com/bytepine/NexusRider)（`:6800`）
4. 完整配置：[NexusLink 使用指南](https://github.com/bytepine/NexusLink/blob/master/docs/usage-guide.md)

---

## 编译与测试

| 任务 | 命令 |
|------|------|
| 跨版本工程编译 | `py Script/build_test.py`（本机已装引擎编 `Nexus.uproject`；临时目录隔离、不改工程；`--max-workers` 并行；`--editor-only` / `--game-only`） |
| 仅 Game 目标 | `py Script/build_test_game.py --versions UE_5.7` |
| L2 MCP 回归（日常，headless） | `py Script/run_e2e.py` |
| L2 MCP 全量（GUI，含 PIE/Lua） | `py Script/run_e2e.py --gui` 或 `--full` |

| 层级 | 说明 |
|------|------|
| L1 C++ | `Plugins/NexusLinkTestSuite/` |
| L2 pytest | 本仓 `Tests/` — 策略见 [Tests/README.md](Tests/README.md) |

---

## 相关仓库

| 仓库 | 可见性 | 关系 |
|------|--------|------|
| [NexusLink](https://github.com/bytepine/NexusLink) | 公开 | UE MCP 插件（本仓子模块） |
| [NexusRider](https://github.com/bytepine/NexusRider) | 公开 | Rider MCP 代理 |
| [NexusVSCode](https://github.com/bytepine/NexusVSCode) | 公开 | VSCode / Cursor MCP 扩展 |

---

## License

本仓源码与文档：[MIT](LICENSE) © byteyang

示例关卡与 Mannequin 等 `.uasset` 基于 UE 模板内容，使用须遵守 [Unreal Engine EULA](https://www.unrealengine.com/eula)。NexusLink 插件许可见 [Plugins/NexusLink/LICENSE](Plugins/NexusLink/LICENSE)（MIT）。
