# Copyright byteyang. All Rights Reserved.
"""重设父类、只读导航与资产编辑器入口的 MCP 回归。"""
import pytest
from _framework.mcp_client import cap_first


@pytest.mark.parametrize("query,name", [
    ("reparent", "ManageAssetBlueprint"),
    ("navigation path", "GetNavigationPath"),
    ("asset editor", "ControlEditorAssetEditor"),
    ("FindAsset", "SearchAsset"),
])
def test_editor_gaps_intent_discovery(mcp, require_tools, query, name):
    require_tools(name)
    result = mcp.call("SearchCapabilities", Query=query)
    assert result["Capability"]["name"] == name, result
    assert result["Capability"]["Parameters"] and not result.get("bTruncated"), result


def test_editor_gaps_reparent(mcp, require_tools, test_ns):
    require_tools("CreateAssetBlueprint", "ManageAssetBlueprint", "GetAssetBlueprint")
    path = f"{test_ns}/BP_Reparent"
    mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="Actor")
    result = mcp.call("ManageAssetBlueprint", AssetPath=path, bCompile=True,
                      Operations=[{"Action": "Reparent", "ParentClass": "Character"}])
    assert cap_first(result)["bChanged"] and result["bCompiled"], result
    mcp.call("SearchAsset", AssetType="Blueprint", PathFilter=test_ns)
    readback = cap_first(mcp.call("GetAssetBlueprint", AssetPath=path, Sections=["Component"]))
    assert "Character" in readback["ParentClass"], readback
    rejected = mcp.try_call("ManageAssetBlueprint", AssetPath=path,
                           Operations=[{"Action": "Reparent", "ParentClass": "Actor"}])
    assert rejected.get("isError"), rejected


def test_editor_gaps_navigation_read_only(mcp, require_tools):
    require_tools("GetNavigationPath", "GetEditorContext")
    before = cap_first(mcp.call("GetEditorContext", Sections=["CurrentMap"]))
    result = cap_first(mcp.call("GetNavigationPath", World="Editor",
                               Start={"X": 0, "Y": 0, "Z": 0}, End={"X": 100, "Y": 0, "Z": 0}, MaxPoints=2))
    assert isinstance(result["bNavigationAvailable"], bool) and isinstance(result["bPathFound"], bool), result
    assert len(result["Points"]) <= 2 and result["WorldType"] == "Editor", result
    assert result["QueryResult"] in {"Unavailable", "Success", "Fail", "Error", "Invalid"}, result
    after = cap_first(mcp.call("GetEditorContext", Sections=["CurrentMap"]))
    assert after["AssetPath"] == before["AssetPath"] and after["MapName"] == before["MapName"]


def test_editor_gaps_asset_editor_validate(mcp, require_tools, test_ns):
    require_tools("ControlEditorAssetEditor", "CreateAssetBlueprint")
    path = f"{test_ns}/BP_EditorValidate"
    mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="Actor")
    status = cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=path, Action="Status"))
    preview = cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=path, bValidateOnly=True))
    assert preview["bValidateOnly"] and preview["bIsOpen"] == status["bIsOpen"], preview


def test_feedback_blueprint_metadata_batch(mcp, require_tools, test_ns):
    require_tools("CreateAssetBlueprint", "ManageAssetBlueprint", "GetAssetBlueprint")
    path = f"{test_ns}/BP_FeedbackMetadata"
    mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="Actor")
    mcp.call("ManageAssetBlueprint", AssetPath=path, Operations=[
        {"Action": "AddVariable", "VariableName": f"Value{i}", "VariableType": "bool"}
        for i in range(42)
    ] + [{"Action": "AddFunction", "FunctionName": "OnRep_Value0"}])
    mcp.call("ManageAssetBlueprint", AssetPath=path, bCompile=True, Operations=[
        {"Action": "SetVariableCategory", "VariableName": f"Value{i}", "Category": "NPC|对话"}
        for i in range(42)
    ] + [
        {"Action": "SetVariableMetadata", "VariableName": "Value0", "ToolTip": "对话占用状态"},
        {"Action": "SetVariableReplication", "VariableName": "Value0", "Replication": "RepNotify", "RepNotifyFunction": "OnRep_Value0"},
        {"Action": "SetFunctionCallInEditor", "FunctionName": "OnRep_Value0", "bCallInEditor": True},
    ])
    got = cap_first(mcp.call("GetAssetBlueprint", AssetPath=path, Sections=["Variable", "Function"]))
    variables = got["Variables"]
    assert len(variables) == 42 and all(v["Category"] == "NPC|对话" for v in variables), got
    value = next(v for v in variables if v["Name"] == "Value0")
    assert value["ToolTip"] == "对话占用状态" and value["Replication"] == "RepNotify", value
    assert value["RepNotifyFunction"] == "OnRep_Value0", value
    assert next(f for f in got["Functions"] if f["Name"] == "OnRep_Value0")["bCallInEditor"], got
    rejected = mcp.try_call("ManageAssetBlueprint", AssetPath=path, Operations=[
        {"Action": "SetVariableReplication", "VariableName": "Value0", "Replication": "RepNotify", "RepNotifyFunction": "Missing"},
    ])
    assert rejected.get("isError"), rejected
    mcp.call("ManageAssetBlueprint", AssetPath=path, bCompile=True, Operations=[
        {"Action": "SetVariableReplication", "VariableName": "Value0", "Replication": "Replicated"},
        {"Action": "SetVariableMetadata", "VariableName": "Value0", "ToolTip": ""},
        {"Action": "SetFunctionCallInEditor", "FunctionName": "OnRep_Value0", "bCallInEditor": False},
    ])
    got = cap_first(mcp.call("GetAssetBlueprint", AssetPath=path, Sections=["Variable", "Function"], NameFilter="Value0"))
    assert got["Variables"][0]["Replication"] == "Replicated" and got["Variables"][0]["ToolTip"] == "", got
    assert not got["Functions"][0]["bCallInEditor"], got


@pytest.mark.requires_gui
def test_editor_gaps_asset_editor_open(mcp, require_tools, test_ns):
    require_tools("ControlEditorAssetEditor", "CreateAssetBlueprint")
    path = f"{test_ns}/BP_EditorOpen"
    mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="Actor")
    opened = cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=path, Action="Open"))
    assert opened["bIsOpen"], opened
    focused = cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=path, Action="Focus"))
    assert focused["bWasOpen"] and focused["bIsOpen"], focused
