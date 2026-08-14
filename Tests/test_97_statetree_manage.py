# Copyright byteyang. All Rights Reserved.
"""阶段九七：manage_asset_state_tree — StateTree 结构编辑（UE5.5+）。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.5")]


@pytest.fixture(scope="module")
def st_path(test_ns, mcp):
    path = f"{test_ns}/ST_Created"
    if is_capability_available(mcp, "create_asset_state_tree"):
        r = mcp.call_capability("create_asset_state_tree", assetPath=path)
        entry = cap_first(r)
        if not entry.get("error") or "already exists" in str(entry.get("error", "")):
            return path
    r = mcp.call_capability(
        "search_asset",
        query="StateTree",
        assetType="StateTree",
        pathFilter="/Game/",
        limit=1,
    )
    assets = r.get("results") or r.get("assets") or []
    if not assets:
        pytest.skip("无法创建且项目中无 StateTree 资产")
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


def test_manage_state_tree_add_task_transition(st_path, mcp):
    add_task = mcp.call_capability(
        "manage_asset_state_tree",
        assetPath=st_path,
        operations=[{
            "action": "add_task",
            "stateName": "NxTestState_Renamed",
            "nodeType": "StateTreeTask_Delay",
        }],
    )
    te = cap_first(add_task)
    assert isinstance(te, dict), add_task

    mcp.call_capability(
        "manage_asset_state_tree",
        assetPath=st_path,
        operations=[{"action": "add_state", "stateName": "NxTransSrc"}],
    )
    mcp.call_capability(
        "manage_asset_state_tree",
        assetPath=st_path,
        operations=[{"action": "add_state", "stateName": "NxTransDst"}],
    )
    r = mcp.call_capability(
        "manage_asset_state_tree",
        assetPath=st_path,
        operations=[{
            "action": "add_transition",
            "stateName": "NxTransSrc",
            "targetState": "NxTransDst",
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
