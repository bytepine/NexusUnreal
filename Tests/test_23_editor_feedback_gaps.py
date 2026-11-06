# Copyright byteyang. All Rights Reserved.
"""重设父类、只读导航与资产编辑器入口的 MCP 回归。"""
import pytest
from _framework.mcp_client import cap_first


@pytest.mark.parametrize("query,name", [
    ("reparent", "ManageAssetBlueprint"),
    ("navigation path", "GetNavigationPath"),
    ("asset editor", "ControlEditorAssetEditor"),
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


@pytest.mark.requires_gui
def test_editor_gaps_asset_editor_open(mcp, require_tools, test_ns):
    require_tools("ControlEditorAssetEditor", "CreateAssetBlueprint")
    path = f"{test_ns}/BP_EditorOpen"
    mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="Actor")
    opened = cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=path, Action="Open"))
    assert opened["bIsOpen"], opened
    focused = cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=path, Action="Focus"))
    assert focused["bWasOpen"] and focused["bIsOpen"], focused
