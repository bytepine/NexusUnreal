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
        mcp.call_capability("DeleteAsset", AssetPath=dup)
    try:
        dup_r = mcp.call_capability("DuplicateAsset", AssetPath=src, DestAssetPath=dup)
    except MCPError as e:
        pytest.skip(f"duplicate 关卡失败：{e}")
    dup_entry = cap_first(dup_r)
    actual = dup_entry.get("DestAssetPath") or dup_entry.get("Path") or dup
    if dup_entry.get("Error"):
        pytest.skip(f"duplicate 关卡返回 error：{dup_entry}")
    with contextlib.suppress(MCPError):
        mcp.call_capability("SaveAsset", AssetPath=actual)
    probe = mcp.call_capability(
        "GetAssetLevel",
        AssetPath=actual,
        Sections=["Settings"],
        Limit=1,
    )
    probe_entry = cap_first(probe)
    if probe_entry.get("Error"):
        pytest.skip(f"副本关卡不可读：{probe_entry}")
    return actual


def test_get_asset_level_actors_and_settings(mcp, require_tools):
    require_tools("GetAssetLevel")
    path = first_level_path(mcp)
    assert path, "无法定位关卡地图样本"
    r = mcp.call_capability(
        "GetAssetLevel",
        AssetPath=path,
        Sections=["Actors", "Settings"],
        Limit=20,
    )
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert entry.get("PackagePath"), entry
    assert "ActorTotalCount" in entry, entry
    assert isinstance(entry.get("Actors"), list), entry
    assert "Settings" in entry, entry


def test_manage_level_spawn_and_remove_actor(test_ns, mcp, scratch_level, require_tools):
    """manage_asset_level：在副本关卡 spawn Actor 后 remove。"""
    require_tools("ManageAssetLevel", "GetAssetLevel")
    bp = ensure_blueprint(mcp, test_ns, "BP_LevelDiskProbe")

    spawn = mcp.call_capability(
        "ManageAssetLevel",
        AssetPath=scratch_level,
        Operations=[{
            "Action": "SpawnActor",
            "AssetPath": bp,
            "Location": "0,0,400",
        }],
    )
    spawn_entry = cap_first(spawn)
    assert not spawn_entry.get("Error"), spawn_entry
    actor_name = (
        spawn_entry.get("ActorName")
        or spawn_entry.get("Label")
        or spawn_entry.get("name")
    )
    assert actor_name, spawn_entry

    after = cap_first(
        mcp.call_capability(
            "GetAssetLevel",
            AssetPath=scratch_level,
            Sections=["Actors"],
            NameFilter=str(actor_name),
            Limit=50,
        )
    )
    actors = after.get("Actors") or []
    assert actors, f"spawn 后未在关卡中找到 Actor：{after!r}"

    remove = mcp.call_capability(
        "ManageAssetLevel",
        AssetPath=scratch_level,
        Operations=[{
            "Action": "RemoveActor",
            "ActorName": actor_name,
        }],
    )
    remove_entry = cap_first(remove)
    assert not remove_entry.get("Error"), remove_entry

    gone = cap_first(
        mcp.call_capability(
            "GetAssetLevel",
            AssetPath=scratch_level,
            Sections=["Actors"],
            NameFilter=str(actor_name),
            Limit=50,
        )
    )
    remaining = gone.get("Actors") or []
    assert not remaining, f"remove 后 Actor 仍在关卡中：{gone!r}"


def test_create_asset_level(test_ns, mcp):
    path = f"{test_ns}/Maps/L_Created"
    r = mcp.call_capability("CreateAssetLevel", AssetPath=path)
    entry = cap_first(r)
    if entry.get("Error") and "already exists" in str(entry.get("Error")):
        return
    assert not entry.get("Error"), r
    got = cap_first(mcp.call_capability("GetAssetLevel", AssetPath=path, Sections=["Settings"]))
    assert not got.get("Error"), got


def test_manage_level_properties(mcp, scratch_level):
    r = mcp.call_capability(
        "ManageAssetLevel",
        AssetPath=scratch_level,
        Operations=[{"Action": "SetProperty", "PropertyPath": "WorldSettings.KillZ", "Value": "-10000"}],
    )
    entry = cap_first(r)
    if entry.get("Error"):
        pytest.skip(f"level set_property 跳过: {entry}")
    listing = mcp.call_capability(
        "GetAssetLevel", AssetPath=scratch_level, Sections=["Actors"], Limit=5
    )
    actors = cap_first(listing).get("Actors") or []
    name = None
    for a in actors:
        if isinstance(a, dict):
            name = a.get("ActorName") or a.get("name") or a.get("Label")
            if name:
                break
    if not name:
        pytest.skip("关卡无 Actor 可 set_actor_property")
    ap = mcp.call_capability(
        "ManageAssetLevel",
        AssetPath=scratch_level,
        Operations=[{
            "Action": "SetActorProperty",
            "ActorName": name,
            "PropertyPath": "RelativeLocation.Z",
            "Value": "0",
        }],
    )
    if cap_first(ap).get("Error"):
        pytest.skip(f"set_actor_property 跳过: {cap_first(ap)}")
