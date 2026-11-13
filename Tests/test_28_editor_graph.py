# Copyright byteyang. All Rights Reserved.
"""原生图编辑器查询、导航与选择，不使用 Slate 输入接口。"""
import time
import uuid

import pytest

from _framework.assertions import merge_with_defaults
from _framework.asset_helpers import resolve_skeleton
from _framework.mcp_client import cap_first


def _items(payload, name):
    return merge_with_defaults(payload.get(name, []), payload.get(f"{name}_defaults", {}))


def _graph(mcp, path, graph_name, **arguments):
    return cap_first(mcp.call("GetEditorGraph", AssetPath=path, GraphName=graph_name, **arguments))


def _control(mcp, path, graph_name, action, **arguments):
    result = cap_first(mcp.call("ControlEditorGraph", AssetPath=path, GraphName=graph_name,
                                Action=action, **arguments))
    assert result["bRequestAccepted"], result
    return result


def _graph_name(mcp, path, short_name=None):
    inventory = cap_first(mcp.call("GetEditorGraph", AssetPath=path))
    graphs = _items(inventory, "Graphs")
    if short_name:
        graphs = [item for item in graphs if item["GraphName"].split(".")[-1] == short_name]
    assert len(graphs) == 1, inventory
    return graphs[0]["GraphName"]


def _discover(mcp, path, asset_type):
    found = mcp.call("SearchAsset", AssetType=asset_type, PathFilter=path.rsplit("/", 1)[0])
    assert any(item["Path"].split(".")[0] == path for item in _items(found, "Assets")), found


def _blueprint(mcp, path):
    mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="Actor")
    mcp.call("ManageAssetBlueprint", AssetPath=path, Operations=[
        {"Action": "AddVariable", "VariableName": "GraphProbeValue", "VariableType": "float"},
        {"Action": "AddFunction", "FunctionName": "GraphProbe"},
    ])
    for node_class, x, y in (("K2Node_VariableGet", 64, 96), ("K2Node_VariableSet", 512, 160)):
        mcp.call("ManageAssetBlueprint", AssetPath=path, Operations=[{
            "Action": "AddNode", "GraphName": "GraphProbe", "NodeClass": node_class,
            "VariableName": "GraphProbeValue", "PosX": x, "PosY": y,
        }])
    _discover(mcp, path, "Blueprint")
    return _graph_name(mcp, path, "GraphProbe")


def _layout(payload):
    fields = ("NodeId", "NodeClass", "PosX", "PosY", "Width", "Height", "Comment")
    return sorted(tuple(str(node.get(field, "")) for field in fields) for node in _items(payload, "Nodes"))


@pytest.mark.parametrize("name", ["GetEditorGraph", "ControlEditorGraph"])
def test_editor_graph_discovery(mcp, require_tools, name):
    require_tools(name)
    found = mcp.call("SearchCapabilities", CapabilityName=name, Query="")
    assert found["Capability"]["name"] == name and found["Capability"]["Parameters"], found


def test_editor_graph_read_layout_and_filter(mcp, require_tools, test_ns):
    require_tools("GetEditorGraph", "CreateAssetBlueprint", "ManageAssetBlueprint")
    path = f"{test_ns}/BP_EditorGraphRead"
    graph_name = _blueprint(mcp, path)
    snapshot = _graph(mcp, path, graph_name)
    nodes = _items(snapshot, "Nodes")
    assert not snapshot["bIsOpen"] and not snapshot["bViewAvailable"], snapshot
    assert "ViewLocation" not in snapshot and "Zoom" not in snapshot and "SelectedNodeIds" not in snapshot, snapshot
    assert {(64, 96), (512, 160)} <= {(node["PosX"], node["PosY"]) for node in nodes}, snapshot
    assert all({"Width", "Height", "Comment"} <= node.keys() for node in nodes), snapshot
    node_id = next(node["NodeId"] for node in nodes if node["PosX"] == 64)
    exact = _graph(mcp, path, graph_name, NodeId=node_id)
    assert [node["NodeId"] for node in _items(exact, "Nodes")] == [node_id], exact
    page = _graph(mcp, path, graph_name, Offset=1, Limit=1)
    assert len(_items(page, "Nodes")) == 1, page
    past_end = _graph(mcp, path, graph_name, NodeId=node_id, Offset=100, Limit=1)
    assert _items(past_end, "Nodes") == [] and not past_end["bViewAvailable"], past_end
    for arguments in ({"GraphName": "MissingGraph"},
                      {"GraphName": graph_name, "NodeId": str(uuid.uuid4())}):
        rejected = mcp.try_call("GetEditorGraph", AssetPath=path, **arguments)
        assert rejected.get("isError"), rejected
    assert _layout(_graph(mcp, path, graph_name)) == _layout(snapshot)


@pytest.mark.requires_gui
def test_editor_graph_native_controls(mcp, require_tools, test_ns):
    require_tools("GetEditorGraph", "ControlEditorGraph", "CreateAssetBlueprint", "ManageAssetBlueprint",
                  "CompileBlueprint", "SaveAsset")
    path = f"{test_ns}/BP_EditorGraphControl"
    graph_name = _blueprint(mcp, path)
    mcp.call("CompileBlueprint", AssetPath=path)
    mcp.call("SaveAsset", AssetPath=path)
    opened_asset = cap_first(mcp.call("ControlEditorGraph", AssetPath=path, Action="Open"))
    assert opened_asset["bRequestAccepted"] and not opened_asset["bViewDeferred"], opened_asset
    available_graphs = _items(opened_asset, "Graphs")
    assert len(available_graphs) >= 2 and graph_name in {item["GraphName"] for item in available_graphs}, opened_asset
    opened = _control(mcp, path, graph_name, "Open")
    assert opened["bIsOpen"], opened
    baseline = _graph(mcp, path, graph_name)
    nodes = _items(baseline, "Nodes")
    assert not baseline["bDirty"], baseline
    assert baseline["bViewAvailable"] and all("bSelected" in node for node in nodes), baseline
    first = next(node["NodeId"] for node in nodes if node["PosX"] == 64)
    second = next(node["NodeId"] for node in nodes if node["PosX"] == 512)
    _control(mcp, path, graph_name, "SelectNodes", NodeIds=[first])
    assert set(_graph(mcp, path, graph_name)["SelectedNodeIds"]) == {first}
    rejected = mcp.try_call("ControlEditorGraph", AssetPath=path, GraphName=graph_name,
                           Action="SelectNodes", NodeIds=[second, str(uuid.uuid4())])
    assert rejected.get("isError"), rejected
    assert set(_graph(mcp, path, graph_name)["SelectedNodeIds"]) == {first}
    _control(mcp, path, graph_name, "SelectNodes", NodeIds=[second], SelectionMode="Add")
    assert set(_graph(mcp, path, graph_name)["SelectedNodeIds"]) == {first, second}
    _control(mcp, path, graph_name, "SelectNodes", NodeIds=[first], SelectionMode="Remove")
    assert set(_graph(mcp, path, graph_name)["SelectedNodeIds"]) == {second}
    _control(mcp, path, graph_name, "ClearSelection")
    assert _graph(mcp, path, graph_name)["SelectedNodeIds"] == []
    for arguments in ({"Zoom": 0}, {"Zoom": -1}, {"ViewLocation": {"X": 123}}):
        rejected = mcp.try_call("ControlEditorGraph", AssetPath=path, GraphName=graph_name,
                               Action="SetView", **arguments)
        assert rejected.get("isError"), rejected
    _control(mcp, path, graph_name, "SetView", ViewLocation={"X": 123, "Y": -87}, Zoom=1)
    deadline = time.monotonic() + 5
    while True:
        view = _graph(mcp, path, graph_name)
        if (view.get("bViewAvailable") and abs(view["ViewLocation"]["X"] - 123) < 1
                and abs(view["ViewLocation"]["Y"] + 87) < 1 and abs(view["Zoom"] - 1) < .01):
            break
        assert time.monotonic() < deadline, view
        time.sleep(.05)
    focused = _control(mcp, path, graph_name, "FocusNode", NodeId=first)
    assert focused["bViewDeferred"], focused
    assert first in _graph(mcp, path, graph_name)["SelectedNodeIds"]
    framed = _control(mcp, path, graph_name, "ZoomToFit", bOnlySelection=True)
    assert framed["bViewDeferred"], framed
    after = _graph(mcp, path, graph_name)
    assert after["bViewAvailable"] and after["Zoom"] > 0, after
    assert not after["bDirty"] and _layout(after) == _layout(baseline)


@pytest.mark.requires_gui
@pytest.mark.parametrize("kind,asset_type", [("UserWidget", "Widget"), ("AnimBlueprint", "AnimBlueprint")])
def test_editor_graph_native_blueprint_domain_views(mcp, require_tools, test_ns, kind, asset_type):
    creator = f"CreateAsset{kind}"
    require_tools("GetEditorGraph", "ControlEditorGraph", "ManageAssetBlueprint", "CompileBlueprint",
                  "SaveAsset", creator)
    path = f"{test_ns}/{kind}_EditorGraphView"
    parameters = {"SkeletonPath": resolve_skeleton(mcp)} if kind == "AnimBlueprint" else {}
    mcp.call(creator, AssetPath=path, **parameters)
    _discover(mcp, path, asset_type)
    graph_name = _graph_name(mcp, path, "EventGraph")
    mcp.call("ManageAssetBlueprint", AssetPath=path, Operations=[{
        "Action": "AddNode", "GraphName": "EventGraph", "NodeClass": "K2Node_CustomEvent",
        "CustomEventName": "GraphViewProbe", "PosX": 64, "PosY": 96,
    }])
    mcp.call("CompileBlueprint", AssetPath=path)
    mcp.call("SaveAsset", AssetPath=path)
    opened_asset = cap_first(mcp.call("ControlEditorGraph", AssetPath=path, Action="Open"))
    assert opened_asset["bRequestAccepted"], opened_asset
    assert graph_name in {item["GraphName"] for item in _items(opened_asset, "Graphs")}, opened_asset
    _control(mcp, path, graph_name, "Open")
    baseline = _graph(mcp, path, graph_name)
    assert baseline["bIsOpen"] and baseline["bViewAvailable"] and not baseline["bDirty"], baseline
    node_id = next(node["NodeId"] for node in _items(baseline, "Nodes")
                   if node["PosX"] == 64 and node["PosY"] == 96)
    _control(mcp, path, graph_name, "SelectNodes", NodeIds=[node_id])
    assert _graph(mcp, path, graph_name)["SelectedNodeIds"] == [node_id]
    _control(mcp, path, graph_name, "ClearSelection")
    assert _graph(mcp, path, graph_name)["SelectedNodeIds"] == []
    _control(mcp, path, graph_name, "SetView", ViewLocation={"X": 80, "Y": -40}, Zoom=1)
    after = _graph(mcp, path, graph_name)
    assert after["bViewAvailable"] and abs(after["Zoom"] - 1) < .01, after
    assert abs(after["ViewLocation"]["X"] - 80) < 1 and abs(after["ViewLocation"]["Y"] + 40) < 1, after
    assert not after["bDirty"] and _layout(after) == _layout(baseline)


@pytest.mark.requires_gui
@pytest.mark.parametrize("kind", ["Material", "MaterialFunction", "BehaviorTree", "PCGGraph"])
def test_editor_graph_native_domain_views(mcp, require_tools, test_ns, kind):
    creator = f"CreateAsset{kind}"
    require_tools("GetEditorGraph", "ControlEditorGraph", "ControlEditorAssetEditor", creator)
    path = f"{test_ns}/{kind}_EditorGraphView"
    mcp.call(creator, AssetPath=path)
    _discover(mcp, path, kind)
    asset_editor = cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=path, Action="Open"))
    assert asset_editor["bIsOpen"], asset_editor
    graph_name = _graph_name(mcp, path)
    inventory = cap_first(mcp.call("GetEditorGraph", AssetPath=path))
    if kind in {"Material", "MaterialFunction"}:
        assert all(item["GraphPath"].startswith("/Engine/Transient") for item in _items(inventory, "Graphs")), inventory
    _control(mcp, path, graph_name, "Open")
    baseline = _graph(mcp, path, graph_name)
    assert baseline["bIsOpen"] and baseline["bViewAvailable"], baseline
    _control(mcp, path, graph_name, "SetView", ViewLocation={"X": 80, "Y": -40}, Zoom=1)
    _control(mcp, path, graph_name, "ClearSelection")
    nodes = _items(baseline, "Nodes")
    if nodes:
        _control(mcp, path, graph_name, "SelectNodes", NodeIds=[nodes[0]["NodeId"]])
        assert nodes[0]["NodeId"] in _graph(mcp, path, graph_name)["SelectedNodeIds"]
    _control(mcp, path, graph_name, "ZoomToFit")
    after = _graph(mcp, path, graph_name)
    assert after["bDirty"] == baseline["bDirty"] and _layout(after) == _layout(baseline)
