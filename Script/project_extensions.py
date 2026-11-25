# Copyright byteyang. All Rights Reserved.
"""NexusUnreal 工程描述符的引擎兼容性过滤。"""

import json
from pathlib import Path


EXTENSIONS_DIRECTORY = "Plugins/NexusLink/OptionalPlugins"

# 与 NexusLink.Build.cs 的 API 版本要求一致。UE4 的实验版 EnhancedInput
# 与示例工程的 NexusInputStubs 定义了同名 UHT 类型，必须按版本过滤。
_MINIMUM_ENGINE_VERSIONS = {
    "NexusLinkCommonUI": (5, 0),
    "NexusLinkControlRig": (5, 0),
    "NexusLinkDataRegistry": (5, 0),
    "NexusLinkEnhancedInput": (5, 0),
    "NexusLinkGameFeatures": (5, 7),
    "NexusLinkGameplayTagsEditor": (4, 26),
    "NexusLinkGeometryCollection": (5, 0),
    "NexusLinkIKRig": (5, 0),
    "NexusLinkMetasound": (5, 0),
    "NexusLinkModelViewViewModel": (5, 5),
    "NexusLinkMovieRenderPipeline": (5, 0),
    "NexusLinkPCG": (5, 4),
    "NexusLinkPoseSearch": (5, 4),
    "NexusLinkSemanticSearch": (5, 8),
    "NexusLinkStateTree": (5, 5),
}


def filter_project_descriptor(descriptor, extensions, engine_path: Path, *, include_unlisted=False):
    """返回禁用的扩展以及从描述符移除的工程模块。"""
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

    engine_plugins = {
        plugin.stem for plugin in (engine / "Plugins").rglob("*.uplugin")
    }
    references = descriptor["Plugins"]
    configured = {plugin["Name"]: plugin for plugin in references}
    disabled = []
    for extension in extensions:
        reference = configured.get(extension.stem)
        if not (reference["Enabled"] if reference else include_unlisted):
            continue
        dependencies = json.loads(extension.read_text(encoding="utf-8-sig")).get("Plugins", [])
        minimum = _MINIMUM_ENGINE_VERSIONS.get(extension.stem, (0, 0))
        supported = engine_version >= minimum and all(
            dependency["Name"] in engine_plugins or dependency["Name"] == "NexusLink"
            for dependency in dependencies
            if dependency["Enabled"] and not dependency.get("Optional", False)
        )
        if reference and not supported:
            reference["Enabled"] = False
            disabled.append(extension.stem)
        elif not reference and supported:
            references.append({"Name": extension.stem, "Enabled": True})
    return disabled, removed_modules


def remove_extensions_directory(descriptor):
    additional_dirs = descriptor.get("AdditionalPluginDirectories", [])
    if EXTENSIONS_DIRECTORY in additional_dirs:
        additional_dirs.remove(EXTENSIONS_DIRECTORY)
