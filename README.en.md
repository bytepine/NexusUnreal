# NexusUnreal

[中文](README.md) | English

See the [test guide](Tests/README.en.md#gas-diagnostics-and-network-retests) for the GAS network diagnostics example, the one-server/two-client `--quickstart` workflow, manually launched fixed-scenario baseline retests, and HTML / JSON / JUnit archives. The default game mode remains unchanged.

A **public UE 5.7 sample project** demonstrating the [NexusLink](https://github.com/bytepine/NexusLink) MCP plugin in a ThirdPerson template project. It includes UnLua scripts, game C++ modules, and the MCP regression tests.

> NexusLink, UnLua, and NexusLinkExt are mounted as Git submodules; their plugin sources are not included directly in this repository. Fab / marketplace users should install NexusLink separately, or clone with `--recurse-submodules`.
>
> See the public [bytepine/NexusLink](https://github.com/bytepine/NexusLink) repository for **NexusLink documentation and releases**.

## Clone

**Recommended**, including the NexusLink, UnLua, and NexusLinkExt submodules:

```bash
git clone --recurse-submodules https://github.com/bytepine/NexusUnreal.git
```

If the repository is already cloned without its submodules:

```bash
git submodule update --init --recursive
```

Engine association: `Nexus.uproject` → `EngineAssociation: 5.7`.

## Modules and paths

| Purpose | Path |
|---------|------|
| Default level | `/Game/ThirdPerson/Lvl_ThirdPerson` |
| Blueprints / GameMode | `/Game/ThirdPerson/` |
| Character animations | `/Game/Characters/Mannequins/` |
| UnLua scripts | `Content/Script/` |
| **UnLua plugin** (submodule) | `Plugins/UnLua/` |
| **UnLuaTestSuite** | `Plugins/UnLuaTestSuite/` |
| Game C++ | `Source/Nexus/` |
| Template variant C++ | `Source/NexusGameplay/` (Combat / Platforming / SideScrolling, UE 5.6+) |
| UE 4 input compatibility layer | `Source/NexusInputStubs/` (4.x targets only) |
| **NexusLink plugin** (submodule) | `Plugins/NexusLink/` |
| **NexusLinkExt** (submodule) | `Plugins/NexusLinkExt/` |
| **NexusLinkTestSuite** | `Plugins/NexusLinkTestSuite/` |
| **NexusLinkExtTestSuite** | `Plugins/NexusLinkExtTestSuite/` |

Plugin version: `Plugins/NexusLink/VERSION` or [NexusLink Releases](https://github.com/bytepine/NexusLink/releases).

## MCP access

1. Initialize the NexusLink submodule, or download its ZIP from [NexusLink Releases](https://github.com/bytepine/NexusLink/releases) into `Plugins/NexusLink`.
2. Enable **Editor Preferences → Plugins → NexusLink → Enable MCP Server** (off by default), exposing HTTP `:45000` / WS `:55000`. In PIE / standalone Development packages, open the console with `~` and run `NexusLink.Mcp on`; `NexusLink.Mcp panel` opens the in-game debug panel. These switches apply to the current session and do not write configuration files.
3. IDE proxies: [NexusVSCode](https://github.com/bytepine/NexusVSCode) (`:6900`) or [NexusRider](https://github.com/bytepine/NexusRider) (`:6800`).
4. Full configuration: [NexusLink usage guide](https://github.com/bytepine/NexusLink/blob/master/docs/usage-guide.md).

## Build and test

| Task | Command |
|------|---------|
| Cross-version project builds | `py Script/build_test.py` (builds `Nexus.uproject` with locally installed engines in isolated temporary directories without modifying the project; one engine at a time, no `-MaxParallelActions`, leaving concurrency to UBT; automatically retries C3859/C1076 with a single action; supports `--editor-only` / `--game-only`) |
| Game targets only | `py Script/build_test_game.py --versions UE_5.7` |
| Package for any platform | `py Script/package.py` (defaults to the host platform + Development; `--platform Win64 Linux`; `--config Shipping`; arguments after `--` pass through to UAT) |
| L2 MCP regression, daily/headless | `py Script/run_e2e.py` |
| Full L2 MCP regression, GUI including PIE/Lua | `py Script/run_e2e.py --gui` or `--full` |

| Layer | Description |
|-------|-------------|
| L1 C++ | `Plugins/NexusLinkTestSuite/` (`NexusLink.`); UnLua tests: `Plugins/NexusLinkExtTestSuite/` (`NexusLinkExt.`) |
| L2 pytest | This repository's `Tests/`; see [Tests/README.en.md](Tests/README.en.md) for policy |

## Documentation

All maintained documentation must provide complete Chinese and English versions, in separate Chinese and English files with reciprocal links at the top. Update both languages together, including README files, contribution and test guides, checklists, and changelogs; generated documents must be updated through their source or generator. Keep commands, paths, API names, and version numbers consistent between languages.

## Related repositories

| Repository | Visibility | Relationship |
|------------|------------|--------------|
| [NexusLink](https://github.com/bytepine/NexusLink) | Public | UE MCP plugin, mounted as a submodule |
| [NexusLinkExt](https://github.com/bytepine/NexusLinkExt) | Public | Optional-plugin capabilities, currently UnLua; mounted as a submodule |
| [NexusRider](https://github.com/bytepine/NexusRider) | Public | Rider MCP proxy |
| [NexusVSCode](https://github.com/bytepine/NexusVSCode) | Public | VSCode / Cursor MCP extension |

## License

Source and documentation: [MIT](LICENSE) © byteyang.

Sample levels, Mannequin assets, and other `.uasset` files are based on UE template content and remain subject to the [Unreal Engine EULA](https://www.unrealengine.com/eula). The NexusLink plugin uses [MIT](Plugins/NexusLink/LICENSE), as does [NexusLinkExt](Plugins/NexusLinkExt/LICENSE).
