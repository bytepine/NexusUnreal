# Copyright byteyang. All Rights Reserved.
"""阶段十四：关卡 get/manage（磁盘 Actor 增删）。"""

from __future__ import annotations

import contextlib

import pytest

from _framework.asset_helpers import ensure_blueprint, first_level_path
from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l3_asset


@pytest.fixture(scope="module")
def scratch_level(test_ns, mcp) -> str:
    """复制模板关卡到 test_ns，供 manage_asset_level 磁盘写操作。"""
    src = first_level_path(mcp)
    if not src:
        pytest.skip("无法定位关卡地图样本")
    dup = f"{test_ns}/Maps/L_McpScratch"
    with contextlib.suppress(MCPError):
        mcp.call_capability("delete_asset", assetPath=dup)
    try:
        dup_r = mcp.call_capability("duplicate_asset", assetPath=src, newPath=dup)
    except MCPError as e:
        pytest.skip(f"duplicate 关卡失败：{e}")
    dup_entry = cap_first(dup_r)
    actual = dup_entry.get("newPath") or dup_entry.get("path") or dup
    if dup_entry.get("error"):
        pytest.skip(f"duplicate 关卡返回 error：{dup_entry}")
    with contextlib.suppress(MCPError):
        mcp.call_capability("save_asset", assetPaths=[actual])
    probe = mcp.call_capability(
        "get_asset_level",
        assetPath=actual,
        sections=["settings"],
        limit=1,
    )
    probe_entry = cap_first(probe)
    if probe_entry.get("error"):
        pytest.skip(f"副本关卡不可读：{probe_entry}")
    return actual


def test_get_asset_level_actors_and_settings(mcp, require_tools):
    require_tools("get_asset_level")
    path = first_level_path(mcp)
    assert path, "无法定位关卡地图样本"
    r = mcp.call_capability(
        "get_asset_level",
        assetPath=path,
        sections=["actors", "settings"],
        limit=20,
    )
    entry = (r.get("results") or [r])[0]
    assert not entry.get("error"), entry
    assert entry.get("packagePath"), entry
    assert "actorTotalCount" in entry, entry
    assert isinstance(entry.get("actors"), list), entry
    assert "settings" in entry, entry


def test_manage_level_spawn_and_remove_actor(test_ns, mcp, scratch_level, require_tools):
    """manage_asset_level：在副本关卡 spawn Actor 后 remove。"""
    require_tools("manage_asset_level", "get_asset_level")
    bp = ensure_blueprint(mcp, test_ns, "BP_LevelDiskProbe")

    spawn = mcp.call_capability(
        "manage_asset_level",
        assetPath=scratch_level,
        action="spawn_actor",
        blueprintPath=bp,
        location="0,0,400",
    )
    spawn_entry = cap_first(spawn)
    assert not spawn_entry.get("error"), spawn_entry
    actor_name = (
        spawn_entry.get("actorName")
        or spawn_entry.get("label")
        or spawn_entry.get("name")
    )
    assert actor_name, spawn_entry

    after = cap_first(
        mcp.call_capability(
            "get_asset_level",
            assetPath=scratch_level,
            sections=["actors"],
            nameFilter=str(actor_name),
            limit=50,
        )
    )
    actors = after.get("actors") or []
    assert actors, f"spawn 后未在关卡中找到 Actor：{after!r}"

    remove = mcp.call_capability(
        "manage_asset_level",
        assetPath=scratch_level,
        action="remove_actor",
        actorName=actor_name,
    )
    remove_entry = cap_first(remove)
    assert not remove_entry.get("error"), remove_entry

    gone = cap_first(
        mcp.call_capability(
            "get_asset_level",
            assetPath=scratch_level,
            sections=["actors"],
            nameFilter=str(actor_name),
            limit=50,
        )
    )
    remaining = gone.get("actors") or []
    assert not remaining, f"remove 后 Actor 仍在关卡中：{gone!r}"
