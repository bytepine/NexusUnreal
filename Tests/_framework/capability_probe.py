# Copyright byteyang. All Rights Reserved.
"""SearchMode 下通过 search_capabilities 探测 Capability 是否可用。"""

from __future__ import annotations

from typing import Iterable, List

from _framework.legacy_map import LEGACY_CAP_NAMES
from _framework.mcp_client import MCPClient, MCPError

_META_ALWAYS = frozenset({"search_capabilities", "call_capability", "submit_feedback"})


def resolve_capability_name(tool_or_cap: str) -> str:
    return LEGACY_CAP_NAMES.get(tool_or_cap, tool_or_cap)


def is_capability_available(mcp: MCPClient, tool_or_cap: str) -> bool:
    """tools/list 在 SearchMode 下只有元工具；改走精确 capability 查询。"""
    name = resolve_capability_name(tool_or_cap)
    if name in _META_ALWAYS:
        return True
    try:
        r = mcp.call("search_capabilities", capabilityName=name)
    except MCPError:
        return False
    if r.get("errorKind") in ("not_found", "disabled"):
        return False
    if r.get("capability"):
        return True
    caps = r.get("capabilities")
    if isinstance(caps, list):
        return any(
            isinstance(c, dict) and c.get("name") == name for c in caps
        )
    return False


def require_capabilities(mcp: MCPClient, *names: str) -> None:
    missing = [n for n in names if not is_capability_available(mcp, n)]
    if missing:
        resolved = [resolve_capability_name(n) for n in missing]
        raise _MissingCapabilities(missing, resolved)


class _MissingCapabilities(Exception):
    def __init__(self, requested: Iterable[str], resolved: List[str]) -> None:
        self.requested = list(requested)
        self.resolved = resolved
        super().__init__(f"required capability not available: {resolved}")
