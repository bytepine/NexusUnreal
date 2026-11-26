# Copyright byteyang. All Rights Reserved.
"""NexusUnreal 工程描述符的引擎兼容性过滤。"""

import json
from pathlib import Path


def filter_project_descriptor(descriptor, engine_path: Path):
    """返回为兼容示例游戏代码而禁用的引擎插件和移除的工程模块。"""
    engine = engine_path / "Engine"
    version = json.loads((engine / "Build" / "Build.version").read_text(encoding="utf-8-sig"))
    engine_version = (version["MajorVersion"], version["MinorVersion"])
    removed_modules = []
    # 两个 Target.cs 只在 UE 5.6 起编译此模块，Cook 按描述符加载模块。
    if engine_version < (5, 6):
        modules = descriptor.get("Modules", [])
        supported_modules = [module for module in modules if module["Name"] != "NexusGameplay"]
        if len(supported_modules) != len(modules):
            descriptor["Modules"] = supported_modules
            removed_modules.append("NexusGameplay")

    disabled_plugins = []
    if engine_version < (5, 0):
        # UE4 实验版 EnhancedInput 与 NexusInputStubs 声明了同名 UHT 类型。
        for plugin in descriptor.get("Plugins", []):
            if plugin["Name"] == "EnhancedInput" and plugin["Enabled"]:
                plugin["Enabled"] = False
                disabled_plugins.append(plugin["Name"])
    return disabled_plugins, removed_modules
