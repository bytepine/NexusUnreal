# Copyright byteyang. All Rights Reserved.
"""动画分段/关键帧闭环、Niagara 深层写入、Game Features 与自定义工具发现。"""
import json
import os
import uuid
import pytest
from _framework.mcp_client import cap_first, MCPError
from _framework.assertions import merge_with_defaults
from test_17_native_toolsets import native_domain, official
from test_15_editor_operations import operation_result


def reference(path):
    return {"refPath": path + "." + path.rsplit("/", 1)[-1]}


def animation(mcp, action, parameters=None, write=False):
    return official(mcp, "ControlEditorAnimation" if write else "GetEditorAnimation", Action=action, Parameters=parameters or {})


def test_game_feature_discovery_and_target_validation(mcp, require_tools):
    require_tools("GetProjectGameFeatures", "ControlEditorGameFeature")
    listed = cap_first(mcp.call("GetProjectGameFeatures", Sections=["Plugins"], Limit=1))
    assert listed["Returned"] <= 1 and listed["Total"] >= listed["Returned"], listed
    for name in ("NexusLink", "file:C:/InvalidFeature.uplugin", "__UnknownFeature__"):
        bad = mcp.try_call("ControlEditorGameFeature", Action="Activate", PluginName=name)
        assert bad.get("isError"), bad
    bad = mcp.try_call("GetProjectGameFeatures", Sections=["State"], PluginName="NexusLink")
    assert bad.get("isError"), bad


@pytest.mark.skipif_ue_below("5.8")
def test_sequencer_section_and_typed_keys(mcp, require_tools, test_ns):
    native_domain(mcp, require_tools, "ControlEditorAnimation", "AnimationAssistantToolset")
    path = f"{test_ns}/LS_NativeSections"
    mcp.call("CreateAssetLevelSequence", AssetPath=path)
    sequence = reference(path)
    track = animation(mcp, "AddSequenceTrack", {"sequence": sequence, "track_type": {"refPath": "/Script/MovieSceneTracks.MovieSceneSlomoTrack"}}, write=True)
    assert "refPath" in track, track
    section = animation(mcp, "AddSection", {"track": track}, write=True)
    assert "refPath" in section, section
    animation(mcp, "SetSectionRange", {"section": section, "start_frame": 0, "end_frame": 48}, write=True)
    value = animation(mcp, "SectionRange", {"section": section})
    assert value["start"] == 0 and value["end"] == 48, value
    channels = animation(mcp, "ChannelNames", {"section": section})["Items"]
    assert channels, channels
    channel = {"section": section, "channel_name": channels[0]}
    assert animation(mcp, "AddFloatKey", dict(channel, frame=12, value=0.375, interpolation="linear"), write=True)["bApplied"]
    keys = animation(mcp, "Keys", channel)["Items"]
    assert any(item["frame"] == 12 and item["value"] == 0.375 for item in keys), keys
    assert animation(mcp, "RemoveKey", dict(channel, frame=12), write=True)["bApplied"]
    assert not animation(mcp, "Keys", channel)["Items"]
    animation(mcp, "RemoveSection", {"track": track, "section": section}, write=True)
    assert not animation(mcp, "Sections", {"track": track})["Items"]
    bool_track = animation(mcp, "AddSequenceTrack", {"sequence": sequence, "track_type": {"refPath": "/Script/MovieSceneTracks.MovieSceneBoolTrack"}}, write=True)
    bool_section = animation(mcp, "AddSection", {"track": bool_track}, write=True)
    bool_channel = animation(mcp, "ChannelNames", {"section": bool_section})["Items"][0]
    assert animation(mcp, "AddBoolKey", {"section": bool_section, "channel_name": bool_channel, "frame": 3, "value": True}, write=True)["bApplied"]
    assert animation(mcp, "Keys", {"section": bool_section, "channel_name": bool_channel})["Items"][0]["value"] is True
    with pytest.raises((AssertionError, MCPError)) as error:
        operation_result(mcp, mcp.call("ControlEditorAnimation", Action="SetSectionRange", Parameters={}))
    assert "section" in str(error.value).lower(), str(error.value)


@pytest.mark.skipif_ue_below("5.8")
def test_custom_toolset_discovery_and_unregister(mcp, require_tools):
    native_domain(mcp, require_tools, "GetProjectToolsets", "ToolsetRegistry")
    require_tools("ExecPython")
    suffix = uuid.uuid4().hex[:8]
    classname = "NexusDiscoveryFixture_" + suffix
    code = f"""import unreal, toolset_registry
@unreal.uclass()
class {classname}(unreal.ToolsetDefinition):
    @toolset_registry.tool_call
    @staticmethod
    def inspect_value(input_name: str) -> str:
        \"\"\"Return the fixture input.\"\"\"
        return input_name
unreal.ToolsetRegistry.register_toolset_class({classname})
"""
    mcp.call("ExecPython", Code=code)
    try:
        listed = cap_first(mcp.call("GetProjectToolsets", NameFilter=classname))
        items = merge_with_defaults(listed["Toolsets"], listed.get("Toolsets_defaults", {}))
        assert len(items) == 1, listed
        name = items[0]["Name"]
        tools = cap_first(mcp.call("GetProjectToolsets", Sections=["Tools"], ToolsetName=name))
        tool = tools["Tools"][0]["Name"]
        schema = cap_first(mcp.call("GetProjectToolsets", Sections=["Schema"], ToolsetName=name, ToolName=tool))["Schema"]
        assert "input_name" in schema["inputSchema"]["properties"], schema
        denied = mcp.try_call("ControlEditorAnimation", Action=tool, Parameters={"input_name": "no arbitrary execution"})
        assert denied.get("isError"), denied
        routes = cap_first(mcp.call("GetProjectToolsets", Sections=["AnimationRoutes"], Limit=100))
        assert routes["Total"] >= 59, routes
        for route in merge_with_defaults(routes["AnimationRoutes"], routes.get("AnimationRoutes_defaults", {})):
            assert route["bAvailable"], route
            schema = cap_first(mcp.call("GetProjectToolsets", Sections=["Schema"], ToolsetName=route["ToolsetName"], ToolName=route["ToolName"]))["Schema"]
            assert schema["name"] == route["ToolName"], route
    finally:
        mcp.call("ExecPython", Code=f"unreal.ToolsetRegistry.unregister_toolset_class({classname})")
    listed = cap_first(mcp.call("GetProjectToolsets", NameFilter=classname))
    assert listed["Total"] == 0, listed
    invalid = mcp.try_call("GetProjectToolsets", Sections=["Schema"], ToolsetName=name, ToolName=tool)
    assert invalid.get("isError"), invalid


@pytest.mark.skipif_ue_below("5.8")
def test_niagara_deep_system_write_and_variable_readback(mcp, require_tools, test_ns):
    native_domain(mcp, require_tools, "ControlEditorNiagara", "NiagaraToolsets")
    path = f"{test_ns}/NS_DeepWrite"
    mcp.call("CreateAssetNiagaraSystem", AssetPath=path)
    system = reference(path)
    schema = official(mcp, "GetEditorNiagara", Action="SystemSchema")
    assert schema, schema
    before = official(mcp, "GetEditorNiagara", Action="SystemData", AssetPath=system["refPath"])
    assert before, before
    result = official(mcp, "ControlEditorNiagara", Action="SetSystemData", Parameters={"system": system, "systemData": {"propertyValues": json.dumps({"bDeterminism": True, "RandomSeed": 1347})}})
    assert result.get("bApplied", True), result
    after = official(mcp, "GetEditorNiagara", Action="SystemData", AssetPath=system["refPath"])
    assert "1347" in json.dumps(after), after
    result = official(mcp, "GetEditorNiagara", Action="UserVariables", AssetPath=system["refPath"])
    assert result is not None
    data_schema = official(mcp, "GetEditorNiagara", Action="DataInterfaceSchema", ClassPath="/Script/Niagara.NiagaraDataInterfaceCurve")
    assert data_schema, data_schema

    variable_type = {"classStructOrEnum": {"refPath": "/Script/Niagara.NiagaraFloat"}}
    variable = {"name": "User.DeepFloat", "description": "Deep write fixture", "type": variable_type,
                "defaultValue": {"struct": {"refPath": "/Script/Niagara.NiagaraFloat"}, "value": {"value": 2.75}}}
    official(mcp, "ControlEditorNiagara", Action="AddUserVariables", Parameters={"system": system, "variablesToAdd": [variable]})
    variables = official(mcp, "GetEditorNiagara", Action="UserVariables", AssetPath=system["refPath"])["userVariables"]
    assert next(v for v in variables if v["name"] == "User.DeepFloat")["defaultValue"]["value"]["value"] == 2.75
    official(mcp, "ControlEditorNiagara", Action="RemoveUserVariables", Parameters={"system": system, "variablesToRemove": [{"name": variable["name"], "type": variable_type}]})
    assert not any(v["name"] == variable["name"] for v in official(mcp, "GetEditorNiagara", Action="UserVariables", AssetPath=system["refPath"])["userVariables"])
    mcp.call("ManageAssetNiagaraSystem", AssetPath=path, Operations=[{"Action": "AddEmitter", "EmitterName": "DeepFixtureEmitter"}])
    emitter = {"system": system, "emitterName": "DeepFixtureEmitter", "scriptName": "", "moduleName": "", "rendererIndex": -1, "inputNameStack": []}
    renderer = official(mcp, "ControlEditorNiagara", Action="AddRenderer", Parameters={"newRendererLocation": emitter, "rendererClass": {"refPath": "/Script/Niagara.NiagaraSpriteRendererProperties"}})
    renderer_ref = dict(emitter, rendererIndex=renderer["rendererIndex"])
    official(mcp, "ControlEditorNiagara", Action="SetRendererData", Parameters={"renderer": renderer_ref, "rendererData": {"propertyValues": json.dumps({"MacroUVRadius": 13.0})}})
    values = official(mcp, "GetEditorNiagara", Action="RendererData", AssetPath=system["refPath"], EmitterName=emitter["emitterName"], RendererIndex=renderer["rendererIndex"])
    assert json.loads(values["propertyValues"])["MacroUVRadius"] == 13.0, values
    official(mcp, "ControlEditorNiagara", Action="RemoveRenderer", Parameters={"rendererToRemove": renderer_ref})
    with pytest.raises((MCPError, AssertionError)):
        official(mcp, "GetEditorNiagara", Action="RendererData", AssetPath=system["refPath"], EmitterName=emitter["emitterName"], RendererIndex=renderer["rendererIndex"])


@pytest.mark.skipif_ue_below("5.8")
def test_toolset_registry_filters(mcp, require_tools):
    native_domain(mcp, require_tools, "GetProjectToolsets", "ToolsetRegistry")
    operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Discover"))
    result = operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Run", TestNames=["NexusLink.Toolsets.DiscoveryFilters"]))
    assert result["Tests"][0]["Outcome"] == "Passed", result


def test_game_feature_lifecycle_callback(mcp, require_tools):
    require_tools("GetProjectGameFeatures", "ControlEditorGameFeature", "CreateAssetDataAsset")
    name = os.environ.get("NEXUS_GAME_FEATURE_FIXTURE")
    if not name:
        pytest.skip("Needs an explicitly configured empty Game Feature fixture plugin (NEXUS_GAME_FEATURE_FIXTURE)")
    state = cap_first(mcp.call("GetProjectGameFeatures", Sections=["State"], PluginName=name))["State"]
    if state["bActive"]:
        operation_result(mcp, mcp.call("ControlEditorGameFeature", Action="Deactivate", PluginName=name))
    try:
        activated = operation_result(mcp, mcp.call("ControlEditorGameFeature", Action="Activate", PluginName=name))["OfficialResult"]
    except MCPError as error:
        assert "Plugin_Missing_GameFeatureData" in str(error), str(error)
        state = cap_first(mcp.call("GetProjectGameFeatures", Sections=["State"], PluginName=name))["State"]
        assert not state["bActive"] and state["State"] == "ErrorRegistering", state
        mcp.call("CreateAssetDataAsset", AssetPath=f"/{name}/GameFeatureData", ParentClass="GameFeatureData")
        activated = operation_result(mcp, mcp.call("ControlEditorGameFeature", Action="Activate", PluginName=name))["OfficialResult"]
    try:
        assert activated["bApplied"] and activated["bActive"] and activated["State"] == "Active", activated
        state = cap_first(mcp.call("GetProjectGameFeatures", Sections=["State"], PluginName=name))["State"]
        assert state["bActive"] and state["State"] == "Active", state
    finally:
        deactivated = operation_result(mcp, mcp.call("ControlEditorGameFeature", Action="Deactivate", PluginName=name))["OfficialResult"]
        assert deactivated["bApplied"] and not deactivated["bActive"] and deactivated["State"] == "Loaded", deactivated


@pytest.mark.skipif_ue_below("5.8")
def test_control_rig_bake_and_control_key(mcp, require_tools, test_ns):
    native_domain(mcp, require_tools, "ControlEditorAnimation", "AnimationAssistantToolset")
    require_tools("ExecPython")
    meshes = mcp.call("SearchAsset", AssetType="SkeletalMesh", PathFilter="/Game/Characters/Mannequins/", NameFilter="Manny", Limit=8)
    rigs = mcp.call("SearchAsset", AssetType="ControlRigBlueprint", PathFilter="/Game/Characters/Mannequins/Rigs/", NameFilter="Body", Limit=8)
    mesh_rows = merge_with_defaults(meshes["Assets"], meshes.get("Assets_defaults", {}))
    rig_rows = merge_with_defaults(rigs["Assets"], rigs.get("Assets_defaults", {}))
    if not mesh_rows or not rig_rows:
        pytest.skip("Needs mannequin skeletal mesh and Body Control Rig content")
    mesh_path, rig_path = mesh_rows[0]["Path"], rig_rows[0]["Path"]
    path = f"{test_ns}/LS_RigBake"
    mcp.call("CreateAssetLevelSequence", AssetPath=path)
    sequence = reference(path)
    prefix = "nexus_cr_" + uuid.uuid4().hex[:8]
    code = f"""import unreal
{prefix}_seq=unreal.load_asset({path!r})
{prefix}_seq.set_playback_start(0)
{prefix}_seq.set_playback_end(4)
{prefix}_actor=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(unreal.SkeletalMeshActor,unreal.Vector())
{prefix}_actor.skeletal_mesh_component.set_skeletal_mesh_asset(unreal.load_asset({mesh_path!r}))
{prefix}_binding={prefix}_seq.add_possessable({prefix}_actor)
"""
    mcp.call("ExecPython", Code=code)
    try:
        binding = animation(mcp, "Bindings", {"sequence": sequence})["Items"][0]
        assert animation(mcp, "OpenSequence", {"sequence": sequence}, write=True)["bApplied"]
        assert animation(mcp, "BakeToControlRig", {"sequence": sequence, "binding": binding, "control_rig_asset_path": rig_path,
                        "reduce_keys": False, "tolerance": 0.001, "reset_controls": True}, write=True)["bApplied"]
        controls = animation(mcp, "Controls", {"sequence": sequence, "control_rig_asset_path": rig_path})["Items"]
        name = next(control["name"] for control in controls if control["type"] == "EULER_TRANSFORM")
        control = {"sequence": sequence, "control_rig_asset_path": rig_path, "control_name": name, "frame": 0}
        assert animation(mcp, "SetRigTransform", dict(control, location_x=12.5, location_y=3.0, location_z=2.0,
                        rotation_pitch=0.0, rotation_yaw=15.0, rotation_roll=0.0, set_key=True), write=True)["bApplied"]
        value = animation(mcp, "RigTransform", control)
        assert value["location"]["x"] == pytest.approx(12.5), value
        assert value["rotation"]["yaw"] == pytest.approx(15.0), value
        assert animation(mcp, "ControlRigs", {"sequence": sequence})["Items"]
        assert isinstance(animation(mcp, "AnimationLayers")["Items"], list)
    finally:
        animation(mcp, "CloseSequence", write=True)
        mcp.call("ExecPython", Code=f"unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor({prefix}_actor); del {prefix}_actor, {prefix}_seq, {prefix}_binding")


@pytest.mark.skipif_ue_below("5.8")
def test_niagara_nested_dynamic_input_write(mcp, require_tools, test_ns):
    native_domain(mcp, require_tools, "ControlEditorNiagara", "NiagaraToolsets")
    path = f"{test_ns}/NS_DeepDynamic"
    mcp.call("CreateAssetNiagaraSystem", AssetPath=path)
    mcp.call("ManageAssetNiagaraSystem", AssetPath=path, Operations=[{"Action": "AddEmitter", "EmitterName": "DeepInputEmitter"}])
    asset = reference(path)["refPath"]
    topology = official(mcp, "GetEditorNiagara", Action="EmitterTopology", AssetPath=asset, EmitterName="DeepInputEmitter")
    script = topology["particleSpawnScript"]["scriptName"]
    location = {"system": reference(path), "emitterName": "DeepInputEmitter", "scriptName": script, "moduleName": "", "rendererIndex": -1, "inputNameStack": []}
    float_type = {"classStructOrEnum": {"refPath": "/Script/Niagara.NiagaraFloat"}}
    def float_value(value):
        return {"struct": {"refPath": "/Script/Niagara.NiagaraFloat"}, "value": {"value": value}}
    module = official(mcp, "ControlEditorNiagara", Action="AddSetParametersModule", Parameters={"moduleLocationRef": location,
                      "parameters": [{"variable": {"name": "Particles.DeepProbe", "type": float_type}, "defaultValue": float_value(1.25)}]})
    stack = official(mcp, "GetEditorNiagara", Action="ScriptTopology", AssetPath=asset, EmitterName=location["emitterName"], ScriptName=script)
    assert any(m["moduleName"] == module["moduleName"] for m in stack["modules"]), stack
    inspect = {"AssetPath": asset, "EmitterName": location["emitterName"], "ScriptName": script, "ModuleName": module["moduleName"], "InputNameStack": ["Particles.DeepProbe"]}
    input_ref = dict(location, moduleName=module["moduleName"], inputNameStack=inspect["InputNameStack"])
    assert official(mcp, "GetEditorNiagara", Action="InputData", **inspect)["value"]["value"] == 1.25
    official(mcp, "ControlEditorNiagara", Action="SetStackInputData", Parameters={"stackInputRef": input_ref, "inputData": float_value(4.25)})
    assert official(mcp, "GetEditorNiagara", Action="InputData", **inspect)["value"]["value"] == 4.25
    available = official(mcp, "GetEditorNiagara", Action="AvailableDynamicInputs", ClassPath="/Script/Niagara.NiagaraFloat")["Items"]
    multiply = next((asset for asset in available if "Multiply_Float.Multiply_Float" in asset["refPath"]), None)
    assert multiply, available
    official(mcp, "ControlEditorNiagara", Action="SetStackInputData", Parameters={"stackInputRef": input_ref,
             "inputData": {"struct": {"refPath": "/Script/NiagaraEditor.NiagaraExt_StackInputData_DynamicInput"}, "value": {"dynamicInputAsset": multiply}}})
    assert official(mcp, "GetEditorNiagara", Action="InputData", **inspect)["value"]["dynamicInputAsset"] == multiply
    chain = official(mcp, "GetEditorNiagara", Action="DynamicInputChain", **inspect)["value"]
    child = next(node["value"] for node in chain["inputs"] if node["value"]["bIsEditable"] and node["value"]["type"] == float_type)
    nested_names = inspect["InputNameStack"] + [child["name"]]
    official(mcp, "ControlEditorNiagara", Action="SetStackInputData", Parameters={"stackInputRef": dict(input_ref, inputNameStack=nested_names), "inputData": float_value(8.5)})
    value = official(mcp, "GetEditorNiagara", Action="InputData", **dict(inspect, InputNameStack=nested_names))
    assert value["value"]["value"] == 8.5, value
