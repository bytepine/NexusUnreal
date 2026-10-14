# Copyright byteyang. All Rights Reserved.
"""阶段七：资产引用 — dependencies / referencers / 继承 children·ancestors。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l1_readonly


@pytest.fixture(scope="module")
def some_assets(test_ns, mcp):
    """Create a minimal BP + material to have deterministic ref graph."""
    bp = f"{test_ns}/BP_RefTest"
    mat = f"{test_ns}/M_RefTest"
    mcp.call("CreateAssetBlueprint", AssetPath=bp, ParentClass="Actor")
    mcp.call("CreateAssetMaterial", AssetPath=mat)
    return bp, mat


@pytest.fixture(scope="module")
def inheritance_chain(test_ns, mcp):
    """Parent → Child → GrandChild 蓝图链，用于继承方向断言。"""
    parent = f"{test_ns}/BP_RefParent"
    child = f"{test_ns}/BP_RefChild"
    grand = f"{test_ns}/BP_RefGrand"
    mcp.call("CreateAssetBlueprint", AssetPath=parent, ParentClass="Actor")
    mcp.call("SaveAsset", AssetPath=parent)
    parent_class = f"{parent}.BP_RefParent_C"
    mcp.call("CreateAssetBlueprint", AssetPath=child, ParentClass=parent_class)
    mcp.call("SaveAsset", AssetPath=child)
    child_class = f"{child}.BP_RefChild_C"
    mcp.call("CreateAssetBlueprint", AssetPath=grand, ParentClass=child_class)
    mcp.call("SaveAsset", AssetPath=grand)
    return parent, child, grand


def test_dependencies_batch(mcp, some_assets):
    bp, mat = some_assets
    # get_asset_refs 已单数化为 assetPath，分别查询每个资产
    for asset in (bp, mat):
        r = mcp.call(
            "GetAssetRefs",
            AssetPath=asset,
            Direction="Dependencies",
            bRecursive=True,
        )
        assert isinstance(r, dict), f"get_asset_refs {asset}: {r!r}"


def test_referencers(mcp, some_assets):
    bp, _ = some_assets
    r = mcp.call("GetAssetRefs", AssetPath=bp, Direction="Referencers")
    # 单条提升后顶层即含 refs/direction；兼容旧 results[] / referencers 键
    entry = cap_first(r)
    assert (
        "Results" in r
        or "Referencers" in r
        or "Refs" in entry
        or entry.get("Direction") == "Referencers"
    ), r


def test_referencers_with_filter(mcp, some_assets):
    _, mat = some_assets
    r = mcp.call("GetAssetRefs",
                 AssetPath=mat,
                 Direction="Referencers",
                 NameFilter="MI_")
    # No crash / graceful empty is OK
    assert isinstance(r, dict)


def test_children_direct(mcp, inheritance_chain):
    parent, child, grand = inheritance_chain
    r = mcp.call("GetAssetRefs", AssetPath=parent, Direction="Children")
    entry = cap_first(r)
    paths = {item.get("Path") for item in entry.get("Refs") or []}
    assert child in paths, r
    assert grand not in paths, r


def test_descendants(mcp, inheritance_chain):
    parent, child, grand = inheritance_chain
    r = mcp.call("GetAssetRefs", AssetPath=parent, Direction="Descendants")
    entry = cap_first(r)
    paths = {item.get("Path") for item in entry.get("Refs") or []}
    assert child in paths and grand in paths, r
    by_path = {item["Path"]: item for item in entry.get("Refs") or []}
    assert by_path[child].get("Depth") == 1
    assert by_path[grand].get("Depth") == 2


def test_parent_and_ancestors(mcp, inheritance_chain):
    parent, child, grand = inheritance_chain
    r = mcp.call("GetAssetRefs", AssetPath=grand, Direction="Parent")
    entry = cap_first(r)
    paths = [item.get("Path") for item in entry.get("Refs") or []]
    assert paths and paths[0] == child, r

    r2 = mcp.call("GetAssetRefs", AssetPath=grand, Direction="Ancestors")
    entry2 = cap_first(r2)
    paths2 = [item.get("Path") for item in entry2.get("Refs") or []]
    assert child in paths2 and parent in paths2, r2


def test_asset_type_filter(mcp, inheritance_chain):
    parent, _, _ = inheritance_chain
    r = mcp.call(
        "GetAssetRefs",
        AssetPath=parent,
        Direction="Descendants",
        AssetTypeFilter="Blueprint",
    )
    entry = cap_first(r)
    for item in entry.get("Refs") or []:
        assert "Blueprint" in (item.get("AssetType") or ""), item
