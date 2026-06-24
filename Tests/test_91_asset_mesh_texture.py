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
    results = r.get("results") or [r]
    entry = results[0] if results else r
    assert not entry.get("error"), entry
    assert entry.get("success") is True, entry


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
        entry = (probe.get("results") or [probe])[0]
        if not entry.get("error") and entry.get("width") and entry.get("height"):
            path = candidate
            break
    if not path:
        path = "/Game/Mannequin/Character/Textures/T_Male_N"
    assert path, "无法定位有效 Texture2D 样本"
    r = mcp.call_capability("get_asset_texture", assetPath=path)
    entry = (r.get("results") or [r])[0]
    assert not entry.get("error"), entry
    assert entry.get("width") and entry.get("height"), entry


def test_get_asset_static_mesh_project_sample(mcp, require_tools):
    """get_asset_static_mesh：项目内找 StaticMesh 做只读快照。"""
    require_tools("get_asset_static_mesh")
    path = first_asset_path(mcp, "StaticMesh")
    assert path, "无法定位 StaticMesh 样本"
    r = mcp.call_capability("get_asset_static_mesh", assetPath=path)
    results = r.get("results") or [r]
    entry = results[0] if results else r
    assert not entry.get("error"), entry
    assert "lodCount" in entry or "materialSlots" in entry, entry
