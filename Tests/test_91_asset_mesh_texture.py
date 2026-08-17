# Copyright byteyang. All Rights Reserved.
"""阶段十二：Texture / StaticMesh 只读 + compile_blueprint。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import ensure_blueprint, first_asset_path
from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l3_asset


def test_compile_blueprint_test_actor(test_ns, mcp, require_tools):
    """compile_blueprint：编译 test_ns 中 BP_TestActor。"""
    require_tools("compile_blueprint")
    bp = ensure_blueprint(mcp, test_ns, "BP_TestActor")
    r = mcp.call_capability("compile_blueprint", assetPath=bp)
    entry = cap_first(r)
    assert not entry.get("error"), entry
    # compile 成功时可能仍带 compilerWarnings；无 error 且无显式 success:false 即可
    assert entry.get("success") is not False, entry


@pytest.mark.requires_gui
def test_get_asset_texture_project_sample(mcp, require_tools):
    """get_asset_texture：项目内找一张 Texture2D 做只读快照。"""
    require_tools("get_asset_texture")
    listing = mcp.call_capability(
        "search_asset",
        assetType="Texture2D",
        pathFilter="/Game/Mannequin/Character/Textures",
        limit=10,
    )
    payload = cap_first(listing)
    path = None
    for row in payload.get("assets") or []:
        candidate = row.get("assetPath") or row.get("path")
        if not candidate:
            continue
        probe = mcp.call_capability("get_asset_texture", assetPath=candidate)
        entry = cap_first(probe)
        if not entry.get("error") and entry.get("width") and entry.get("height"):
            path = candidate
            break
    if not path:
        path = "/Game/Mannequin/Character/Textures/T_Male_N"
    assert path, "无法定位有效 Texture2D 样本"
    r = mcp.call_capability("get_asset_texture", assetPath=path)
    entry = cap_first(r)
    assert not entry.get("error"), entry
    assert entry.get("width") and entry.get("height"), entry


def test_get_asset_static_mesh_project_sample(mcp, require_tools):
    """get_asset_static_mesh：项目内找 StaticMesh 做只读快照。"""
    require_tools("get_asset_static_mesh")
    path = first_asset_path(mcp, "StaticMesh")
    assert path, "无法定位 StaticMesh 样本"
    r = mcp.call_capability("get_asset_static_mesh", assetPath=path)
    entry = cap_first(r)
    assert not entry.get("error"), entry
    assert "lodCount" in entry or "materialSlots" in entry, entry


def test_manage_static_mesh_collision_and_socket(mcp, require_tools):
    """P1：StaticMesh 碰撞复杂度 + Box + Socket + LOD ScreenSize。"""
    require_tools("manage_asset_static_mesh", "get_asset_static_mesh")
    path = first_asset_path(mcp, "StaticMesh")
    assert path, "无法定位 StaticMesh 样本"
    sock = "NxTestSocket"
    ops = [
        {"action": "set_collision_trace_flag", "collisionTraceFlag": "UseSimpleAsComplex"},
        {"action": "clear_simple_collision"},
        {"action": "add_box_collision", "extentX": 20, "extentY": 20, "extentZ": 20},
        {"action": "add_socket", "socketName": sock, "locX": 1, "locY": 2, "locZ": 3},
        {"action": "set_lod_screen_size", "lodIndex": 0, "screenSize": 0.9},
    ]
    r = mcp.call_capability("manage_asset_static_mesh", assetPath=path, operations=ops)
    for e in (r.get("results") or [cap_first(r)]):
        if isinstance(e, dict):
            assert not e.get("error"), r
    got = cap_first(mcp.call_capability("get_asset_static_mesh", assetPath=path))
    assert not got.get("error"), got
    col = got.get("collision") or {}
    assert col.get("boxElemCount", 0) >= 1, got
    names = [s.get("name") for s in (got.get("sockets") or []) if isinstance(s, dict)]
    assert sock in names, got
    rm = mcp.call_capability(
        "manage_asset_static_mesh",
        assetPath=path,
        operations=[{"action": "remove_socket", "socketName": sock}],
    )
    assert not cap_first(rm).get("error"), rm
