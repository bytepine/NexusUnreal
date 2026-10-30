# Copyright byteyang. All Rights Reserved.
"""原生 Toolset / 引擎兼容实现：参数、结构、读写回环与拒绝后无额外写入。"""
import json
import uuid
import pytest
from _framework.mcp_client import cap_first
from test_15_editor_operations import operation_result
from test_19_remaining_toolsets import reference


def editor(mcp, capability, **arguments):
    result = operation_result(mcp, mcp.call(capability, **arguments))
    return result.get("OfficialResult", result.get("CompatibilityResult", result))


def edit(mcp, capability, path, **operation):
    result = cap_first(mcp.call(capability, AssetPath=path, Operations=[operation]))
    assert not result.get("Error"), result
    return result


def test_blueprint_graph_plan_and_function_parameters(mcp, require_tools, test_ns):
    require_tools("CreateAssetBlueprint", "ManageAssetBlueprint", "GetAssetBlueprint")
    path = f"{test_ns}/BP_GraphPlan"
    mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="Actor")
    edit(mcp, "ManageAssetBlueprint", path, Action="AddVariable", VariableName="PlanValue", VariableType="float")
    edit(mcp, "ManageAssetBlueprint", path, Action="SetVariableCategory", VariableName="PlanValue", Category="Compatibility")
    edit(mcp, "ManageAssetBlueprint", path, Action="SetVariableEditable", VariableName="PlanValue", bEditable=True)
    edit(mcp, "ManageAssetBlueprint", path, Action="AddFunction", FunctionName="PlanFunction")
    edit(mcp, "ManageAssetBlueprint", path, Action="AddFunctionParameter", GraphName="PlanFunction", ParameterName="InputValue", VariableType="float", bInput=True)
    plan = edit(mcp, "ManageAssetBlueprint", path, Action="WriteGraphPlan", GraphName="PlanFunction",
                GraphNodes=[{"Id": "Read", "NodeClass": "K2Node_VariableGet", "VariableName": "PlanValue"},
                            {"Id": "Write", "NodeClass": "K2Node_VariableSet", "VariableName": "PlanValue"}],
                GraphLinks=[{"From": "Read", "FromPin": "PlanValue", "To": "Write", "ToPin": "PlanValue"}])
    assert len(plan["Nodes"]) == 2, plan
    node = plan["Nodes"][0]["NodeId"]
    connected = cap_first(mcp.call("GetAssetBlueprint", AssetPath=path, Sections=["Subgraph"], GraphName="PlanFunction", NodeId=node))
    assert len(connected["Subgraph"]) == 2, connected
    edit(mcp, "ManageAssetBlueprint", path, Action="ArrangeNodes", GraphName="PlanFunction")
    invalid = mcp.try_call("ManageAssetBlueprint", AssetPath=path, Operations=[{
        "Action": "WriteGraphPlan", "GraphName": "PlanFunction", "GraphNodes": [
            {"Id": "Read", "NodeClass": "K2Node_VariableGet", "VariableName": "PlanValue"}],
        "GraphLinks": [{"From": "Read", "FromPin": "MissingPin", "To": "Read", "ToPin": "MissingPin"}]}])
    assert invalid.get("isError"), invalid
    edit(mcp, "ManageAssetBlueprint", path, Action="RemoveFunctionParameter", GraphName="PlanFunction", ParameterName="InputValue", bInput=True)


def test_static_mesh_generated_lods_and_convex(mcp, require_tools, test_ns):
    require_tools("DuplicateAsset", "ManageAssetStaticMesh", "GetAssetStaticMesh")
    path = f"{test_ns}/SM_Generation"
    mcp.call("DuplicateAsset", AssetPath="/Engine/BasicShapes/Cube", DestAssetPath=path)
    edit(mcp, "ManageAssetStaticMesh", path, Action="GenerateLODs", TrianglePercents=[0.75, 0.5])
    generated = cap_first(mcp.call("GetAssetStaticMesh", AssetPath=path))
    assert generated["LODCount"] == 3, generated
    bad = mcp.try_call("ManageAssetStaticMesh", AssetPath=path, Operations=[{"Action": "GenerateLODs", "TrianglePercents": [0.25, 0.75]}])
    assert bad.get("isError"), bad
    edit(mcp, "ManageAssetStaticMesh", path, Action="GenerateConvexCollision", HullCount=2, MaxHullVertices=16, HullPrecision=10000)
    edit(mcp, "ManageAssetStaticMesh", path, Action="RemoveLODs")
    assert cap_first(mcp.call("GetAssetStaticMesh", AssetPath=path))["LODCount"] == 1


def test_scene_folders_and_selection(mcp, require_tools):
    require_tools("GetEditorScene", "ControlEditorScene", "ExecPython")
    folder = "NexusCompatibility_" + uuid.uuid4().hex[:8]
    renamed = folder + "_Renamed"
    editor(mcp, "ControlEditorScene", Action="CreateFolder", FolderPath=folder)
    mcp.call("ExecPython", Code=f"import unreal\na=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.Actor,unreal.Vector())\na.set_folder_path('{folder}')")
    try:
        actors = editor(mcp, "GetEditorScene", Action="FolderActors", FolderPath=folder)
        assert "refPath" in json.dumps(actors), actors
        editor(mcp, "ControlEditorScene", Action="RenameFolder", FolderPath=folder, NewFolderPath=renamed)
        listed = editor(mcp, "GetEditorScene", Action="Folders", Limit=500)
        assert renamed in json.dumps(listed), listed
        bad = mcp.try_call("ControlEditorScene", Action="SetSelection", ActorPaths=["/Invalid/Actor"])
        assert bad.get("isError"), bad
    finally:
        editor(mcp, "ControlEditorScene", Action="DeleteFolder", FolderPath=renamed)
        mcp.call("ExecPython", Code="unreal.EditorLevelLibrary.destroy_actor(a)")


def test_scene_selection_and_static_mesh_merge(mcp, require_tools, test_ns):
    require_tools("GetEditorScene", "ControlEditorScene", "ExecPython", "GetAssetStaticMesh")
    label="NexusMerge_"+uuid.uuid4().hex[:8]
    code=f"""import unreal
mesh=unreal.load_asset('/Engine/BasicShapes/Cube')
merge_sources=[]
for i in range(2):
    actor=unreal.EditorLevelLibrary.spawn_actor_from_object(mesh,unreal.Vector(i*120,0,0))
    actor.set_actor_label('{label}_'+str(i))
    actor.set_folder_path('{label}')
    merge_sources.append(actor)
"""
    mcp.call("ExecPython",Code=code)
    try:
        actors=editor(mcp,"GetEditorScene",Action="FolderActors",FolderPath=label)["Items"]
        paths=[actor["refPath"] for actor in actors]
        assert len(paths)==2,actors
        editor(mcp,"ControlEditorScene",Action="SetSelection",ActorPaths=paths)
        assert len(editor(mcp,"GetEditorScene",Action="Selection")["Items"])==2
        asset=f"{test_ns}/SM_SceneMerge"
        editor(mcp,"ControlEditorScene",Action="MergeActors",ActorPaths=paths,AssetPath=asset,ActorName=label+"_Merged")
        mcp.call("ExecPython",Code=f"merged_actor=next(actor for actor in unreal.EditorLevelLibrary.get_all_level_actors() if actor.get_actor_label()=='{label}_Merged')\nmerged_mesh=merged_actor.static_mesh_component.static_mesh\nassert merged_mesh is not None and merged_mesh.get_num_lods() >= 1\nassert merged_mesh.get_path_name().startswith('{test_ns}/')")
        # 默认保留源 Actor，避免合并操作静默破坏输入场景。
        assert len(editor(mcp,"GetEditorScene",Action="FolderActors",FolderPath=label)["Items"])==2
    finally:
        editor(mcp,"ControlEditorScene",Action="SetSelection",ActorPaths=[])
        mcp.call("ExecPython",Code=f"for actor in unreal.EditorLevelLibrary.get_all_level_actors():\n    if actor.get_actor_label().startswith('{label}'):\n        unreal.EditorLevelLibrary.destroy_actor(actor)")


def test_widget_structural_operations(mcp, require_tools, test_ns):
    require_tools("CreateAssetUserWidget", "ManageAssetUserWidget", "GetAssetUserWidget")
    path=f"{test_ns}/WBP_StructureCompatibility"
    mcp.call("CreateAssetUserWidget", AssetPath=path)
    for op in [dict(Action="Add",WidgetClass="VerticalBox",WidgetName="Root"),
               dict(Action="Add",WidgetClass="TextBlock",WidgetName="Label",ParentWidget="Root"),
               dict(Action="Add",WidgetClass="HorizontalBox",WidgetName="Destination",ParentWidget="Root"),
               dict(Action="Move",WidgetName="Label",ParentWidget="Destination"),
               dict(Action="Wrap",WidgetName="Label",WidgetClass="Border")]:
        edit(mcp,"ManageAssetUserWidget",path,**op)
    tree=cap_first(mcp.call("GetAssetUserWidget",AssetPath=path))
    assert "Label" in json.dumps(tree) and "Destination" in json.dumps(tree),tree
    bad=mcp.try_call("ManageAssetUserWidget",AssetPath=path,Operations=[dict(Action="Move",WidgetName="Root",ParentWidget="Destination")])
    assert bad.get("isError"),bad


def test_sequencer_compatible_sections_and_keys(mcp, require_tools, test_ns):
    require_tools("GetEditorAnimation","ControlEditorAnimation","CreateAssetLevelSequence")
    path=f"{test_ns}/LS_Compatibility"
    mcp.call("CreateAssetLevelSequence",AssetPath=path)
    track=editor(mcp,"ControlEditorAnimation",Action="AddSequenceTrack",Parameters={"sequence":reference(path),"track_type":{"refPath":"/Script/MovieSceneTracks.MovieSceneSlomoTrack"}})
    section=editor(mcp,"ControlEditorAnimation",Action="AddSection",Parameters={"track":track})
    editor(mcp,"ControlEditorAnimation",Action="SetSectionRange",Parameters={"section":section,"start_frame":0,"end_frame":48})
    bounds=editor(mcp,"GetEditorAnimation",Action="SectionRange",Parameters={"section":section})
    assert bounds["start"]==0 and bounds["end"]==48,bounds
    names=editor(mcp,"GetEditorAnimation",Action="ChannelNames",Parameters={"section":section})["Items"]
    channel={"section":section,"channel_name":names[0]}
    editor(mcp,"ControlEditorAnimation",Action="AddFloatKey",Parameters=dict(channel,frame=12,value=0.375,interpolation="linear"))
    assert editor(mcp,"GetEditorAnimation",Action="Keys",Parameters=channel)["Items"][0]["value"]==0.375
    editor(mcp,"ControlEditorAnimation",Action="RemoveKey",Parameters=dict(channel,frame=12))
    assert not editor(mcp,"GetEditorAnimation",Action="Keys",Parameters=channel)["Items"]


def test_niagara_compatible_variables_and_renderers(mcp, require_tools, test_ns):
    require_tools("ControlEditorNiagara","GetEditorNiagara","CreateAssetNiagaraSystem")
    path=f"{test_ns}/NS_Compatibility"
    mcp.call("CreateAssetNiagaraSystem",AssetPath=path)
    system=reference(path)
    value_type={"classStructOrEnum":{"refPath":"/Script/Niagara.NiagaraFloat"}}
    variable={"name":"User.CompatibilityFloat","type":value_type,"defaultValue":{"struct":{"refPath":"/Script/Niagara.NiagaraFloat"},"value":{"value":2.75}}}
    editor(mcp,"ControlEditorNiagara",Action="AddUserVariables",Parameters={"system":system,"variablesToAdd":[variable]})
    variables=editor(mcp,"GetEditorNiagara",Action="UserVariables",AssetPath=system["refPath"])["userVariables"]
    assert next(item for item in variables if item["name"]==variable["name"])["defaultValue"]["value"]["value"]==2.75
    edit(mcp,"ManageAssetNiagaraSystem",path,Action="AddEmitter",EmitterName="CompatibilityEmitter")
    emitter={"system":system,"emitterName":"CompatibilityEmitter","scriptName":"","moduleName":"","rendererIndex":-1,"inputNameStack":[]}
    renderer=editor(mcp,"ControlEditorNiagara",Action="AddRenderer",Parameters={"newRendererLocation":emitter,"rendererClass":{"refPath":"/Script/Niagara.NiagaraSpriteRendererProperties"}})
    renderer_ref=dict(emitter,rendererIndex=renderer["rendererIndex"])
    editor(mcp,"ControlEditorNiagara",Action="SetRendererData",Parameters={"renderer":renderer_ref,"rendererData":{"propertyValues":json.dumps({"SortOrderHint":13})}})
    values=editor(mcp,"GetEditorNiagara",Action="RendererData",AssetPath=system["refPath"],EmitterName=emitter["emitterName"],RendererIndex=renderer["rendererIndex"])
    assert json.loads(values["propertyValues"])["SortOrderHint"]==13,values
    editor(mcp,"ControlEditorNiagara",Action="RemoveRenderer",Parameters={"rendererToRemove":renderer_ref})


@pytest.mark.skipif_ue_below("5.4")
def test_pcg_compatible_parameter_definitions(mcp, require_tools, test_ns):
    require_tools("ControlEditorPCG","GetEditorPCG","CreateAssetPCGGraph","GetEditorScene","ExecPython")
    path=f"{test_ns}/PCG_Compatibility"
    mcp.call("CreateAssetPCGGraph",AssetPath=path)
    editor(mcp,"ControlEditorPCG",Action="SetGraphParameters",AssetPath=reference(path)["refPath"],ParameterDefinitions=[{"Name":"Density","Type":"Float","ContainerType":"None","DefaultValueJson":"0.25"}])
    schema=editor(mcp,"GetEditorPCG",Action="GraphSchema",AssetPath=reference(path)["refPath"])
    assert "density" in json.dumps(schema).lower(),schema
    folder="NexusPCG_"+uuid.uuid4().hex[:8]
    mcp.call("ExecPython",Code=f"import unreal\npcg_fixture=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.PCGVolume,unreal.Vector())\npcg_fixture.set_folder_path('{folder}')\npcg_fixture.get_component_by_class(unreal.PCGComponent).set_graph(unreal.load_asset('{path}'))")
    try:
        actors=editor(mcp,"GetEditorScene",Action="FolderActors",FolderPath=folder)["Items"]
        actor=actors[0]["refPath"]
        editor(mcp,"ControlEditorPCG",Action="SetInstanceParameters",ActorPath=actor,Parameters={"Density":0.75})
        values=editor(mcp,"GetEditorPCG",Action="InstanceParameters",ActorPath=actor)
        assert "0.75" in json.dumps(values),values
        editor(mcp,"ControlEditorPCG",Action="ResetInstanceParameters",ActorPath=actor,ParameterNames=["Density"])
        reset=editor(mcp,"GetEditorPCG",Action="InstanceParameters",ActorPath=actor)
        assert "0.25" in json.dumps(reset),reset
    finally:
        mcp.call("ExecPython",Code="unreal.EditorLevelLibrary.destroy_actor(pcg_fixture)")
