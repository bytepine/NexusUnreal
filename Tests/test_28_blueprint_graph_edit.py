# Copyright byteyang. All Rights Reserved.
"""蓝图结构体引脚与选定节点复制：专用 MCP 操作，可在 headless 下运行。"""
import uuid
import re
from decimal import Decimal

import pytest

from _framework.asset_helpers import resolve_skeleton
from _framework.mcp_client import cap_first
from _framework.assertions import merge_with_defaults


def expand_graph_defaults(value):
    if isinstance(value, list):
        return [expand_graph_defaults(item) for item in value]
    if not isinstance(value, dict):
        return value
    expanded = dict(value)
    for field in ("Nodes", "Pins", "LinkedTo"):
        if field in expanded:
            expanded[field] = merge_with_defaults(expanded[field], expanded.get(f"{field}_defaults", {}))
        expanded.pop(f"{field}_defaults", None)
    return {key: expand_graph_defaults(item) for key, item in expanded.items()}


def edit(mcp, path, **operation):
    result = cap_first(mcp.call("ManageAssetBlueprint", AssetPath=path, Operations=[operation]))
    assert not result.get("Error"), result
    return expand_graph_defaults(result)


def graph_nodes(mcp, path, graph="EventGraph"):
    result = cap_first(mcp.call("GetAssetBlueprint", AssetPath=path, Sections=["graph"], GraphName=graph, Limit=500))
    return {node["NodeId"]: node for node in expand_graph_defaults(result)["Nodes"]}


def pin(node, name):
    return next(item for item in node["Pins"] if item["PinName"] == name)


def create_blueprint(mcp, require_tools, test_ns, name):
    require_tools("CreateAssetBlueprint", "ManageAssetBlueprint", "GetAssetBlueprint", "SearchAsset")
    path = f"{test_ns}/BP_{name}"
    mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="Actor")
    mcp.call("SearchAsset", AssetType="Blueprint", PathFilter=path.rsplit("/", 1)[0])
    return path


def add_variable_node(mcp, path, variable, setter=False, graph="EventGraph", **position):
    return edit(mcp, path, Action="AddNode", GraphName=graph,
                NodeClass="K2Node_VariableSet" if setter else "K2Node_VariableGet",
                VariableName=variable, **position)["NodeId"]


def assert_rejected_without_changes(mcp, path, operation, graph="EventGraph"):
    before = graph_nodes(mcp, path, graph)
    rejected = mcp.try_call("ManageAssetBlueprint", AssetPath=path, Operations=[operation])
    assert rejected.get("isError"), rejected
    after = graph_nodes(mcp, path, graph)
    assert after == before, (operation, before, after)
    return rejected


def assert_removal_rejected(mcp, path, graph, node_id, error, *, animation=False):
    before = graph_nodes(mcp, path, graph)
    assert not cap_first(mcp.call("GetEditorGraph", AssetPath=path))["bDirty"]
    calls = [("GetAssetEditPreview", {"Capability": "ManageAssetBlueprint"}),
             ("ManageAssetBlueprint", {"bVerifyStructure": True}), ("ManageAssetBlueprint", {})]
    if animation:
        calls.append(("ManageAssetAnimBlueprint", {}))
    for tool, options in calls:
        remove = {"Action": "RemoveNode", "GraphName": graph, "NodeId": node_id}
        rejected = mcp.try_call(tool, AssetPath=path, Operations=[remove], **options)
        assert rejected.get("isError") and error in str(rejected), rejected
        assert graph_nodes(mcp, path, graph) == before
        assert not cap_first(mcp.call("GetEditorGraph", AssetPath=path))["bDirty"]


def test_blueprint_remove_node_protects_function_entry(mcp, require_tools, test_ns):
    path = create_blueprint(mcp, require_tools, test_ns, "ProtectedEntry")
    require_tools("GetAssetEditPreview", "GetEditorGraph", "SaveAsset")
    graph = "RunSequence"
    edit(mcp, path, Action="AddFunction", FunctionName=graph)
    entry_id = next(node_id for node_id, node in graph_nodes(mcp, path, graph).items()
                    if node["NodeClass"] == "K2Node_FunctionEntry")
    sequence = edit(mcp, path, Action="AddNode", GraphName=graph, NodeClass="K2Node_ExecutionSequence")["NodeId"]
    edit(mcp, path, Action="Connect", GraphName=graph, SourceNodeId=entry_id, SourcePinName="then",
         TargetNodeId=sequence, TargetPinName="execute")
    mcp.call("SaveAsset", AssetPath=path)
    assert any(link["NodeId"] == sequence for link in pin(graph_nodes(mcp, path, graph)[entry_id], "then")["LinkedTo"])
    assert_removal_rejected(mcp, path, graph, entry_id, "cannot be deleted")

    overview = cap_first(mcp.call("GetAssetBlueprint", AssetPath=path, Sections=["GraphOverview"]))
    graph_path = next(g["GraphPath"] for g in overview["Graphs"] if g["GraphName"] == graph)
    remove = {"Action": "RemoveNode", "GraphName": graph_path, "NodeId": sequence}
    preview = mcp.call("GetAssetEditPreview", Capability="ManageAssetBlueprint", AssetPath=path, Operations=[remove])
    assert cap_first(preview)["bValid"] and preview["Removed"], preview
    assert sequence in graph_nodes(mcp, path, graph)
    written = cap_first(mcp.call("ManageAssetBlueprint", AssetPath=path, Operations=[remove], bVerifyStructure=True))
    assert written["bStructureVerified"], written
    after = graph_nodes(mcp, path, graph)
    assert sequence not in after and not pin(after[entry_id], "then").get("LinkedTo")


def test_remove_node_protects_math_expression_graph(mcp, require_tools, test_ns):
    require_tools("CreateAssetAnimBlueprint", "GetAssetBlueprint", "ManageAssetBlueprint", "ManageAssetAnimBlueprint",
                  "GetAssetEditPreview", "GetEditorGraph", "ExecPython", "SaveAsset")
    path = f"{test_ns}/ABP_ReadOnlyExpression"
    mcp.call("CreateAssetAnimBlueprint", AssetPath=path, SkeletonPath=resolve_skeleton(mcp))
    expression = edit(mcp, path, Action="AddNode", GraphName="EventGraph", NodeClass="K2Node_MathExpression")["NodeId"]

    def graphs():
        overview = cap_first(mcp.call("GetAssetBlueprint", AssetPath=path, Sections=["GraphOverview"]))
        return [g["GraphPath"] for g in overview["Graphs"]]

    graph = next(name for name in graphs() if "K2Node_MathExpression" in name)
    mcp.call("ExecPython", Code=f"import unreal\nunreal.find_object(None, {graph!r}).get_outer().set_editor_property('expression', 'x + 1')")
    mcp.call("SaveAsset", AssetPath=path)
    arithmetic = next(node_id for node_id, node in graph_nodes(mcp, path, graph).items()
                      if node["NodeClass"] == "K2Node_CallFunction")
    assert_removal_rejected(mcp, path, graph, arithmetic, "read-only graph", animation=True)
    before = graph_nodes(mcp, path, graph)
    for tool, operation in (
        ("ManageAssetBlueprint", {"Action": "SetNode", "NodeId": arithmetic, "Comment": "changed"}),
        ("ManageAssetBlueprint", {"Action": "DisconnectAll", "SourceNodeId": arithmetic, "SourcePinName": "ReturnValue"}),
        ("ManageAssetBlueprint", {"Action": "ArrangeNodes"}),
        ("ManageAssetAnimBlueprint", {"Action": "SetNode", "NodeId": arithmetic, "PosX": 307}),
    ):
        rejected = mcp.try_call(tool, AssetPath=path, Operations=[dict(operation, GraphName=graph)])
        assert rejected["isError"] and "read-only graph" in str(rejected), rejected
    assert graph_nodes(mcp, path, graph) == before
    assert not cap_first(mcp.call("GetEditorGraph", AssetPath=path))["bDirty"]

    remove = {"Action": "RemoveNode", "GraphName": "EventGraph", "NodeId": expression}
    preview = cap_first(mcp.call("GetAssetEditPreview", Capability="ManageAssetBlueprint", AssetPath=path, Operations=[remove]))
    assert preview["bValid"] and graph_nodes(mcp, path, graph) == before
    rolled_back = mcp.try_call("CallCapability", Calls=[
        {"Capability": "ManageAssetBlueprint", "Arguments": {"AssetPath": path, "Operations": [operation]}}
        for operation in (remove, dict(remove, NodeId=str(uuid.uuid4())))])
    assert rolled_back["isError"] and rolled_back["structuredContent"]["bRolledBack"], rolled_back
    assert expression in graph_nodes(mcp, path) and graph in graphs()
    assert graph_nodes(mcp, path, graph) == before
    actual = cap_first(mcp.call("ManageAssetBlueprint", AssetPath=path, Operations=[remove], bVerifyStructure=True))
    assert actual["bStructureVerified"] and expression not in graph_nodes(mcp, path) and graph not in graphs()


def test_blueprint_set_node_rejects_bad_pin_before_edit(mcp, require_tools, test_ns):
    path = create_blueprint(mcp, require_tools, test_ns, "SetNodeValidation")
    event = edit(mcp, path, Action="AddNode", NodeClass="K2Node_CustomEvent",
                 CustomEventName="BeforeEdit", GraphName="EventGraph")["NodeId"]
    mcp.call("SaveAsset", AssetPath=path)
    rejected = assert_rejected_without_changes(mcp, path, {
        "Action": "SetNode", "NodeId": event, "GraphName": "EventGraph", "CustomEventName": "AfterEdit",
        "PosX": 317, "Comment": "rejected", "PinName": "MissingPin", "PinDefaultValue": "1"})
    assert "MissingPin" in str(rejected)
    assert not cap_first(mcp.call("GetEditorGraph", AssetPath=path))["bDirty"]


def test_anim_blueprint_remove_node_protects_root(mcp, require_tools, test_ns):
    require_tools("CreateAssetAnimBlueprint", "ManageAssetAnimBlueprint", "GetAssetBlueprint")
    path = f"{test_ns}/ABP_ProtectedRoot"
    mcp.call("CreateAssetAnimBlueprint", AssetPath=path, SkeletonPath=resolve_skeleton(mcp))
    root = next(node_id for node_id, node in graph_nodes(mcp, path, "AnimGraph").items()
                if node["NodeClass"] == "AnimGraphNode_Root")
    player = cap_first(mcp.call("ManageAssetAnimBlueprint", AssetPath=path, Operations=[
        {"Action": "AddNode", "NodeClass": "SequencePlayer"}]))["NodeId"]
    mcp.call("ManageAssetAnimBlueprint", AssetPath=path, Operations=[{
        "Action": "Connect", "SourceNodeId": player, "SourcePinName": "Pose", "TargetNodeId": root, "TargetPinName": "Result",
    }])
    before = graph_nodes(mcp, path, "AnimGraph")
    assert any(link["NodeId"] == player for link in pin(before[root], "Result")["LinkedTo"])
    invalid_asset = mcp.try_call("ManageAssetAnimBlueprint", AssetPath=path, Operations=[{
        "Action": "SetNode", "NodeId": player, "SequencePath": f"{test_ns}/MissingSequence", "PosX": 317}])
    assert invalid_asset["isError"] and "Animation asset not found" in str(invalid_asset), invalid_asset
    assert graph_nodes(mcp, path, "AnimGraph") == before
    rejected = mcp.try_call("ManageAssetAnimBlueprint", AssetPath=path, Operations=[{"Action": "RemoveNode", "NodeId": root}])
    assert rejected.get("isError") and "cannot be deleted" in str(rejected), rejected
    assert graph_nodes(mcp, path, "AnimGraph") == before
    mcp.call("ManageAssetAnimBlueprint", AssetPath=path, Operations=[{"Action": "RemoveNode", "NodeId": player}])
    after = graph_nodes(mcp, path, "AnimGraph")
    assert player not in after and not pin(after[root], "Result").get("LinkedTo")


def test_blueprint_struct_pin_split_recombine_and_layout_readback(mcp, require_tools, test_ns):
    path = create_blueprint(mcp, require_tools, test_ns, "StructPinRoundtrip")
    edit(mcp, path, Action="AddVariable", VariableName="GraphVector", VariableType="Vector")
    node_id = add_variable_node(mcp, path, "GraphVector", setter=True, PosX=-240, PosY=135)
    edit(mcp, path, Action="SetNode", GraphName="EventGraph", NodeId=node_id, Comment="Struct pin roundtrip",
         PinName="GraphVector", PinDefaultValue="1,2,3")
    initial = graph_nodes(mcp, path)[node_id]
    assert (initial["PosX"], initial["PosY"], initial["Comment"]) == (-240, 135, "Struct pin roundtrip"), initial
    assert isinstance(initial["Width"], (int, float)) and isinstance(initial["Height"], (int, float)), initial
    assert not pin(initial, "GraphVector")["bHidden"] and pin(initial, "GraphVector")["SubPins"] == [], initial

    split = edit(mcp, path, Action="SplitPin", GraphName="EventGraph", NodeId=node_id, PinName="GraphVector")
    split_node = graph_nodes(mcp, path)[node_id]
    assert split["Node"] == split_node, split
    parent = pin(split_node, "GraphVector")
    assert parent["bHidden"] and len(parent["SubPins"]) == 3, parent
    for child_name in parent["SubPins"]:
        child = pin(split_node, child_name)
        assert child["ParentPin"] == "GraphVector" and not child["bHidden"], child
    assert [float(pin(split_node, child)["DefaultValue"]) for child in parent["SubPins"]] == [1, 2, 3], split_node

    # 父引脚和子引脚都能明确指定合并范围；合并后从资产重新读回。
    recombined = edit(mcp, path, Action="RecombinePin", GraphName="EventGraph", NodeId=node_id, PinName=parent["SubPins"][0])
    restored = graph_nodes(mcp, path)[node_id]
    restored_pin = pin(restored, "GraphVector")
    assert recombined["PinName"] == "GraphVector" and not restored_pin["bHidden"] and not restored_pin["SubPins"], restored
    assert len(restored["Pins"]) == len(initial["Pins"]), restored
    assert [float(value) for value in restored_pin["DefaultValue"].split(",")] == [1, 2, 3], restored_pin
    edit(mcp, path, Action="SplitPin", GraphName="EventGraph", NodeId=node_id, PinName="GraphVector")
    edit(mcp, path, Action="RecombinePin", GraphName="EventGraph", NodeId=node_id, PinName="GraphVector")
    assert graph_nodes(mcp, path)[node_id] == restored


def test_blueprint_struct_pin_rejects_connected_scalar_and_foreign_nodes(mcp, require_tools, test_ns):
    path = create_blueprint(mcp, require_tools, test_ns, "StructPinValidation")
    for name, variable_type in (("GraphVector", "Vector"), ("GraphFloat", "float")):
        edit(mcp, path, Action="AddVariable", VariableName=name, VariableType=variable_type)
    read_vector = add_variable_node(mcp, path, "GraphVector")
    write_vector = add_variable_node(mcp, path, "GraphVector", setter=True)
    read_float = add_variable_node(mcp, path, "GraphFloat")
    edit(mcp, path, Action="AddFunction", FunctionName="OtherGraph")
    foreign = add_variable_node(mcp, path, "GraphVector", graph="OtherGraph")
    base = dict(Action="SplitPin", GraphName="EventGraph", NodeId=write_vector, PinName="GraphVector")
    for invalid in (
        dict(base, NodeId=""), dict(base, NodeId=str(uuid.uuid4())), dict(base, NodeId=foreign),
        dict(base, PinName="MissingPin"), dict(base, NodeId=read_float, PinName="GraphFloat"),
        {key: value for key, value in base.items() if key != "PinName"},
        dict(base, Action="RecombinePin"),
    ):
        assert_rejected_without_changes(mcp, path, invalid)

    # SetNode 可直接写原始文本；SplitPin 必须在原生分量数 check 前拒绝非法默认值。
    for invalid_default in ("1,2,3,4", "nan,2,3", "1e400,2,3", "oops,2,3"):
        edit(mcp, path, Action="SetNode", GraphName="EventGraph", NodeId=write_vector,
             PinName="GraphVector", PinDefaultValue=invalid_default)
        rejected = assert_rejected_without_changes(mcp, path, base)
        assert "default" in str(rejected).lower(), rejected
    edit(mcp, path, Action="SetNode", GraphName="EventGraph", NodeId=write_vector, PinName="GraphVector", PinDefaultValue="1,2,3")

    edit(mcp, path, Action="Connect", GraphName="EventGraph", SourceNodeId=read_vector, SourcePinName="GraphVector",
         TargetNodeId=write_vector, TargetPinName="GraphVector")
    assert_rejected_without_changes(mcp, path, base)
    edit(mcp, path, Action="Disconnect", GraphName="EventGraph", SourceNodeId=read_vector, SourcePinName="GraphVector",
         TargetNodeId=write_vector, TargetPinName="GraphVector")
    edit(mcp, path, **base)
    assert_rejected_without_changes(mcp, path, base)
    split_node = graph_nodes(mcp, path)[write_vector]
    child_name = pin(split_node, "GraphVector")["SubPins"][0]
    edit(mcp, path, Action="Connect", GraphName="EventGraph", SourceNodeId=read_float, SourcePinName="GraphFloat",
         TargetNodeId=write_vector, TargetPinName=child_name)
    assert_rejected_without_changes(mcp, path, dict(base, Action="RecombinePin"))
    assert_rejected_without_changes(mcp, path, dict(base, Action="RecombinePin", PinName=child_name))
    edit(mcp, path, Action="DisconnectAll", GraphName="EventGraph", SourceNodeId=write_vector, SourcePinName=child_name)
    edit(mcp, path, **dict(base, Action="RecombinePin"))


def test_blueprint_struct_pin_preserves_unsupported_input_defaults(mcp, require_tools, test_ns):
    path = create_blueprint(mcp, require_tools, test_ns, "StructPinUnsupportedDefaults")
    edit(mcp, path, Action="AddVariable", VariableName="GraphTransform", VariableType="Transform")
    setter = add_variable_node(mcp, path, "GraphTransform", setter=True)
    non_default = "17,23,41|0,0,0|2,3,4"
    edit(mcp, path, Action="SetNode", GraphName="EventGraph", NodeId=setter, PinName="GraphTransform", PinDefaultValue=non_default)
    rejected = assert_rejected_without_changes(mcp, path, dict(Action="SplitPin", GraphName="EventGraph", NodeId=setter, PinName="GraphTransform"))
    assert "Unsupported" in str(rejected), rejected
    assert pin(graph_nodes(mcp, path)[setter], "GraphTransform")["DefaultValue"] == non_default

    # 输出引脚不承载输入默认值，Transform 仍可走 schema 原生拆组。
    getter = add_variable_node(mcp, path, "GraphTransform")
    split = edit(mcp, path, Action="SplitPin", GraphName="EventGraph", NodeId=getter, PinName="GraphTransform")
    assert pin(split["Node"], "GraphTransform")["SubPins"], split
    edit(mcp, path, Action="RecombinePin", GraphName="EventGraph", NodeId=getter, PinName="GraphTransform")
    restored = pin(graph_nodes(mcp, path)[getter], "GraphTransform")
    assert not restored["bHidden"] and not restored["SubPins"], restored


@pytest.mark.parametrize("variable_type,default_value,source_values,edited_values", [
    ("Vector", "16777217.125,0.000000000123456789,-2.345678901234567",
     ("16777217.125", "0.000000000123456789", "-2.345678901234567"),
     ("16777219.375", "0.000000000987654321", "-3.456789012345678")),
    ("Rotator", "16777217.125,0.000000000123456789,-2.345678901234567",
     ("16777217.125", "0.000000000123456789", "-2.345678901234567"),
     ("16777219.375", "0.000000000987654321", "-3.456789012345678")),
    ("Vector2D", "X=16777217.125 Y=0.000000000123456789",
     ("16777217.125", "0.000000000123456789"), ("16777219.375", "0.000000000987654321")),
    ("LinearColor", "(R=0.0000000123456789,G=0.234567891,B=0.345678912,A=0.456789123)",
     ("0.0000000123456789", "0.234567891", "0.345678912", "0.456789123"),
     ("0.0000000987654321", "0.345678912", "0.456789123", "0.567891234")),
], ids=["vector", "rotator", "vector2d", "linear_color"])
def test_blueprint_struct_pin_preserves_component_precision(mcp, require_tools, test_ns,
                                                           variable_type, default_value, source_values, edited_values):
    path = create_blueprint(mcp, require_tools, test_ns, f"StructPinPrecision_{variable_type}")
    edit(mcp, path, Action="AddVariable", VariableName="PrecisionValue", VariableType=variable_type)
    node_id = add_variable_node(mcp, path, "PrecisionValue", setter=True)
    edit(mcp, path, Action="SetNode", GraphName="EventGraph", NodeId=node_id,
         PinName="PrecisionValue", PinDefaultValue=default_value)
    operation = dict(GraphName="EventGraph", NodeId=node_id, PinName="PrecisionValue")
    split = edit(mcp, path, Action="SplitPin", **operation)["Node"]
    parent = pin(split, "PrecisionValue")
    child_names = parent["SubPins"]
    expected_split = (source_values[2], source_values[0], source_values[1]) if variable_type == "Rotator" else source_values
    assert parent["DefaultValue"] == default_value, parent
    assert [Decimal(pin(split, child)["DefaultValue"]) for child in child_names] == [Decimal(value) for value in expected_split], split

    # 合并必须采用当前子值，保留大坐标与细小小数，不能复用旧父值或先转成 float。
    for child_name, value in zip(child_names, edited_values):
        edit(mcp, path, Action="SetNode", GraphName="EventGraph", NodeId=node_id, PinName=child_name, PinDefaultValue=value)
    edit(mcp, path, Action="SetNode", GraphName="EventGraph", NodeId=node_id, PinName=child_names[0], PinDefaultValue="nan")
    assert_rejected_without_changes(mcp, path, dict(Action="RecombinePin", **operation))
    edit(mcp, path, Action="SetNode", GraphName="EventGraph", NodeId=node_id, PinName=child_names[0], PinDefaultValue=edited_values[0])
    recombined = edit(mcp, path, Action="RecombinePin", **operation)["Node"]
    expected_parent = (edited_values[1], edited_values[2], edited_values[0]) if variable_type == "Rotator" else edited_values
    actual_parent = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", pin(recombined, "PrecisionValue")["DefaultValue"])
    assert [Decimal(value) for value in actual_parent] == [Decimal(value) for value in expected_parent], recombined
    split_again = edit(mcp, path, Action="SplitPin", **operation)["Node"]
    assert [Decimal(pin(split_again, child)["DefaultValue"]) for child in pin(split_again, "PrecisionValue")["SubPins"]] == [Decimal(value) for value in edited_values], split_again


def test_blueprint_duplicate_nodes_preserves_internal_links_offsets_and_comments(mcp, require_tools, test_ns):
    path = create_blueprint(mcp, require_tools, test_ns, "DuplicateSelectedNodes")
    edit(mcp, path, Action="AddVariable", VariableName="GraphValue", VariableType="float")
    read_id = add_variable_node(mcp, path, "GraphValue", PosX=-180, PosY=90)
    write_id = add_variable_node(mcp, path, "GraphValue", setter=True, PosX=240, PosY=180)
    edit(mcp, path, Action="SetNode", GraphName="EventGraph", NodeId=read_id, Comment="Copied comment")
    edit(mcp, path, Action="Connect", GraphName="EventGraph", SourceNodeId=read_id, SourcePinName="GraphValue",
         TargetNodeId=write_id, TargetPinName="GraphValue")
    before = graph_nodes(mcp, path)
    copied = edit(mcp, path, Action="DuplicateNodes", GraphName="EventGraph", NodeIds=[read_id, write_id], OffsetX=315, OffsetY=-72)
    mapping = copied["NodeIdMap"]
    assert set(mapping) == {read_id, write_id}, copied
    assert len(set(mapping.values())) == 2 and not set(mapping.values()) & set(before), copied
    after = graph_nodes(mcp, path)
    assert len(after) == len(before) + 2, after
    for original_id, original in before.items():
        assert after[original_id] == original, (original, after[original_id])
    for original_id, new_id in mapping.items():
        new = after[new_id]
        assert new["PosX"] == before[original_id]["PosX"] + 315 and new["PosY"] == before[original_id]["PosY"] - 72, new
        assert new["Comment"] == before[original_id]["Comment"], new
        for copied_pin in new["Pins"]:
            for link in copied_pin.get("LinkedTo", []):
                assert link["NodeId"] in mapping.values(), link
    links = pin(after[mapping[read_id]], "GraphValue")["LinkedTo"]
    assert [(link["NodeId"], link["PinName"]) for link in links] == [(mapping[write_id], "GraphValue")], links
    assert copied["Nodes"] == [after[mapping[read_id]], after[mapping[write_id]]], copied

    # 只复制连接的一端时，原图外部连线不会被复制到新节点。
    single = edit(mcp, path, Action="DuplicateNodes", GraphName="EventGraph", NodeIds=[write_id])
    new_single = graph_nodes(mcp, path)[single["NodeIdMap"][write_id]]
    assert not pin(new_single, "GraphValue").get("LinkedTo"), new_single
    assert (new_single["PosX"], new_single["PosY"]) == (before[write_id]["PosX"] + 64, before[write_id]["PosY"] + 64), new_single
    zero = edit(mcp, path, Action="DuplicateNodes", GraphName="EventGraph", NodeIds=[read_id], OffsetX=0, OffsetY=0)
    zero_node = graph_nodes(mcp, path)[zero["NodeIdMap"][read_id]]
    assert (zero_node["PosX"], zero_node["PosY"]) == (before[read_id]["PosX"], before[read_id]["PosY"]), zero_node


def test_blueprint_duplicate_nodes_rejects_invalid_selection_boundaries_and_offsets(mcp, require_tools, test_ns):
    path = create_blueprint(mcp, require_tools, test_ns, "DuplicateNodeValidation")
    edit(mcp, path, Action="AddVariable", VariableName="GraphValue", VariableType="float")
    local = add_variable_node(mcp, path, "GraphValue", PosX=1)
    edit(mcp, path, Action="AddFunction", FunctionName="OtherGraph")
    foreign = add_variable_node(mcp, path, "GraphValue", graph="OtherGraph")
    function_nodes = graph_nodes(mcp, path, "OtherGraph")
    boundary = next(node_id for node_id, node in function_nodes.items() if node["NodeClass"] == "K2Node_FunctionEntry")
    base = dict(Action="DuplicateNodes", GraphName="EventGraph", NodeIds=[local])
    for invalid in (
        dict(base, NodeIds=[]), dict(base, NodeIds=[local] * 65), dict(base, NodeIds=[local, local]),
        dict(base, NodeIds=[local, str(uuid.uuid4())]), dict(base, NodeIds=[local, foreign]),
        dict(base, OffsetX=0.5), dict(base, OffsetY=2147483648), dict(base, OffsetX=2147483647),
        {key: value for key, value in base.items() if key != "NodeIds"},
    ):
        assert_rejected_without_changes(mcp, path, invalid)
    assert_rejected_without_changes(mcp, path, dict(base, GraphName="OtherGraph", NodeIds=[boundary]), graph="OtherGraph")
