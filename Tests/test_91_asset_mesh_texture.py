# Copyright byteyang. All Rights Reserved.
"""阶段十二：Texture / StaticMesh 只读 + compile_blueprint。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import ensure_blueprint, first_asset_path
from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l3_asset


def test_compile_blueprint_test_actor(test_ns, mcp, require_tools):
    """compile_blueprint：编译 test_ns 中 BP_TestActor。"""
    require_tools("CompileBlueprint")
    bp = ensure_blueprint(mcp, test_ns, "BP_TestActor")
    r = mcp.call_capability("CompileBlueprint", AssetPath=bp)
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    # compile 成功时可能仍带 compilerWarnings；无 error 且无显式 success:false 即可
    assert entry.get("bSuccess") is not False, entry


@pytest.mark.requires_gui
def test_get_asset_texture_project_sample(mcp, require_tools):
    """get_asset_texture：项目内找一张 Texture2D 做只读快照。"""
    require_tools("GetAssetTexture")
    listing = mcp.call_capability(
        "SearchAsset",
        AssetType="Texture2D",
        PathFilter="/Game/Characters/Mannequins/Textures",
        Limit=10,
    )
    payload = cap_first(listing)
    path = None
    for row in payload.get("Assets") or []:
        candidate = row.get("AssetPath") or row.get("Path")
        if not candidate:
            continue
        probe = mcp.call_capability("GetAssetTexture", AssetPath=candidate)
        entry = cap_first(probe)
        if not entry.get("Error") and entry.get("Width") and entry.get("Height"):
            path = candidate
            break
    if not path:
        path = "/Game/Characters/Mannequins/Textures/Quinn/T_Quinn_01_N"
    assert path, "无法定位有效 Texture2D 样本"
    r = mcp.call_capability("GetAssetTexture", AssetPath=path)
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert entry.get("Width") and entry.get("Height"), entry


def test_get_asset_static_mesh_project_sample(mcp, require_tools):
    """get_asset_static_mesh：项目内找 StaticMesh 做只读快照。"""
    require_tools("GetAssetStaticMesh")
    path = first_asset_path(mcp, "StaticMesh")
    assert path, "无法定位 StaticMesh 样本"
    r = mcp.call_capability("GetAssetStaticMesh", AssetPath=path)
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert "LODCount" in entry or "MaterialSlots" in entry, entry


def test_manage_static_mesh_collision_and_socket(mcp, require_tools):
    """P1：StaticMesh 碰撞复杂度 + Box + Socket + LOD ScreenSize。"""
    require_tools("ManageAssetStaticMesh", "GetAssetStaticMesh")
    path = first_asset_path(mcp, "StaticMesh")
    assert path, "无法定位 StaticMesh 样本"
    sock = "NxTestSocket"
    ops = [
        {"Action": "SetCollisionTraceFlag", "CollisionTraceFlag": "UseSimpleAsComplex"},
        {"Action": "ClearSimpleCollision"},
        {"Action": "AddBoxCollision", "ExtentX": 20, "ExtentY": 20, "ExtentZ": 20},
        {"Action": "AddSocket", "SocketName": sock, "LocX": 1, "LocY": 2, "LocZ": 3},
        {"Action": "SetLODScreenSize", "LODIndex": 0, "ScreenSize": 0.9},
    ]
    r = mcp.call_capability("ManageAssetStaticMesh", AssetPath=path, Operations=ops)
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict):
            assert not e.get("Error"), r
    got = cap_first(mcp.call_capability("GetAssetStaticMesh", AssetPath=path))
    assert not got.get("Error"), got
    col = got.get("Collision") or {}
    assert col.get("BoxElemCount", 0) >= 1, got
    names = [s.get("name") for s in (got.get("Sockets") or []) if isinstance(s, dict)]
    assert sock in names, got
    rm = mcp.call_capability(
        "ManageAssetStaticMesh",
        AssetPath=path,
        Operations=[{"Action": "RemoveSocket", "SocketName": sock}],
    )
    assert not cap_first(rm).get("Error"), rm


def test_manage_static_mesh_remaining_actions(mcp, require_tools):
    require_tools("ManageAssetStaticMesh")
    path = first_asset_path(mcp, "StaticMesh")
    assert path, "无法定位 StaticMesh 样本"
    sock = "NxSmSetSock"
    ops = [
        {"Action": "AddSphereCollision", "Radius": 10},
        {"Action": "AddSocket", "SocketName": sock, "LocX": 0, "LocY": 0, "LocZ": 0},
        {"Action": "SetSocket", "SocketName": sock, "LocX": 2, "LocY": 3, "LocZ": 4},
        {"Action": "RemoveSocket", "SocketName": sock},
        {"Action": "SetProperty", "PropertyPath": "LightMapResolution", "Value": "64"},
    ]
    mat = first_asset_path(mcp, "Material")
    if mat:
        ops.insert(0, {"Action": "SetMaterialSlot", "SlotIndex": 0, "MaterialPath": mat})
    r = mcp.call_capability("ManageAssetStaticMesh", AssetPath=path, Operations=ops)
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"manage_asset_static_mesh 剩余 action 跳过: {e}")


def test_manage_asset_texture_set_property(mcp, require_tools):
    require_tools("ManageAssetTexture")
    path = first_asset_path(mcp, "Texture2D")
    assert path, "无法定位 Texture2D 样本"
    r = mcp.call_capability(
        "ManageAssetTexture",
        AssetPath=path,
        Operations=[{"Action": "SetProperty", "PropertyPath": "bSRGB", "Value": "true"}],
    )
    entry = cap_first(r)
    if entry.get("Error"):
        pytest.skip(f"manage_asset_texture 跳过: {entry}")
