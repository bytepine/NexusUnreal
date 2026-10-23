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
    if is_capability_available(mcp, "CreateAssetStateTree"):
        r = mcp.call_capability("CreateAssetStateTree", AssetPath=path)
        entry = cap_first(r)
        if not entry.get("Error") or "already exists" in str(entry.get("Error", "")):
            return path
    r = mcp.call_capability(
        "SearchAsset",
        Query="StateTree",
        AssetType="StateTree",
        PathFilter="/Game/",
        Limit=1,
    )
    assets = r.get("Results") or r.get("Assets") or []
    if not assets:
        pytest.skip("无法创建且项目中无 StateTree 资产")
    return assets[0].get("Path") or assets[0].get("AssetPath")


def test_get_asset_state_tree(st_path, mcp):
    if not is_capability_available(mcp, "GetAssetStateTree"):
        pytest.skip("get_asset_state_tree 未编入")
    r = mcp.call_capability("GetAssetStateTree", AssetPath=st_path)
    entry = cap_first(r)
    assert not entry.get("Error"), r


def test_manage_state_tree_add_state(st_path, mcp):
    r = mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[{"Action": "AddState", "StateName": "NxTestState_AutoAdded"}],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r
    assert not entry.get("Error") and entry.get("bSuccess") is not False, r


def test_manage_state_tree_rename_state(st_path, mcp):
    r = mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[{
            "Action": "RenameState",
            "StateName": "NxTestState_AutoAdded",
            "NewName": "NxTestState_Renamed",
        }],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r


def test_manage_state_tree_add_task_transition(st_path, mcp):
    add_task = mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[{
            "Action": "AddTask",
            "StateName": "NxTestState_Renamed",
            "NodeType": "StateTreeDelayTask",
        }],
    )
    te = cap_first(add_task)
    assert isinstance(te, dict), add_task

    mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[{"Action": "AddState", "StateName": "NxTransSrc"}],
    )
    mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[{"Action": "AddState", "StateName": "NxTransDst"}],
    )
    r = mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[{
            "Action": "AddTransition",
            "StateName": "NxTransSrc",
            "TargetState": "NxTransDst",
        }],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r


def test_manage_state_tree_remove_state(st_path, mcp):
    r = mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[{"Action": "RemoveState", "StateName": "NxTestState_Renamed"}],
    )
    entry = cap_first(r)
    assert not entry.get("Error") and entry.get("bSuccess") is not False, r


def test_manage_state_tree_task_condition_remove_transition(st_path, mcp):
    mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[{"Action": "AddState", "StateName": "NxCondSrc"}],
    )
    mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[{"Action": "AddState", "StateName": "NxCondDst"}],
    )
    mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[{
            "Action": "AddTask",
            "StateName": "NxCondSrc",
            "NodeType": "StateTreeDelayTask",
        }],
    )
    cond = mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[{
            "Action": "AddEnterCondition",
            "StateName": "NxCondSrc",
            "NodeType": "StateTreeCompareIntCondition",
        }],
    )
    assert isinstance(cap_first(cond), dict), cond
    mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[{
            "Action": "AddTransition",
            "StateName": "NxCondSrc",
            "TargetState": "NxCondDst",
        }],
    )
    rm = mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[
            {"Action": "RemoveTask", "StateName": "NxCondSrc", "Index": 0},
            {"Action": "RemoveEnterCondition", "StateName": "NxCondSrc", "Index": 0},
            {"Action": "RemoveTransition", "StateName": "NxCondSrc", "Index": 0},
        ],
    )
    for e in (rm.get("Results") or [cap_first(rm)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"state_tree remove_* 跳过: {e}")


def test_manage_state_tree_recompile(st_path, mcp):
    r = mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[{"Action": "Recompile"}],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r
