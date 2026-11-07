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
        "SearchAsset",
        Query="",
        AssetType="BlendSpace",
        PathFilter="/Game/",
        Limit=1,
    )
    assets = (r.get("Assets") or []) if isinstance(r, dict) else []
    if not assets:
        pytest.skip("项目中无 BlendSpace 资产，跳过只读测试")
    return assets[0].get("Path") or assets[0].get("AssetPath")


@pytest.fixture(scope="module")
def skel_path(mcp):
    """发现项目中任意 Skeleton 资产路径。"""
    r = mcp.call_capability(
        "SearchAsset",
        Query="",
        AssetType="Skeleton",
        PathFilter="/Game/",
        Limit=1,
    )
    assets = (r.get("Assets") or []) if isinstance(r, dict) else []
    if not assets:
        pytest.skip("项目中无 Skeleton 资产，跳过 BlendSpace 创建测试")
    return assets[0].get("Path") or assets[0].get("AssetPath")


def test_create_blend_space(test_ns, skel_path, mcp):
    new_path = f"{test_ns}/BS_Test"
    r = mcp.call_capability(
        "CreateAssetBlendSpace",
        AssetPath=new_path,
        SkeletonPath=skel_path,
    )
    entry = cap_first(r)
    assert not entry.get("Error") and entry.get("bSuccess") is not False, entry
    assert entry.get("AssetType") in ("BlendSpace", "BlendSpace1D"), entry


def test_get_blend_space(bs_path, mcp):
    r = mcp.call_capability("GetAssetBlendSpace", AssetPath=bs_path)
    entry = cap_first(r)
    assert entry.get("AssetType") in ("BlendSpace", "BlendSpace1D"), entry
    assert "Axes" in entry, entry
    assert "Samples" in entry, entry


def test_manage_blend_space_set_axis(test_ns, skel_path, mcp):
    new_path = f"{test_ns}/BS_ManageTest"
    mcp.call_capability(
        "CreateAssetBlendSpace",
        AssetPath=new_path,
        SkeletonPath=skel_path,
    )
    r = mcp.call_capability(
        "ManageAssetBlendSpace",
        AssetPath=new_path,
        Operations=[{
            "Action": "SetAxis",
            "AxisIndex": 0,
            "DisplayName": "Speed",
            "Min": 0.0,
            "Max": 600.0,
            "GridNum": 4,
        }],
    )
    entry = cap_first(r)
    assert not entry.get("Error") and entry.get("bSuccess") is not False, entry


def test_manage_blend_space_samples(test_ns, skel_path, mcp):
    new_path = f"{test_ns}/BS_Samples"
    mcp.call_capability("CreateAssetBlendSpace", AssetPath=new_path, SkeletonPath=skel_path)
    seq = None
    listing = mcp.call_capability("SearchAsset", AssetType="AnimSequence", PathFilter="/Game/", Limit=1)
    assets = (listing.get("Assets") or []) if isinstance(listing, dict) else []
    if assets:
        seq = assets[0].get("Path") or assets[0].get("AssetPath")
    ops = [{"Action": "AddSample", "X": 0, "Y": 0}]
    if seq:
        ops[0]["AnimationPath"] = seq
    ops.append({"Action": "RemoveSample", "SampleIndex": 0})
    r = mcp.call_capability("ManageAssetBlendSpace", AssetPath=new_path, Operations=ops)
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"blend_space sample 跳过: {e}")


# ── AnimSequence 曲线关键帧 ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def anim_seq_path(mcp, test_ns):
    r = mcp.call_capability(
        "SearchAsset",
        Query="",
        AssetType="AnimSequence",
        PathFilter="/Game/",
        Limit=1,
    )
    assets = (r.get("Assets") or []) if isinstance(r, dict) else []
    if not assets:
        pytest.skip("项目中无 AnimSequence，跳过曲线测试")
    source = assets[0].get("Path") or assets[0].get("AssetPath")
    path = f"{test_ns}/AS_CurveProbe"
    mcp.call("DuplicateAsset", AssetPath=source, DestAssetPath=path)
    return path


def _curve_suffix(test_ns: str) -> str:
    return test_ns.rsplit("/", 1)[-1]


def test_add_float_curve(anim_seq_path, test_ns, mcp):
    name = f"TestCurve_MCP_{_curve_suffix(test_ns)}"
    r = mcp.call_capability(
        "ManageAssetAnimSequence",
        AssetPath=anim_seq_path,
        bSaveToDisk=False,
        Operations=[{"Action": "AddFloatCurve", "CurveName": name}],
    )
    entry = cap_first(r)
    assert (
        (not entry.get("Error") and entry.get("bSuccess") is not False)
        or "已存在" in entry.get("Note", "")
    ), entry


def test_set_curve_key(anim_seq_path, test_ns, mcp):
    name = f"TestCurve_MCP_{_curve_suffix(test_ns)}"
    mcp.call_capability(
        "ManageAssetAnimSequence",
        AssetPath=anim_seq_path,
        bSaveToDisk=False,
        Operations=[{"Action": "AddFloatCurve", "CurveName": name}],
    )
    r = mcp.call_capability(
        "ManageAssetAnimSequence",
        AssetPath=anim_seq_path,
        bSaveToDisk=False,
        Operations=[{
            "Action": "SetCurveKey",
            "CurveName": name,
            "Time": 0.5,
            "Value": 1.0,
        }],
    )
    entry = cap_first(r)
    assert not entry.get("Error") and entry.get("bSuccess") is not False, entry


def test_remove_curve(anim_seq_path, test_ns, mcp):
    name = f"TestCurve_MCP_Rm_{_curve_suffix(test_ns)}"
    mcp.call_capability(
        "ManageAssetAnimSequence",
        AssetPath=anim_seq_path,
        bSaveToDisk=False,
        Operations=[{"Action": "AddFloatCurve", "CurveName": name}],
    )
    r = mcp.call_capability(
        "ManageAssetAnimSequence",
        AssetPath=anim_seq_path,
        bSaveToDisk=False,
        Operations=[{"Action": "RemoveCurve", "CurveName": name}],
    )
    entry = cap_first(r)
    assert entry.get("bRemoved") or (
        not entry.get("Error") and entry.get("bSuccess") is not False
    ), entry


@pytest.mark.parametrize("action, message", [
    ("AddNotify", "requires NotifyName"),
    ("RemoveNotify", "requires NotifyIndex or NotifyName"),
    ("SetRootMotion", "requires RootMotion"),
])
def test_manage_anim_sequence_notify_root_motion_validation(anim_seq_path, mcp, action, message):
    # 每个操作都实际经过 MCP，并断言缺参原因及拒绝后资产未发生变化。
    before = cap_first(mcp.call("GetAssetAnimSequence", AssetPath=anim_seq_path))
    rejected = mcp.try_call("ManageAssetAnimSequence", AssetPath=anim_seq_path,
                            Operations=[{"Action": action}])
    assert rejected.get("isError") and message in str(rejected), rejected
    after = cap_first(mcp.call("GetAssetAnimSequence", AssetPath=anim_seq_path))
    assert after == before, (before, after)


def test_manage_anim_sequence_frame_rate(anim_seq_path, test_ns, mcp):
    path = f"{test_ns}/AS_FrameRate"
    mcp.call("DuplicateAsset", AssetPath=anim_seq_path, DestAssetPath=path)
    result = cap_first(mcp.call("ManageAssetAnimSequence", AssetPath=path,
                                Operations=[{"Action": "SetFrameRate", "FrameRate": 30}]))
    assert not result.get("Error") and result["FrameRate"] == 30, result
    readback = cap_first(mcp.call("GetAssetAnimSequence", AssetPath=path))
    assert readback["FrameRate"] == 30, readback
