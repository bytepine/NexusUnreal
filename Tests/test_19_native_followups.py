# Copyright byteyang. All Rights Reserved.
"""PCG 参数闭环、PhysicsAsset 精细编辑、Tag 配置与 DataRegistry 查询。"""
import uuid
import json
import pytest
from _framework.mcp_client import cap_first, MCPError
from _framework.assertions import merge_with_defaults
from test_17_native_toolsets import native_domain, official
from test_15_editor_operations import operation_result


def object_path(path):
    return path + "." + path.rsplit("/", 1)[1]


def refs(value):
    if isinstance(value, dict):
        if isinstance(value.get("refPath"), str):
            yield value["refPath"]
        for item in value.values():
            yield from refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from refs(item)



def test_physics_asset_create_edit_and_readback(mcp, require_tools, test_ns):
    require_tools("CreateAssetPhysicsAsset", "ManageAssetPhysicsAsset", "GetAssetPhysicsAsset")
    found = mcp.call("SearchAsset", AssetType="SkeletalMesh", PathFilter="/Game/", Limit=1).get("Assets", [])
    if not found:
        pytest.skip("No SkeletalMesh fixture available")
    mesh = found[0].get("Path") or found[0].get("AssetPath")
    path = f"{test_ns}/PA_Detailed"
    created = cap_first(mcp.call("CreateAssetPhysicsAsset", AssetPath=path, SkeletalMeshPath=mesh))
    assert not created.get("Error"), created
    original = cap_first(mcp.call("GetAssetPhysicsAsset", AssetPath=path))
    bodies = merge_with_defaults(original["Bodies"], original.get("Bodies_defaults", {}))
    assert bodies, original
    bone = bodies[0]["BoneName"]
    def edit(**op):
        return cap_first(mcp.call("ManageAssetPhysicsAsset", AssetPath=path, Operations=[op]))
    edit(Action="AddSphere", BoneName=bone, Radius=9)
    snapshot = cap_first(mcp.call("GetAssetPhysicsAsset", AssetPath=path))
    body = next(row for row in merge_with_defaults(snapshot["Bodies"], snapshot.get("Bodies_defaults", {})) if row["BoneName"] == bone)
    index = body["SpheresCount"] - 1
    edit(Action="UpdateShape", BoneName=bone, ShapeType="Sphere", ShapeIndex=index, Radius=13, CenterX=7)
    mcp.call("ManageAssetPhysicsAsset", AssetPath=path, Operations=[{"Action": "SetMassScale", "BoneName": bone, "MassScale": 2.5}])
    snapshot = cap_first(mcp.call("GetAssetPhysicsAsset", AssetPath=path))
    body = next(row for row in merge_with_defaults(snapshot["Bodies"], snapshot.get("Bodies_defaults", {})) if row["BoneName"] == bone)
    shapes = merge_with_defaults(body["Shapes"], body.get("Shapes_defaults", {}))
    shape = next(row for row in shapes if row["ShapeType"] == "Sphere" and row["ShapeIndex"] == index)
    assert shape["Radius"] == 13 and shape["CenterX"] == 7 and body["MassScale"] == 2.5, body
    bad = mcp.try_call("ManageAssetPhysicsAsset", AssetPath=path, Operations=[{"Action": "UpdateShape", "BoneName": bone, "ShapeType": "Sphere", "ShapeIndex": index, "Radius": -1}])
    assert bad.get("isError") or "Error" in str(bad), bad
    mcp.call("ManageAssetPhysicsAsset", AssetPath=path, Operations=[{"Action": "RemoveShape", "BoneName": bone, "ShapeType": "Sphere", "ShapeIndex": index}])
    for shape_type, add_action, dimensions in [("Capsule", "AddCapsule", {"Radius": 11, "HalfHeight": 22}),
                                                ("Box", "AddBox", {"ExtentX": 14, "ExtentY": 15, "ExtentZ": 16})]:
        edit(Action=add_action, BoneName=bone)
        snapshot = cap_first(mcp.call("GetAssetPhysicsAsset", AssetPath=path))
        body = next(row for row in snapshot["Bodies"] if row["BoneName"] == bone)
        shape_index = max(row["ShapeIndex"] for row in body["Shapes"] if row["ShapeType"] == shape_type)
        edit(Action="UpdateShape", BoneName=bone, ShapeType=shape_type, ShapeIndex=shape_index, RotationYaw=23, CenterY=8, **dimensions)
        snapshot = cap_first(mcp.call("GetAssetPhysicsAsset", AssetPath=path))
        body = next(row for row in snapshot["Bodies"] if row["BoneName"] == bone)
        shape = next(row for row in body["Shapes"] if row["ShapeType"] == shape_type and row["ShapeIndex"] == shape_index)
        assert shape["RotationYaw"] == 23 and shape["CenterY"] == 8 and all(shape[key] == value for key, value in dimensions.items()), shape
        edit(Action="RemoveShape", BoneName=bone, ShapeType=shape_type, ShapeIndex=shape_index)

    if len(bodies) >= 2:
        added = edit(Action="AddConstraint", Bone1=bone, Bone2=bodies[1]["BoneName"])
        joint = added["JointName"]
        mcp.call("ManageAssetPhysicsAsset", AssetPath=path, Operations=[{"Action": "SetConstraintLimits", "JointName": joint, "Swing1Motion": "Limited", "Swing1Limit": 27, "TwistMotion": "Locked"}])
        snapshot = cap_first(mcp.call("GetAssetPhysicsAsset", AssetPath=path))
        constraints = merge_with_defaults(snapshot["Constraints"], snapshot.get("Constraints_defaults", {}))
        constraint = next(row for row in constraints if row["JointName"] == joint)
        assert constraint["Swing1Limit"] == 27 and constraint["Swing1Motion"] == "Limited" and constraint["TwistMotion"] == "Locked", constraint
        edit(Action="RemoveConstraint", JointName=joint)
    mcp.call("ManageAssetPhysicsAsset", AssetPath=path, Operations=[{"Action": "RemoveBody", "BoneName": bone}])
    mcp.call("ManageAssetPhysicsAsset", AssetPath=path, Operations=[{"Action": "AddBody", "BoneName": bone}])
    duplicate = mcp.try_call("CreateAssetPhysicsAsset", AssetPath=path, SkeletalMeshPath=mesh)
    assert duplicate.get("isError") or "Error" in str(duplicate), duplicate
    collision = f"{test_ns}/BP_PhysicsDestination"
    mcp.call("CreateAssetBlueprint", AssetPath=collision, ParentClass="Actor")
    wrong_class = mcp.try_call("CreateAssetPhysicsAsset", AssetPath=collision, SkeletalMeshPath=mesh)
    assert wrong_class.get("isError") or "Error" in str(wrong_class), wrong_class
    preserved = mcp.call("SearchAsset", AssetType="Blueprint", PathFilter=test_ns + "/", Query="BP_PhysicsDestination", Limit=2)
    assert preserved.get("Assets"), preserved
    mcp.call("SaveAsset", AssetPath=path)


def test_project_gameplay_tag_lifecycle(mcp, require_tools):
    require_tools("ManageGameplayTags", "GetGameplayTags")
    suffix = uuid.uuid4().hex
    tag, renamed = f"NexusMcpTests.T{suffix}.Original", f"NexusMcpTests.T{suffix}.Renamed"
    source = f"NexusMcpTest_{suffix}.ini"
    def edit(target, **op):
        return cap_first(mcp.call("ManageGameplayTags", Tag=target, Operations=[op]))
    added = edit(tag, Action="Add", TagSource=source, Comment="Nexus tag lifecycle fixture")
    assert added.get("bApplied"), added
    info = cap_first(mcp.call("GetGameplayTags", Sections=["Info"], Tag=tag))["Info"]
    assert info["Source"] == source and info["bExplicit"], info
    sources = cap_first(mcp.call("GetGameplayTags", Sections=["Sources"], NameFilter=source))
    assert source in str(sources), sources
    child = tag + ".Child"
    edit(child, Action="Add", TagSource=source)
    blocked = mcp.try_call("ManageGameplayTags", Tag=tag, Operations=[{"Action": "Remove"}])
    assert blocked.get("isError") or "Error" in str(blocked), blocked
    edit(child, Action="Remove")
    mcp.call("ManageGameplayTags", Tag=tag, Operations=[{"Action": "Rename", "NewTag": renamed}])
    info = cap_first(mcp.call("GetGameplayTags", Sections=["Info"], Tag=renamed))["Info"]
    assert info["Tag"] == renamed, info
    edit(renamed, Action="Remove")
    missing = mcp.try_call("GetGameplayTags", Sections=["Info"], Tag=renamed)
    assert missing.get("isError") or "Error" in str(missing), missing
    invalid = mcp.try_call("ManageGameplayTags", Tag=f"NexusMcpTests.T{suffix}.Unsafe", Operations=[{"Action": "Add", "TagSource": "../Forbidden.ini"}])
    assert invalid.get("isError") or "Error" in str(invalid), invalid


def test_data_registry_discovery_and_values(mcp, require_tools):
    require_tools("GetProjectDataRegistry", "ControlEditorAutomation")
    listed = cap_first(mcp.call("GetProjectDataRegistry", Sections=["Registries"], Limit=5))
    assert isinstance(listed["Registries"], list), listed
    operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Discover"))
    result = operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Run", TestNames=["NexusLink.DataRegistry.Query"]))
    assert result["Tests"][0]["Outcome"] == "Passed", result
    missing = mcp.try_call("GetProjectDataRegistry", RegistryName="__NexusUnknownRegistry__", Sections=["Info"])
    assert missing.get("isError") or "Error" in str(missing), missing


@pytest.mark.skipif_ue_below("5.8")
def test_pcg_parameter_subgraph_instance_roundtrip(mcp, require_tools, test_ns):
    native_domain(mcp, require_tools, "ControlEditorPCG", "PCGToolset")
    parent, child = f"{test_ns}/PCG_Params", f"{test_ns}/PCG_Subgraph"
    for path in [parent, child]:
        mcp.call("CreateAssetPCGGraph", AssetPath=path)
    graph = object_path(parent)
    result = official(mcp, "ControlEditorPCG", Action="SetGraphParameters", AssetPath=graph,
                      ParameterDefinitions=[{"Name": "Density", "Type": "Float", "DefaultValueJson": "1.5"},
                                            {"Name": "ProbeFlag", "Type": "Boolean", "DefaultValueJson": "true"}])
    assert result.get("bApplied", True), result
    schema = official(mcp, "GetEditorPCG", Action="GraphSchema", AssetPath=graph)
    assert {key.lower() for key in json.loads(schema["graphParamsSchema"])} >= {"density", "probeflag"}, schema
    available = official(mcp, "GetEditorPCG", Action="AvailableSubgraphs")
    assert isinstance(available, dict)
    subgraph = official(mcp, "ControlEditorPCG", Action="AddSubgraph", AssetPath=graph,
                        SubgraphPath=object_path(child), NodeName="NestedProbe")
    assert subgraph, subgraph
    nodes = cap_first(mcp.call("GetAssetPCGGraph", AssetPath=parent))
    assert len(nodes["Nodes"]) == 1, nodes
    node_path = nodes["Nodes"][0]["Path"]
    node_info = official(mcp, "GetEditorPCG", Action="NodeInfo", NodePath=node_path)
    assert node_info, node_info
    spawned = official(mcp, "ControlEditorPCG", Action="Spawn", AssetPath=graph, ActorName="NexusPcgParams")
    actor = next(path for path in refs(spawned) if ":PersistentLevel." in path)
    changed = official(mcp, "ControlEditorPCG", Action="SetInstanceParameters", ActorPath=actor, Parameters={"Density": 3.25})
    assert changed.get("bApplied", True), changed
    read = official(mcp, "GetEditorPCG", Action="InstanceParameters", ActorPath=actor)
    assert "3.25" in str(read), read
    reset = official(mcp, "ControlEditorPCG", Action="ResetInstanceParameters", ActorPath=actor, ParameterNames=["Density"])
    assert reset.get("bApplied", True), reset
    read = official(mcp, "GetEditorPCG", Action="InstanceParameters", ActorPath=actor)
    assert "1.5" in str(read), read
    removed = official(mcp, "ControlEditorPCG", Action="RemoveGraphParameters", AssetPath=graph, ParameterNames=["ProbeFlag"])
    assert removed.get("bApplied", True), removed
    assert "probeflag" not in str(official(mcp, "GetEditorPCG", Action="GraphSchema", AssetPath=graph)).lower()
    invalid = mcp.try_call("ControlEditorPCG", Action="AddSubgraph", AssetPath=graph, SubgraphPath=graph, NodeName="Cycle")
    assert invalid.get("isError"), invalid
    indirect = mcp.try_call("ControlEditorPCG", Action="AddSubgraph", AssetPath=object_path(child), SubgraphPath=graph, NodeName="IndirectCycle")
    assert indirect.get("isError"), indirect
    duplicate_node = mcp.try_call("ControlEditorPCG", Action="AddSubgraph", AssetPath=graph, SubgraphPath=object_path(child), NodeName="NestedProbe")
    assert duplicate_node.get("isError"), duplicate_node
    invalid_parameter = mcp.try_call("ControlEditorPCG", Action="SetGraphParameters", AssetPath=graph, ParameterDefinitions=[{"Name": "Bad.Name", "Type": "Float"}])
    assert invalid_parameter.get("isError"), invalid_parameter
    invalid_default = mcp.try_call("ControlEditorPCG", Action="SetGraphParameters", AssetPath=graph, ParameterDefinitions=[{"Name": "BadDefault", "Type": "Float", "DefaultValueJson": "1,2"}])
    assert invalid_default.get("isError"), invalid_default
    mcp.call("SaveAsset", AssetPath=parent)


@pytest.mark.skipif_ue_below("5.8")
def test_pcg_node_settings_readback(mcp, require_tools, test_ns):
    native_domain(mcp, require_tools, "ControlEditorPCG", "PCGToolset")
    path = f"{test_ns}/PCG_NodeEdit"
    mcp.call("CreateAssetPCGGraph", AssetPath=path)
    mcp.call("ManageAssetPCGGraph", AssetPath=path, Operations=[{"Action": "AddNode", "SettingsClass": "PCGCreatePointsGridSettings"}])
    graph_info = cap_first(mcp.call("GetAssetPCGGraph", AssetPath=path))
    node = graph_info["Nodes"][0]
    output = graph_info["OutputNode"]
    mcp.call("ManageAssetPCGGraph", AssetPath=path, Operations=[{"Action": "AddEdge", "FromNodeId": node["Id"], "FromPin": node["OutputPins"][0], "ToNodeId": output["Id"], "ToPin": output["InputPins"][0]}])
    spawned = official(mcp, "ControlEditorPCG", Action="Spawn", AssetPath=object_path(path), ActorName="NexusPcgNodeEdit")
    actor = next(value for value in refs(spawned) if ":PersistentLevel." in value)
    try:
        official(mcp, "GetEditorPCG", Action="NodeData", ActorPath=actor, NodePath=node["Path"], PinLabel=node["OutputPins"][0], Limit=1)
    except MCPError as error:
        assert "inspection" in str(error).lower(), str(error)
    official(mcp, "ControlEditorPCG", Action="Execute", ActorPath=actor)
    before = official(mcp, "GetEditorPCG", Action="NodeData", ActorPath=actor, NodePath=node["Path"], PinLabel=node["OutputPins"][0], Limit=1)

    result = official(mcp, "ControlEditorPCG", Action="UpdateNode", NodePath=node["Path"],
                      Parameters={"CellSize": {"x": 123, "y": 234, "z": 345}}, NodeTitle="AdjustedGrid")
    assert result.get("bApplied", True), result
    info = official(mcp, "GetEditorPCG", Action="NodeInfo", NodePath=node["Path"])
    assert "123" in str(info) and "234" in str(info) and "345" in str(info), info
    official(mcp, "ControlEditorPCG", Action="Execute", ActorPath=actor)
    after = official(mcp, "GetEditorPCG", Action="NodeData", ActorPath=actor, NodePath=node["Path"], PinLabel=node["OutputPins"][0], Limit=1)
    assert before["totalElements"] > 0 and after["totalElements"] > 0 and before["totalElements"] != after["totalElements"], (before, after)

    invalid = mcp.try_call("ControlEditorPCG", Action="UpdateNode", NodePath=node["Path"], Parameters={})
    assert invalid.get("isError"), invalid
