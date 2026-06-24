# Copyright byteyang. All Rights Reserved.
"""阶段十三：AnimSequence / SkeletalMesh / Skeleton 只读（P4）。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import MCPError

pytestmark = pytest.mark.l3_asset


def _first_asset_path(mcp, asset_type: str) -> str | None:
    try:
        listing = mcp.call_capability(
            "search_asset",
            assetType=asset_type,
            pathFilter="/Game/",
            limit=5,
        )
    except MCPError:
        return None
    assets = listing.get("assets") or []
    if not assets:
        return None
    row = assets[0]
    return row.get("assetPath") or row.get("path")


def test_get_asset_anim_sequence_sample(mcp, require_tools):
    require_tools("get_asset_anim_sequence")
    path = _first_asset_path(mcp, "AnimSequence")
    if not path:
        pytest.skip("项目中无 AnimSequence 样本")
    r = mcp.call_capability("get_asset_anim_sequence", assetPath=path)
    entry = (r.get("results") or [r])[0]
    assert not entry.get("error"), entry
    assert entry.get("numFrames") is not None or entry.get("length") is not None, entry
    assert "notifies" in entry, f"expected notifies[] in response: {entry!r}"
    assert isinstance(entry.get("notifies"), list), entry


def test_get_asset_skeletal_mesh_sample(mcp, require_tools):
    require_tools("get_asset_skeletal_mesh")
    path = _first_asset_path(mcp, "SkeletalMesh")
    if not path:
        pytest.skip("项目中无 SkeletalMesh 样本")
    r = mcp.call_capability("get_asset_skeletal_mesh", assetPath=path)
    entry = (r.get("results") or [r])[0]
    assert not entry.get("error"), entry
    assert "lodCount" in entry or "materialSlots" in entry, entry


def test_get_asset_skeleton_sample(mcp, require_tools):
    require_tools("get_asset_skeleton")
    path = _first_asset_path(mcp, "Skeleton")
    if not path:
        pytest.skip("项目中无 Skeleton 样本")
    r = mcp.call_capability("get_asset_skeleton", assetPath=path, limit=20)
    entry = (r.get("results") or [r])[0]
    assert not entry.get("error"), entry
    assert entry.get("boneCount") is not None, entry
