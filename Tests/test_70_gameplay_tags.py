# Copyright byteyang. All Rights Reserved.
"""阶段八：Gameplay Tags — hierarchy / asset 读取。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.l1_readonly


def test_tags_hierarchy(mcp, require_tools):
    require_tools("get_gameplay_tags")
    r = mcp.call("get_gameplay_tags", section="hierarchy")
    assert isinstance(r, dict)


def test_tags_asset_read(mcp, test_ns):
    # Create a throwaway BP to query its tags (expected empty but graceful)
    path = f"{test_ns}/BP_TagProbe"
    try:
        mcp.call("create_blueprint", assetPath=path, parentClass="Actor")
    except Exception:
        pytest.skip("create_blueprint unavailable")
    r = mcp.call("get_gameplay_tags", section="asset", assetPath=path)
    assert isinstance(r, dict)
