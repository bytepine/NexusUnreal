# Copyright byteyang. All Rights Reserved.
"""阶段十二：Texture / StaticMesh 只读 + compile_blueprint。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import MCPError

pytestmark = pytest.mark.l3_asset


def test_compile_blueprint_test_actor(test_ns, mcp, require_tools):
    """compile_blueprint：编译 test_ns 中 BP_TestActor。"""
    require_tools("compile_blueprint")
    bp = f"{test_ns}/BP_TestActor"
    try:
        mcp.call("create_blueprint", assetPath=bp, parentClass="Actor")
    except MCPError:
        pass
    r = mcp.call_capability("compile_blueprint", assetPath=bp)
    results = r.get("results") or [r]
    entry = results[0] if results else r
    assert not entry.get("error"), entry
    assert entry.get("success") is True, entry


def test_get_asset_texture_project_sample(mcp, require_tools):
    """get_asset_texture：项目内找一张 Texture2D 做只读快照。"""
    require_tools("get_asset_texture")
    try:
        listing = mcp.call_capability(
            "search_asset",
            assetType="Texture2D",
            pathFilter="/Game/",
            limit=5,
        )
    except MCPError as e:
        pytest.skip(f"search_asset Texture2D 失败：{e}")
    assets = listing.get("assets") or []
    if not assets:
        pytest.skip("项目中无 Texture2D 样本")
    path = assets[0].get("assetPath") or assets[0].get("path")
    r = mcp.call_capability("get_asset_texture", assetPath=path)
    results = r.get("results") or [r]
    entry = results[0] if results else r
    assert not entry.get("error"), entry
    assert entry.get("width") and entry.get("height"), entry


def test_get_asset_static_mesh_project_sample(mcp, require_tools):
    """get_asset_static_mesh：项目内找 StaticMesh 做只读快照。"""
    require_tools("get_asset_static_mesh")
    try:
        listing = mcp.call_capability(
            "search_asset",
            assetType="StaticMesh",
            pathFilter="/Game/",
            limit=5,
        )
    except MCPError as e:
        pytest.skip(f"search_asset StaticMesh 失败：{e}")
    assets = listing.get("assets") or []
    if not assets:
        pytest.skip("项目中无 StaticMesh 样本")
    path = assets[0].get("assetPath") or assets[0].get("path")
    r = mcp.call_capability("get_asset_static_mesh", assetPath=path)
    results = r.get("results") or [r]
    entry = results[0] if results else r
    assert not entry.get("error"), entry
    assert "lodCount" in entry or "materialSlots" in entry, entry
