# Copyright byteyang. All Rights Reserved.
"""PIE / Runtime 测试辅助（对齐 spawn_runtime_actor 单条 API）。"""

from __future__ import annotations

from typing import Any, Dict, List

from _framework.mcp_client import MCPClient, cap_first


def pie_status_entry(status: dict) -> dict:
    return cap_first(status) if status.get("results") else status


def pie_is_running(status: dict) -> bool:
    entry = pie_status_entry(status)
    if entry.get("isPIERunning") is True:
        return True
    return entry.get("state") in ("running", "playing")


def spawn_runtime_actors(mcp: MCPClient, specs: List[Dict[str, Any]]) -> List[str]:
    """逐条 spawn_runtime_actor；每条 spec 含 blueprintPath/className 与可选位置/旋转。"""
    names: List[str] = []
    for spec in specs:
        r = mcp.call("spawn_actor", **spec)
        entry = cap_first(r)
        if entry.get("error"):
            continue
        name = entry.get("actorName") or entry.get("name")
        if name:
            names.append(str(name))
    return names


def destroy_runtime_actors(mcp: MCPClient, names: List[str]) -> None:
    for name in names:
        try:
            mcp.call("destroy_actor", actorName=name)
        except Exception:
            try:
                mcp.call("destroy_actor", actorNames=[name])
            except Exception:
                pass
