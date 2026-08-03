# Copyright byteyang. All Rights Reserved.
"""阶段七：资产引用 — dependencies / referencers / 继承 children·ancestors。"""

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


@pytest.fixture(scope="module")
def inheritance_chain(test_ns, mcp):
    """Parent → Child → GrandChild 蓝图链，用于继承方向断言。"""
    parent = f"{test_ns}/BP_RefParent"
    child = f"{test_ns}/BP_RefChild"
    grand = f"{test_ns}/BP_RefGrand"
    mcp.call("create_blueprint", assetPath=parent, parentClass="Actor")
    mcp.call("save_asset", assetPaths=[parent])
    parent_class = f"{parent}.BP_RefParent_C"
    mcp.call("create_blueprint", assetPath=child, parentClass=parent_class)
    mcp.call("save_asset", assetPaths=[child])
    child_class = f"{child}.BP_RefChild_C"
    mcp.call("create_blueprint", assetPath=grand, parentClass=child_class)
    mcp.call("save_asset", assetPaths=[grand])
    return parent, child, grand


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


def test_children_direct(mcp, inheritance_chain):
    parent, child, grand = inheritance_chain
    r = mcp.call("get_asset_refs", assetPath=parent, direction="children")
    entry = (r.get("results") or [r])[0]
    paths = {item.get("path") for item in entry.get("refs") or []}
    assert child in paths, r
    assert grand not in paths, r


def test_descendants(mcp, inheritance_chain):
    parent, child, grand = inheritance_chain
    r = mcp.call("get_asset_refs", assetPath=parent, direction="descendants")
    entry = (r.get("results") or [r])[0]
    paths = {item.get("path") for item in entry.get("refs") or []}
    assert child in paths and grand in paths, r
    by_path = {item["path"]: item for item in entry.get("refs") or []}
    assert by_path[child].get("depth") == 1
    assert by_path[grand].get("depth") == 2


def test_parent_and_ancestors(mcp, inheritance_chain):
    parent, child, grand = inheritance_chain
    r = mcp.call("get_asset_refs", assetPath=grand, direction="parent")
    entry = (r.get("results") or [r])[0]
    paths = [item.get("path") for item in entry.get("refs") or []]
    assert paths and paths[0] == child, r

    r2 = mcp.call("get_asset_refs", assetPath=grand, direction="ancestors")
    entry2 = (r2.get("results") or [r2])[0]
    paths2 = [item.get("path") for item in entry2.get("refs") or []]
    assert child in paths2 and parent in paths2, r2


def test_asset_type_filter(mcp, inheritance_chain):
    parent, _, _ = inheritance_chain
    r = mcp.call(
        "get_asset_refs",
        assetPath=parent,
        direction="descendants",
        assetTypeFilter="Blueprint",
    )
    entry = (r.get("results") or [r])[0]
    for item in entry.get("refs") or []:
        assert "Blueprint" in (item.get("assetType") or ""), item
