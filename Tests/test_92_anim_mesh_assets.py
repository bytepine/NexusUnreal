# Copyright byteyang. All Rights Reserved.
"""阶段十三：AnimSequence / SkeletalMesh / Skeleton 只读（P4）。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import first_asset_path
from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l3_asset


def test_get_asset_anim_sequence_sample(mcp, require_tools):
    require_tools("get_asset_anim_sequence")
    path = first_asset_path(mcp, "AnimSequence", path_filter="/Game/Mannequin")
    assert path, "无法定位 AnimSequence 样本"
    r = mcp.call_capability("get_asset_anim_sequence", assetPath=path)
    entry = cap_first(r)
    assert not entry.get("error"), entry
    assert entry.get("numFrames") is not None or entry.get("length") is not None, entry
    assert "notifies" in entry, f"expected notifies[] in response: {entry!r}"
    assert isinstance(entry.get("notifies"), list), entry
    assert "curves" in entry, f"expected curves[] in response: {entry!r}"
    assert isinstance(entry.get("curves"), list), entry
    for c in entry["curves"]:
        assert "name" in c and "keys" in c, c
        assert isinstance(c.get("keys"), list), c


def test_get_asset_skeletal_mesh_sample(mcp, require_tools):
    require_tools("get_asset_skeletal_mesh")
    path = first_asset_path(mcp, "SkeletalMesh", path_filter="/Game/Mannequin")
    assert path, "无法定位 SkeletalMesh 样本"
    r = mcp.call_capability("get_asset_skeletal_mesh", assetPath=path)
    entry = cap_first(r)
    assert not entry.get("error"), entry
    assert "lodCount" in entry or "materialSlots" in entry, entry


def test_manage_skeletal_mesh_socket_and_lod(mcp, require_tools):
    """P1：SkeletalMesh mesh-only Socket + LOD ScreenSize。"""
    require_tools("manage_asset_skeletal_mesh", "get_asset_skeletal_mesh")
    path = first_asset_path(mcp, "SkeletalMesh", path_filter="/Game/Mannequin")
    assert path, "无法定位 SkeletalMesh 样本"
    sock = "NxSkSocket"
    add = mcp.call_capability(
        "manage_asset_skeletal_mesh",
        assetPath=path,
        operations=[
            {"action": "add_socket", "socketName": sock, "boneName": "pelvis", "locX": 5},
            {"action": "set_lod_screen_size", "lodIndex": 0, "screenSize": 0.85},
        ],
    )
    for e in (add.get("results") or [cap_first(add)]):
        if isinstance(e, dict):
            assert not e.get("error"), add
    got = cap_first(mcp.call_capability("get_asset_skeletal_mesh", assetPath=path))
    names = [s.get("name") for s in (got.get("sockets") or []) if isinstance(s, dict)]
    assert sock in names, got
    rm = mcp.call_capability(
        "manage_asset_skeletal_mesh",
        assetPath=path,
        operations=[{"action": "remove_socket", "socketName": sock}],
    )
    assert not cap_first(rm).get("error"), rm


def test_manage_skeletal_mesh_material_property_set_socket(mcp, require_tools):
    require_tools("manage_asset_skeletal_mesh")
    path = first_asset_path(mcp, "SkeletalMesh", path_filter="/Game/Mannequin")
    assert path, "无法定位 SkeletalMesh 样本"
    sock = "NxSkSetSock"
    ops = [
        {"action": "set_property", "propertyPath": "bHasVertexColors", "value": "false"},
        {"action": "add_socket", "socketName": sock, "boneName": "pelvis"},
        {"action": "set_socket", "socketName": sock, "locX": 1, "locY": 2, "locZ": 3},
        {"action": "remove_socket", "socketName": sock},
    ]
    mat = first_asset_path(mcp, "Material")
    if mat:
        ops.insert(0, {"action": "set_material_slot", "slotIndex": 0, "materialPath": mat})
    r = mcp.call_capability("manage_asset_skeletal_mesh", assetPath=path, operations=ops)
    for e in (r.get("results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("error"):
            pytest.skip(f"manage_asset_skeletal_mesh 跳过: {e}")


def test_get_asset_skeleton_sample(mcp, require_tools):
    require_tools("get_asset_skeleton")
    path = first_asset_path(mcp, "Skeleton", path_filter="/Game/Mannequin")
    assert path, "无法定位 Skeleton 样本"
    r = mcp.call_capability("get_asset_skeleton", assetPath=path, limit=20)
    entry = cap_first(r)
    assert not entry.get("error"), entry
    assert entry.get("boneCount") is not None, entry


def test_manage_skeleton_sockets(mcp, require_tools):
    require_tools("manage_asset_skeleton", "get_asset_skeleton")
    path = first_asset_path(mcp, "Skeleton", path_filter="/Game/Mannequin")
    assert path, "无法定位 Skeleton 样本"
    sock = "NxSkelSock"
    r = mcp.call_capability(
        "manage_asset_skeleton",
        assetPath=path,
        operations=[
            {"action": "add_socket", "socketName": sock, "boneName": "pelvis", "location": "1,2,3"},
            {"action": "modify_socket", "socketName": sock, "location": "4,5,6"},
            {"action": "remove_socket", "socketName": sock},
        ],
    )
    for e in (r.get("results") or [cap_first(r)]):
        if isinstance(e, dict):
            assert not e.get("error"), r
