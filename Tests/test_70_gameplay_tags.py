# Copyright byteyang. All Rights Reserved.
"""阶段八：Gameplay Tags — hierarchy / asset 读取。"""

from __future__ import annotations

import pytest
from _framework.assertions import assert_tool_error

pytestmark = pytest.mark.l1_readonly


def test_tags_hierarchy(mcp, require_tools):
    require_tools("GetGameplayTags")
    r = mcp.call("GetGameplayTags", Sections=["Hierarchy"])
    assert isinstance(r, dict)


def test_tags_asset_read(mcp, test_ns):
    # Create a throwaway BP to query its tags (expected empty but graceful)
    path = f"{test_ns}/BP_TagProbe"
    try:
        mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="Actor")
    except Exception:
        pytest.skip("create_asset_blueprint unavailable")
    r = mcp.call("GetGameplayTags", Sections=["Asset"], AssetPath=path)
    assert isinstance(r, dict)
    ref = assert_tool_error(mcp.try_call("GetGameplayTags", Sections=["Referencers"], AssetPath=path))
    assert isinstance(ref, dict)
