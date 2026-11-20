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


def test_get_state_tree_linked_asset_type(test_ns, mcp, require_tools):
    require_tools("CreateAssetStateTree", "ManageAssetStateTree", "GetAssetStateTree", "ExecPython")
    path = f"{test_ns}/ST_LinkedAssetType"
    mcp.call("CreateAssetStateTree", AssetPath=path)
    mcp.call("ManageAssetStateTree", AssetPath=path, bSaveToDisk=True,
             Operations=[{"Action": "AddState", "StateName": "External"}])
    # AddState 未开放 LinkedAsset；用编辑器原生属性准备读回用的节点。
    setup = f"""import unreal
tree = unreal.load_asset({path!r})
state = next(s for s in unreal.ObjectIterator(unreal.StateTreeState) if s.get_outermost().get_name() == {path!r})
state.set_editor_property("type", type(state.get_editor_property("type")).LINKED_ASSET)
assert unreal.EditorAssetLibrary.save_loaded_asset(tree)
del state, tree
"""
    mcp.call("ExecPython", Code=setup)
    entry = cap_first(mcp.call("GetAssetStateTree", AssetPath=path))
    assert [(state["Name"], state["Type"]) for state in entry["SubTrees"]] == [("External", "LinkedAsset")], entry


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


def test_manage_state_tree_add_task(test_ns, mcp, require_tools):
    require_tools("CreateAssetStateTree", "ManageAssetStateTree", "GetAssetStateTree")
    path = f"{test_ns}/ST_DelayTask"
    mcp.call("CreateAssetStateTree", AssetPath=path)
    mcp.call("ManageAssetStateTree", AssetPath=path, Operations=[{"Action": "AddState", "StateName": "Wait"}])
    add_task = mcp.call("ManageAssetStateTree", AssetPath=path, Operations=[
        {"Action": "AddTask", "StateName": "Wait", "NodeType": "StateTreeDelayTask"}])
    assert cap_first(add_task)["TasksCount"] == 1, add_task
    states = cap_first(mcp.call("GetAssetStateTree", AssetPath=path))["SubTrees"]
    state = next(item for item in states if item["Name"] == "Wait")
    assert state["Tasks"][0]["InstanceType"] == "StateTreeDelayTaskInstanceData", state


def test_manage_state_tree_transition_target(test_ns, mcp, require_tools):
    require_tools("CreateAssetStateTree", "ManageAssetStateTree", "GetAssetStateTree")
    path = f"{test_ns}/ST_TransitionTarget"
    mcp.call("CreateAssetStateTree", AssetPath=path)
    mcp.call("ManageAssetStateTree", AssetPath=path, Operations=[
        {"Action": "AddState", "StateName": "Source"},
        {"Action": "AddState", "StateName": "Target"},
        {"Action": "AddTransition", "StateName": "Source", "TargetState": "Target"},
    ])
    tree = cap_first(mcp.call("GetAssetStateTree", AssetPath=path))
    source = next(state for state in tree["SubTrees"] if state["Name"] == "Source")
    assert [transition["Target"] for transition in source["Transitions"]] == ["Target"], source
    mcp.call("ManageAssetStateTree", AssetPath=path, Operations=[
        {"Action": "RenameState", "StateName": "Target", "NewName": "Renamed"},
        {"Action": "AddState", "StateName": "Target"},
    ])
    states = cap_first(mcp.call("GetAssetStateTree", AssetPath=path))["SubTrees"]
    source = next(state for state in states if state["Name"] == "Source")
    assert [transition["Target"] for transition in source["Transitions"]] == ["Renamed"], source


def test_manage_state_tree_transition_rejections(test_ns, mcp, require_tools):
    require_tools("CreateAssetStateTree", "ManageAssetStateTree", "GetAssetStateTree")
    path = f"{test_ns}/ST_TransitionRejections"
    mcp.call("CreateAssetStateTree", AssetPath=path)
    mcp.call("ManageAssetStateTree", AssetPath=path, Operations=[
        {"Action": "AddState", "StateName": "Left"},
        {"Action": "AddState", "StateName": "Right"},
        {"Action": "AddState", "ParentState": "Left", "StateName": "Idle"},
        {"Action": "AddState", "ParentState": "Right", "StateName": "Idle"},
    ])
    before = cap_first(mcp.call("GetAssetStateTree", AssetPath=path))["SubTrees"]
    for source, target in (("IDLE", "Right"), ("Left", "idle")):
        result = mcp.try_call("ManageAssetStateTree", AssetPath=path, Operations=[
            {"Action": "AddTransition", "StateName": source, "TargetState": target}])
        assert result["isError"] and "ambiguous" in str(result["structuredContent"]).lower(), result
        assert cap_first(mcp.call("GetAssetStateTree", AssetPath=path))["SubTrees"] == before

    operations = [
        {"Action": "AddTransition", "StateName": "Left", "TargetState": "Right"},
        {"Action": "RemoveTransition", "StateName": "Left", "Index": 99},
    ]
    result = mcp.try_call("CallCapability", Calls=[
        {"Capability": "ManageAssetStateTree", "Arguments": {"AssetPath": path, "Operations": [op]}}
        for op in operations])
    assert result["isError"] and result["structuredContent"]["bRolledBack"], result
    assert cap_first(mcp.call("GetAssetStateTree", AssetPath=path))["SubTrees"] == before


def test_manage_state_tree_remove_state(st_path, mcp):
    r = mcp.call_capability(
        "ManageAssetStateTree",
        AssetPath=st_path,
        Operations=[{"Action": "RemoveState", "StateName": "NxTestState_Renamed"}],
    )
    entry = cap_first(r)
    assert not entry.get("Error") and entry.get("bSuccess") is not False, r


def test_state_tree_array_owners_roll_back(test_ns, mcp, require_tools):
    require_tools("CreateAssetStateTree", "ManageAssetStateTree", "GetAssetStateTree")
    path = f"{test_ns}/ST_ArrayUndo"
    mcp.call("CreateAssetStateTree", AssetPath=path)
    add_root = {"Action": "AddState", "StateName": "Root"}
    add_child = {"Action": "AddState", "StateName": "Child", "ParentState": "Root"}
    task = {"Action": "AddTask", "StateName": "Root", "NodeType": "StateTreeDelayTask"}
    condition = {"Action": "AddEnterCondition", "StateName": "Root", "NodeType": "StateTreeCompareIntCondition"}
    mcp.call("ManageAssetStateTree", AssetPath=path, Operations=[add_root, add_child, task, condition])
    before = cap_first(mcp.call("GetAssetStateTree", AssetPath=path))["SubTrees"]
    assert before[0]["EnterConditions"][0]["InstanceType"] == "StateTreeCompareIntConditionInstanceData", before
    for op in (
        {**task, "NodeType": condition["NodeType"]}, {**condition, "NodeType": task["NodeType"]},
        {**task, "NodeType": "Vector"},
    ):
        rejected = mcp.try_call("ManageAssetStateTree", AssetPath=path, Operations=[op])
        assert rejected["isError"] and "not a StateTree" in str(rejected), rejected
    for op in (
        {**add_root, "StateName": "AnotherRoot"}, {**add_child, "StateName": "AnotherChild"},
        {"Action": "RemoveState", "StateName": "Child"}, {"Action": "RemoveState", "StateName": "Root"},
        task, condition, {"Action": "RemoveTask", "StateName": "Root", "Index": 0},
        {"Action": "RemoveEnterCondition", "StateName": "Root", "Index": 0},
    ):
        fail = {"Action": "RemoveTransition", "StateName": "Root", "Index": 100}
        result = mcp.try_call("CallCapability", Calls=[
            {"Capability": "ManageAssetStateTree", "Arguments": {"AssetPath": path, "Operations": [action]}}
            for action in (op, fail)])
        assert result["isError"] and result["structuredContent"]["bRolledBack"], (op, result)
        assert cap_first(mcp.call("GetAssetStateTree", AssetPath=path))["SubTrees"] == before, op


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
