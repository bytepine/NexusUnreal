# Copyright byteyang. All Rights Reserved.
"""阶段七：资产引用 — 批量 dependencies / referencers。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.l1_readonly


@pytest.fixture(scope="module")
def some_assets(test_ns, mcp):
    """Create a minimal BP + material to have deterministic ref graph."""
    bp = f"{test_ns}/BP_RefTest"
    mat = f"{test_ns}/M_RefTest"
    mcp.call("create_blueprint", assetPath=bp, parentClass="Actor")
    mcp.call("create_material", assetPath=mat)
    return bp, mat


def test_dependencies_batch(mcp, some_assets):
    bp, mat = some_assets
    # get_asset_refs 已单数化为 assetPath，分别查询每个资产
    for asset in (bp, mat):
        r = mcp.call(
            "get_asset_refs",
            assetPath=asset,
            direction="dependencies",
            recursive=True,
        )
        assert isinstance(r, dict), f"get_asset_refs {asset}: {r!r}"


def test_referencers(mcp, some_assets):
    bp, _ = some_assets
    r = mcp.call("get_asset_refs", assetPath=bp, direction="referencers")
    assert "results" in r or "referencers" in r, r


def test_referencers_with_filter(mcp, some_assets):
    _, mat = some_assets
    r = mcp.call("get_asset_refs",
                 assetPath=mat,
                 direction="referencers",
                 nameFilter="MI_")
    # No crash / graceful empty is OK
    assert isinstance(r, dict)
