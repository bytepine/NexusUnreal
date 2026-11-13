# Copyright byteyang. All Rights Reserved.
"""原生图编辑器查询、导航与选择，不使用 Slate 输入接口。"""
import time
import uuid

import pytest

from _framework.assertions import merge_with_defaults
from _framework.asset_helpers import resolve_skeleton
from _framework.mcp_client import cap_first
from test_15_editor_operations import operation_result


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


@pytest.mark.requires_gui
@pytest.mark.skipif_ue_below("5.8")
def test_editor_graph_pcg_multi_document_views(mcp, require_tools):
    require_tools("CreateAssetPCGGraph", "GetEditorGraph", "ControlEditorGraph", "SearchAsset",
                  "ControlEditorAutomation", "GetEditorOperation", "ControlEditorAssetEditor")
    discovery = dict(AssetType="PCGGraph", PathFilter="/Game/_McpTest/", NameFilter="PCG_DocumentFixture")
    previous = {item["Path"] for item in _items(mcp.call("SearchAsset", **discovery), "Assets")}
    operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Discover"))
    fixture = "NexusLink.EditorGraph.PCGMultiDocumentFixture"
    result = operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Run", TestNames=[fixture]))
    assert len(result["Tests"]) == 1 and result["Tests"][0]["Outcome"] == "Passed", result
    found = [item for item in _items(mcp.call("SearchAsset", **discovery), "Assets") if item["Path"] not in previous]
    assert len(found) == 1, found
    path = found[0]["Path"]
    try:
        inventory = cap_first(mcp.call("GetEditorGraph", AssetPath=path))
        graphs = _items(inventory, "Graphs")
        assert len(graphs) == 3, inventory
        first = next(item["GraphName"] for item in graphs if item["GraphName"].startswith("GraphA."))
        second = next(item["GraphName"] for item in graphs if item["GraphName"].startswith("GraphB."))
        root = next(item["GraphName"] for item in graphs if item["GraphName"] not in {first, second})
        baselines = {name: _graph(mcp, path, name) for name in (root, first, second)}
        assert all(not snapshot["bDirty"] for snapshot in baselines.values()), baselines
        probes = {}
        for name, snapshot in baselines.items():
            nodes = [node for node in _items(snapshot, "Nodes") if node["NodeClass"].endswith(".PCGEditorGraphNode")]
            assert len(nodes) == 1, snapshot
            probes[name] = nodes[0]["NodeId"]
        assert len(set(probes.values())) == 3, probes
        assert baselines[root]["bIsOpen"] and baselines[root]["bViewAvailable"], baselines[root]
        for name in (first, second):
            assert not baselines[name]["bIsOpen"] and not baselines[name]["bViewAvailable"], baselines[name]
            assert "SelectedNodeIds" not in baselines[name], baselines[name]
            assert not _graph(mcp, path, name)["bIsOpen"], name

        def check_view(name, selected, x, y):
            snapshot = _graph(mcp, path, name)
            assert snapshot["bViewAvailable"] and set(snapshot["SelectedNodeIds"]) == set(selected), snapshot
            assert abs(snapshot["ViewLocation"]["X"] - x) < 1 and abs(snapshot["ViewLocation"]["Y"] - y) < 1, snapshot
            assert abs(snapshot["Zoom"] - 1) < .01, snapshot
            return snapshot

        root_id = probes[root]
        _control(mcp, path, root, "SelectNodes", NodeIds=[root_id])
        _control(mcp, path, root, "SetView", ViewLocation={"X": 31, "Y": 47}, Zoom=1)
        check_view(root, [root_id], 31, 47)
        for name, x, y in ((first, 101, -67), (second, 503, 211)):
            opened = _control(mcp, path, name, "Open")
            assert opened["bIsOpen"] and opened["bViewAvailable"], opened
            node_id = probes[name]
            _control(mcp, path, name, "SelectNodes", NodeIds=[node_id])
            _control(mcp, path, name, "SetView", ViewLocation={"X": x, "Y": y}, Zoom=1)
            check_view(name, [node_id], x, y)
            check_view(root, [root_id], 31, 47)
            if name == first:
                assert not _graph(mcp, path, second)["bIsOpen"], second

        first_id = probes[first]
        second_id = probes[second]
        check_view(first, [first_id], 101, -67)
        rejected = mcp.try_call("ControlEditorGraph", AssetPath=path, GraphName=first,
                               Action="SelectNodes", NodeIds=[first_id, second_id])
        assert rejected.get("isError"), rejected
        check_view(first, [first_id], 101, -67)
        check_view(second, [second_id], 503, 211)
        _control(mcp, path, first, "ClearSelection")
        check_view(first, [], 101, -67)
        check_view(second, [second_id], 503, 211)
        _control(mcp, path, first, "SelectNodes", NodeIds=[first_id])
        _control(mcp, path, first, "SetView", ViewLocation={"X": -199, "Y": 88}, Zoom=1)
        check_view(first, [first_id], -199, 88)
        check_view(second, [second_id], 503, 211)
        check_view(root, [root_id], 31, 47)
        for name in (root, first, second):
            after = _graph(mcp, path, name)
            assert _layout(after) == _layout(baselines[name]) and after["bDirty"] == baselines[name]["bDirty"], after
    finally:
        # 夹具仅驻内存且未落盘；关闭窗口后交会话清理，避免临时引用阻止删除而掩盖断言。
        mcp.call("ControlEditorAssetEditor", AssetPath=path, Action="Close")
