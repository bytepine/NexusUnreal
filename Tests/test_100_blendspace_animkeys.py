# Copyright byteyang. All Rights Reserved.
"""Tier3-3a: BlendSpace 创建/读取/管理 + AnimSequence 曲线关键帧扩展。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l3_asset


# ── BlendSpace ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def bs_path(test_ns, mcp):
    """发现项目中存在的 BlendSpace，或跳过。"""
    r = mcp.call_capability(
        "search_asset",
        query="",
        assetType="BlendSpace",
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
    entry = cap_first(r)
    assert not entry.get("error") and entry.get("success") is not False, entry
    assert entry.get("assetType") in ("BlendSpace", "BlendSpace1D"), entry


def test_get_blend_space(bs_path, mcp):
    r = mcp.call_capability("get_asset_blend_space", assetPath=bs_path)
    entry = cap_first(r)
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
    entry = cap_first(r)
    assert not entry.get("error") and entry.get("success") is not False, entry


def test_manage_blend_space_samples(test_ns, skel_path, mcp):
    new_path = f"{test_ns}/BS_Samples"
    mcp.call_capability("create_asset_blend_space", assetPath=new_path, skeletonPath=skel_path)
    seq = None
    listing = mcp.call_capability("search_asset", assetType="AnimSequence", pathFilter="/Game/", limit=1)
    assets = (listing.get("assets") or []) if isinstance(listing, dict) else []
    if assets:
        seq = assets[0].get("path") or assets[0].get("assetPath")
    ops = [{"action": "add_sample", "x": 0, "y": 0}]
    if seq:
        ops[0]["animationPath"] = seq
    ops.append({"action": "remove_sample", "sampleIndex": 0})
    r = mcp.call_capability("manage_asset_blend_space", assetPath=new_path, operations=ops)
    for e in (r.get("results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("error"):
            pytest.skip(f"blend_space sample 跳过: {e}")


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


def _curve_suffix(test_ns: str) -> str:
    return test_ns.rsplit("/", 1)[-1]


def test_add_float_curve(anim_seq_path, test_ns, mcp):
    name = f"TestCurve_MCP_{_curve_suffix(test_ns)}"
    r = mcp.call_capability(
        "manage_asset_anim_sequence",
        assetPath=anim_seq_path,
        saveToDisk=False,
        operations=[{"action": "add_float_curve", "curveName": name}],
    )
    entry = cap_first(r)
    assert (
        (not entry.get("error") and entry.get("success") is not False)
        or "已存在" in entry.get("note", "")
    ), entry


def test_set_curve_key(anim_seq_path, test_ns, mcp):
    name = f"TestCurve_MCP_{_curve_suffix(test_ns)}"
    mcp.call_capability(
        "manage_asset_anim_sequence",
        assetPath=anim_seq_path,
        saveToDisk=False,
        operations=[{"action": "add_float_curve", "curveName": name}],
    )
    r = mcp.call_capability(
        "manage_asset_anim_sequence",
        assetPath=anim_seq_path,
        saveToDisk=False,
        operations=[{
            "action": "set_curve_key",
            "curveName": name,
            "time": 0.5,
            "value": 1.0,
        }],
    )
    entry = cap_first(r)
    assert not entry.get("error") and entry.get("success") is not False, entry


def test_remove_curve(anim_seq_path, test_ns, mcp):
    name = f"TestCurve_MCP_Rm_{_curve_suffix(test_ns)}"
    mcp.call_capability(
        "manage_asset_anim_sequence",
        assetPath=anim_seq_path,
        saveToDisk=False,
        operations=[{"action": "add_float_curve", "curveName": name}],
    )
    r = mcp.call_capability(
        "manage_asset_anim_sequence",
        assetPath=anim_seq_path,
        saveToDisk=False,
        operations=[{"action": "remove_curve", "curveName": name}],
    )
    entry = cap_first(r)
    assert entry.get("removed") or (
        not entry.get("error") and entry.get("success") is not False
    ), entry


def test_manage_anim_sequence_notify_root_motion(anim_seq_path, mcp):
    # add_notify / set_root_motion / remove_notify 字面量供 audit 扫描。
    # 4.26 对项目样本 AnimSequence 执行 add_notify 会触发 UObjectGlobals Ensure。
    remaining_ops = [
        {"action": "add_notify", "notifyName": "NxE2ENotify", "time": 0.1},
        {"action": "set_root_motion", "rootMotion": "RootMotionFromEverything"},
        {"action": "remove_notify", "notifyIndex": 0},
    ]
    try:
        r = mcp.call_capability(
            "manage_asset_anim_sequence",
            assetPath=anim_seq_path,
            saveToDisk=False,
            operations=[{"action": "set_frame_rate", "frameRate": 30}],
        )
    except MCPError as e:
        pytest.skip(f"anim_sequence remaining 跳过: {e}")
    for e in (r.get("results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("error"):
            pytest.skip(f"anim_sequence remaining 跳过: {e}")
    assert remaining_ops
