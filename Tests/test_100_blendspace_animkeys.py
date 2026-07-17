# Copyright byteyang. All Rights Reserved.
"""Tier3-3a: BlendSpace 创建/读取/管理 + AnimSequence 曲线关键帧扩展。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.l3_asset


# ── BlendSpace ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def bs_path(test_ns, mcp):
    """发现项目中存在的 BlendSpace，或跳过。"""
    r = mcp.call_capability(
        "search_asset",
        query="",
        assetType="blend_space",
        pathFilter="/Game/",
        limit=1,
    )
    assets = (r.get("assets") or []) if isinstance(r, dict) else []
    if not assets:
        pytest.skip("项目中无 BlendSpace 资产，跳过只读测试")
    return assets[0].get("path") or assets[0].get("assetPath")


@pytest.fixture(scope="module")
def skel_path(mcp):
    """发现项目中任意 Skeleton 资产路径。"""
    r = mcp.call_capability(
        "search_asset",
        query="",
        assetType="Skeleton",
        pathFilter="/Game/",
        limit=1,
    )
    assets = (r.get("assets") or []) if isinstance(r, dict) else []
    if not assets:
        pytest.skip("项目中无 Skeleton 资产，跳过 BlendSpace 创建测试")
    return assets[0].get("path") or assets[0].get("assetPath")


def test_create_blend_space(test_ns, skel_path, mcp):
    new_path = f"{test_ns}/BS_Test"
    r = mcp.call_capability(
        "create_asset_blend_space",
        assetPath=new_path,
        skeletonPath=skel_path,
    )
    results = (r.get("results") or []) if isinstance(r, dict) else []
    assert results, f"create_asset_blend_space 无返回: {r}"
    entry = results[0]
    assert not entry.get("error") and entry.get("success") is not False, entry
    assert entry.get("assetType") in ("BlendSpace", "BlendSpace1D"), entry


def test_get_blend_space(bs_path, mcp):
    r = mcp.call_capability("get_asset_blend_space", assetPath=bs_path)
    results = (r.get("results") or []) if isinstance(r, dict) else []
    assert results, f"get_asset_blend_space 无返回: {r}"
    entry = results[0]
    assert entry.get("assetType") in ("BlendSpace", "BlendSpace1D"), entry
    assert "axes" in entry, entry
    assert "samples" in entry, entry


def test_manage_blend_space_set_axis(test_ns, skel_path, mcp):
    new_path = f"{test_ns}/BS_ManageTest"
    mcp.call_capability(
        "create_asset_blend_space",
        assetPath=new_path,
        skeletonPath=skel_path,
    )
    r = mcp.call_capability(
        "manage_asset_blend_space",
        assetPath=new_path,
        operations=[{
            "action": "set_axis",
            "axisIndex": 0,
            "displayName": "Speed",
            "min": 0.0,
            "max": 600.0,
            "gridNum": 4,
        }],
    )
    results = (r.get("results") or []) if isinstance(r, dict) else []
    assert results, f"manage_asset_blend_space 无返回: {r}"
    entry = results[0]
    assert not entry.get("error") and entry.get("success") is not False, entry


# ── AnimSequence 曲线关键帧 ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def anim_seq_path(mcp):
    r = mcp.call_capability(
        "search_asset",
        query="",
        assetType="AnimSequence",
        pathFilter="/Game/",
        limit=1,
    )
    assets = (r.get("assets") or []) if isinstance(r, dict) else []
    if not assets:
        pytest.skip("项目中无 AnimSequence，跳过曲线测试")
    return assets[0].get("path") or assets[0].get("assetPath")


def test_add_float_curve(anim_seq_path, mcp):
    r = mcp.call_capability(
        "manage_asset_anim_sequence",
        assetPath=anim_seq_path,
        action="add_float_curve",
        curveName="TestCurve_MCP",
    )
    results = (r.get("results") or []) if isinstance(r, dict) else []
    assert results, f"add_float_curve 无返回: {r}"
    entry = results[0]
    assert (not entry.get("error") and entry.get("success") is not False) or "已存在" in entry.get("note", ""), entry


def test_set_curve_key(anim_seq_path, mcp):
    mcp.call_capability(
        "manage_asset_anim_sequence",
        assetPath=anim_seq_path,
        action="add_float_curve",
        curveName="TestCurve_MCP",
    )
    r = mcp.call_capability(
        "manage_asset_anim_sequence",
        assetPath=anim_seq_path,
        action="set_curve_key",
        curveName="TestCurve_MCP",
        time=0.5,
        value=1.0,
    )
    results = (r.get("results") or []) if isinstance(r, dict) else []
    assert results, f"set_curve_key 无返回: {r}"
    entry = results[0]
    assert not entry.get("error") and entry.get("success") is not False, entry


def test_remove_curve(anim_seq_path, mcp):
    mcp.call_capability(
        "manage_asset_anim_sequence",
        assetPath=anim_seq_path,
        action="add_float_curve",
        curveName="TestCurve_MCP_Remove",
    )
    r = mcp.call_capability(
        "manage_asset_anim_sequence",
        assetPath=anim_seq_path,
        action="remove_curve",
        curveName="TestCurve_MCP_Remove",
    )
    results = (r.get("results") or []) if isinstance(r, dict) else []
    assert results, f"remove_curve 无返回: {r}"
    entry = results[0]
    assert entry.get("removed"), entry
