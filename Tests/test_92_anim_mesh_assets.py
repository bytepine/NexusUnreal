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


def test_get_asset_skeletal_mesh_sample(mcp, require_tools):
    require_tools("get_asset_skeletal_mesh")
    path = first_asset_path(mcp, "SkeletalMesh", path_filter="/Game/Mannequin")
    assert path, "无法定位 SkeletalMesh 样本"
    r = mcp.call_capability("get_asset_skeletal_mesh", assetPath=path)
    entry = cap_first(r)
    assert not entry.get("error"), entry
    assert "lodCount" in entry or "materialSlots" in entry, entry


def test_get_asset_skeleton_sample(mcp, require_tools):
    require_tools("get_asset_skeleton")
    path = first_asset_path(mcp, "Skeleton", path_filter="/Game/Mannequin")
    assert path, "无法定位 Skeleton 样本"
    r = mcp.call_capability("get_asset_skeleton", assetPath=path, limit=20)
    entry = cap_first(r)
    assert not entry.get("error"), entry
    assert entry.get("boneCount") is not None, entry
