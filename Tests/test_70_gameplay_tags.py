# Copyright byteyang. All Rights Reserved.
"""阶段八：Gameplay Tags — hierarchy / asset 读取。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.l1_readonly


def test_tags_hierarchy(mcp, require_tools):
    require_tools("get_gameplay_tags")
    r = mcp.call("get_gameplay_tags", sections=["hierarchy"])
    assert isinstance(r, dict)


def test_tags_asset_read(mcp, test_ns):
    # Create a throwaway BP to query its tags (expected empty but graceful)
    path = f"{test_ns}/BP_TagProbe"
    try:
        mcp.call("create_asset_blueprint", assetPath=path, parentClass="Actor")
    except Exception:
        pytest.skip("create_asset_blueprint unavailable")
    r = mcp.call("get_gameplay_tags", sections=["asset"], assetPath=path)
    assert isinstance(r, dict)
    ref = mcp.call("get_gameplay_tags", sections=["referencers"], assetPath=path)
    assert isinstance(ref, dict)
