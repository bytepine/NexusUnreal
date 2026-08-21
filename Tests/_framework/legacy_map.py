# Copyright byteyang. All Rights Reserved.
"""旧 MCP 工具名 → 当前 Capability 名映射表。

权威：NexusLink/Resources/legacy_capability_names.json。
MCPClient.call() 仅为外部旧调用做名字路由；测试应直接用规范名。
已拆分的工具（get_lua / manage_lua 等）不在表中。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

_HERE = Path(__file__).resolve()


def _legacy_json_path() -> Path:
    # Tests/_framework → nexus-unreal/Plugins/Developer/NexusLink/Resources
    p = _HERE.parents[2] / "Plugins" / "Developer" / "NexusLink" / "Resources" / "legacy_capability_names.json"
    if p.is_file():
        return p
    raise FileNotFoundError(f"legacy_capability_names.json not found: {p}")


LEGACY_CAP_NAMES: Dict[str, str] = json.loads(_legacy_json_path().read_text(encoding="utf-8"))

META_TOOLS = frozenset({
    "search_capabilities",
    "call_capability",
    "submit_feedback",
    "list_unreal_instances",
    "connect_unreal_instance",
})
