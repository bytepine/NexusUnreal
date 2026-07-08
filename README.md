# NexusUnreal

**公开** UE 4.26 **示例工程**：演示如何在 ThirdPerson 模板项目中集成 [NexusLink](https://github.com/bytepine/NexusLink) MCP 插件。含 UnLua 脚本、游戏 C++ 模块与 MCP 回归测试宿主。

> 本仓**不包含** NexusLink 插件本体（以 git 子模块挂载）；Fab / 商店用户请单独安装插件，或克隆时 `--recurse-submodules`。
>
> **NexusLink 插件文档与发版**见公开仓 [bytepine/NexusLink](https://github.com/bytepine/NexusLink)。

---

## 克隆

**推荐**（同时拉取 NexusLink 子模块）：

```bash
git clone --recurse-submodules https://github.com/bytepine/NexusUnreal.git
```

已克隆但未拉子模块时：

```bash
git submodule update --init --recursive
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

插件版本：见 `Plugins/Developer/NexusLink/VERSION` 或 [NexusLink Releases](https://github.com/bytepine/NexusLink/releases)

---

## MCP 接入

1. 确保 NexusLink 子模块已初始化，或从 [NexusLink Releases](https://github.com/bytepine/NexusLink/releases) 下载 zip 放入 `Plugins/Developer/NexusLink`
2. 启用：**Editor Preferences → Plugins → NexusLink → 启用 MCP 服务器**（默认关）→ HTTP `:45000` / WS `:55000`
3. IDE 代理：[NexusVSCode](https://github.com/bytepine/NexusVSCode)（`:6900`）或 [NexusRider](https://github.com/bytepine/NexusRider)（`:6800`）
4. 完整配置：[NexusLink 使用指南](https://github.com/bytepine/NexusLink/blob/master/docs/usage-guide.md)

---

## 编译与测试

| 任务 | 命令 |
|------|------|
| 游戏 C++ 编译 | `py Script/build_test_game.py --versions UE_4.26` |
| 跨版本插件编译 | `build_test.bat`（见 NexusLink 文档） |
| L2 MCP 回归（日常，headless） | `py Script/run_e2e.py` |
| L2 MCP 全量（GUI，含 PIE/Lua） | `py Script/run_e2e.py --gui` 或 `--full` |

| 层级 | 说明 |
|------|------|
| L1 C++ | `Plugins/Developer/NexusLink/Source/NexusLinkTests/` |
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

示例关卡与 Mannequin 等 `.uasset` 基于 UE 模板内容，使用须遵守 [Unreal Engine EULA](https://www.unrealengine.com/eula)。NexusLink 插件许可见 [Plugins/Developer/NexusLink/LICENSE](Plugins/Developer/NexusLink/LICENSE)（MIT）。
