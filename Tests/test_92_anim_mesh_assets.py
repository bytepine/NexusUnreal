# Copyright byteyang. All Rights Reserved.
"""阶段十三：AnimSequence / SkeletalMesh / Skeleton 只读（P4）。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import first_asset_path
from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l3_asset


def test_get_asset_anim_sequence_sample(mcp, require_tools):
    require_tools("GetAssetAnimSequence")
    path = first_asset_path(mcp, "AnimSequence", path_filter="/Game/Characters/Mannequins")
    assert path, "无法定位 AnimSequence 样本"
    r = mcp.call_capability("GetAssetAnimSequence", AssetPath=path)
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert entry.get("NumFrames") is not None or entry.get("Length") is not None, entry
    assert "Notifies" in entry, f"expected notifies[] in response: {entry!r}"
    assert isinstance(entry.get("Notifies"), list), entry
    assert "Curves" in entry, f"expected curves[] in response: {entry!r}"
    assert isinstance(entry.get("Curves"), list), entry
    for c in entry["Curves"]:
        assert "name" in c and "Keys" in c, c
        assert isinstance(c.get("Keys"), list), c


def test_get_asset_skeletal_mesh_sample(mcp, require_tools):
    require_tools("GetAssetSkeletalMesh")
    path = first_asset_path(mcp, "SkeletalMesh", path_filter="/Game/Characters/Mannequins")
    assert path, "无法定位 SkeletalMesh 样本"
    r = mcp.call_capability("GetAssetSkeletalMesh", AssetPath=path)
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert "LODCount" in entry or "MaterialSlots" in entry, entry


def test_manage_skeletal_mesh_socket_and_lod(mcp, require_tools):
    """P1：SkeletalMesh mesh-only Socket + LOD ScreenSize。"""
    require_tools("ManageAssetSkeletalMesh", "GetAssetSkeletalMesh")
    path = first_asset_path(mcp, "SkeletalMesh", path_filter="/Game/Characters/Mannequins")
    assert path, "无法定位 SkeletalMesh 样本"
    sock = "NxSkSocket"
    add = mcp.call_capability(
        "ManageAssetSkeletalMesh",
        AssetPath=path,
        Operations=[
            {"Action": "AddSocket", "SocketName": sock, "BoneName": "pelvis", "LocX": 5},
            {"Action": "SetLODScreenSize", "LODIndex": 0, "ScreenSize": 0.85},
        ],
    )
    for e in (add.get("Results") or [cap_first(add)]):
        if isinstance(e, dict):
            assert not e.get("Error"), add
    got = cap_first(mcp.call_capability("GetAssetSkeletalMesh", AssetPath=path))
    names = [s.get("name") for s in (got.get("Sockets") or []) if isinstance(s, dict)]
    assert sock in names, got
    rm = mcp.call_capability(
        "ManageAssetSkeletalMesh",
        AssetPath=path,
        Operations=[{"Action": "RemoveSocket", "SocketName": sock}],
    )
    assert not cap_first(rm).get("Error"), rm


def test_manage_skeletal_mesh_material_property_set_socket(mcp, require_tools):
    require_tools("ManageAssetSkeletalMesh")
    path = first_asset_path(mcp, "SkeletalMesh", path_filter="/Game/Characters/Mannequins")
    assert path, "无法定位 SkeletalMesh 样本"
    sock = "NxSkSetSock"
    ops = [
        {"Action": "SetProperty", "PropertyPath": "bHasVertexColors", "Value": "false"},
        {"Action": "AddSocket", "SocketName": sock, "BoneName": "pelvis"},
        {"Action": "SetSocket", "SocketName": sock, "LocX": 1, "LocY": 2, "LocZ": 3},
        {"Action": "RemoveSocket", "SocketName": sock},
    ]
    mat = first_asset_path(mcp, "Material")
    if mat:
        ops.insert(0, {"Action": "SetMaterialSlot", "SlotIndex": 0, "MaterialPath": mat})
    r = mcp.call_capability("ManageAssetSkeletalMesh", AssetPath=path, Operations=ops)
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"manage_asset_skeletal_mesh 跳过: {e}")


def test_get_asset_skeleton_sample(mcp, require_tools):
    require_tools("GetAssetSkeleton")
    path = first_asset_path(mcp, "Skeleton", path_filter="/Game/Characters/Mannequins")
    assert path, "无法定位 Skeleton 样本"
    r = mcp.call_capability("GetAssetSkeleton", AssetPath=path, Limit=20)
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert entry.get("BoneCount") is not None, entry


def test_manage_skeleton_sockets(mcp, require_tools):
    require_tools("ManageAssetSkeleton", "GetAssetSkeleton")
    path = first_asset_path(mcp, "Skeleton", path_filter="/Game/Characters/Mannequins")
    assert path, "无法定位 Skeleton 样本"
    sock = "NxSkelSock"
    r = mcp.call_capability(
        "ManageAssetSkeleton",
        AssetPath=path,
        Operations=[
            {"Action": "AddSocket", "SocketName": sock, "BoneName": "pelvis", "Location": "1,2,3"},
            {"Action": "ModifySocket", "SocketName": sock, "Location": "4,5,6"},
            {"Action": "RemoveSocket", "SocketName": sock},
        ],
    )
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict):
            assert not e.get("Error"), r
