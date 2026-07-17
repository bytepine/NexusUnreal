# Copyright byteyang. All Rights Reserved.
"""阶段九七：manage_asset_state_tree — StateTree 结构编辑（UE5.5+）。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.5")]


@pytest.fixture(scope="module")
def st_path(test_ns, mcp):
    """假设项目中有一个现成的 StateTree，或用 search_asset 动态发现。"""
    r = mcp.call_capability(
        "search_asset",
        query="StateTree",
        assetType="StateTree",
        pathFilter="/Game/",
        limit=1,
    )
    assets = r.get("results") or []
    if not assets:
        pytest.skip("项目中无 StateTree 资产，跳过测试")
    return assets[0].get("path") or assets[0].get("assetPath")


def test_manage_state_tree_add_state(st_path, mcp):
    r = mcp.call_capability(
        "manage_asset_state_tree",
        assetPath=st_path,
        operations=[{"action": "add_state", "stateName": "NxTestState_AutoAdded"}],
    )
    entry = cap_first(r)
    assert not entry.get("error"), r
    assert not entry.get("error") and entry.get("success") is not False, r


def test_manage_state_tree_rename_state(st_path, mcp):
    r = mcp.call_capability(
        "manage_asset_state_tree",
        assetPath=st_path,
        operations=[{
            "action": "rename_state",
            "stateName": "NxTestState_AutoAdded",
            "newName": "NxTestState_Renamed",
        }],
    )
    entry = cap_first(r)
    assert not entry.get("error"), r


def test_manage_state_tree_remove_state(st_path, mcp):
    r = mcp.call_capability(
        "manage_asset_state_tree",
        assetPath=st_path,
        operations=[{"action": "remove_state", "stateName": "NxTestState_Renamed"}],
    )
    entry = cap_first(r)
    assert not entry.get("error") and entry.get("success") is not False, r


def test_manage_state_tree_recompile(st_path, mcp):
    r = mcp.call_capability(
        "manage_asset_state_tree",
        assetPath=st_path,
        operations=[{"action": "recompile"}],
    )
    entry = cap_first(r)
    assert not entry.get("error"), r
