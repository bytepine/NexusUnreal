# Copyright byteyang. All Rights Reserved.
"""剩余编辑器能力：UMG、材质、配置/插件与 Sequencer。"""
import json
import os
from pathlib import Path
import uuid
import pytest
from _framework.mcp_client import cap_first
from _framework.assertions import merge_with_defaults
from test_20_editor_compatibility import editor,edit
from test_19_remaining_toolsets import reference


def manage(mcp,capability,selector,operation):
    result=cap_first(mcp.call(capability,**selector,Operations=[operation]))
    assert not result.get("Error"),result
    return result


def test_widget_variable_event_rename(mcp,require_tools,test_ns):
    require_tools("CreateAssetUserWidget","ManageAssetUserWidget","GetAssetBlueprint")
    path=f"{test_ns}/WBP_Advanced"
    mcp.call("CreateAssetUserWidget",AssetPath=path)
    edit(mcp,"ManageAssetUserWidget",path,Action="Add",WidgetName="Root",WidgetClass="CanvasPanel")
    edit(mcp,"ManageAssetUserWidget",path,Action="Add",WidgetName="ActionButton",WidgetClass="Button",ParentWidget="Root")
    mcp.call("ManageAssetUserWidget",AssetPath=path,bCompile=True,Operations=[dict(Action="SetVariable",WidgetName="ActionButton",bIsVariable=True)])
    edit(mcp,"ManageAssetUserWidget",path,Action="BindEvent",WidgetName="ActionButton",EventName="OnClicked")
    edit(mcp,"ManageAssetUserWidget",path,Action="Rename",WidgetName="ActionButton",NewWidgetName="RenamedButton")
    data=cap_first(mcp.call("GetAssetUserWidget",AssetPath=path))
    assert "RenamedButton" in json.dumps(data),data
    mcp.call("ExecPython",Code=f"import unreal\nbp=unreal.load_asset('{path}')\nassert bp is not None")
    bad=mcp.try_call("ManageAssetUserWidget",AssetPath=path,Operations=[dict(Action="Rename",WidgetName="RenamedButton",NewWidgetName="Root")])
    assert bad.get("isError"),bad


@pytest.mark.skipif_ue_below("5.6")
def test_widget_ui_components(mcp,require_tools,test_ns):
    require_tools("ManageAssetUserWidget","GetAssetUserWidget")
    path=f"{test_ns}/WBP_Components"
    mcp.call("CreateAssetUserWidget",AssetPath=path)
    edit(mcp,"ManageAssetUserWidget",path,Action="Add",WidgetName="Root",WidgetClass="CanvasPanel")
    edit(mcp,"ManageAssetUserWidget",path,Action="Add",WidgetName="Target",WidgetClass="Button",ParentWidget="Root")
    component="/Script/UMG.NavigationUIComponent"
    edit(mcp,"ManageAssetUserWidget",path,Action="AddUIComponent",WidgetName="Target",ComponentClass=component)
    data=cap_first(mcp.call("GetAssetUserWidget",AssetPath=path,Sections=["UIComponents"]))
    assert data["UIComponentCount"]==1,data
    edit(mcp,"ManageAssetUserWidget",path,Action="RemoveUIComponent",WidgetName="Target",ComponentClass=component)
    assert cap_first(mcp.call("GetAssetUserWidget",AssetPath=path,Sections=["UIComponents"]))["UIComponentCount"]==0


@pytest.mark.parametrize("kind",["Material","MaterialFunction"])
def test_material_graph_organization(mcp,require_tools,test_ns,kind):
    require_tools("ManageAssetMaterial","GetAssetMaterial")
    path=f"{test_ns}/M_Organize_{kind}"
    mcp.call("CreateAssetMaterialFunction" if kind=="MaterialFunction" else "CreateAssetMaterial",AssetPath=path)
    edit(mcp,"ManageAssetMaterial",path,Action="AddNode",ExpressionClass="MaterialExpressionScalarParameter",ParameterName="Gain",DefaultValue="0.5")
    edit(mcp,"ManageAssetMaterial",path,Action="RenameParameterGroup",GroupName="None",NewGroupName="Compatibility")
    groups=cap_first(mcp.call("GetAssetMaterial",AssetPath=path,Sections=["ParameterGroups"]))
    assert "Compatibility" in json.dumps(groups),groups
    edit(mcp,"ManageAssetMaterial",path,Action="Layout")
    edit(mcp,"ManageAssetMaterial",path,Action="UngroupParameters",GroupName="Compatibility")
    edit(mcp,"ManageAssetMaterial",path,Action="DeleteUnused")
    graph=cap_first(mcp.call("GetAssetMaterial",AssetPath=path,Sections=["graph"]))
    assert "Gain" not in json.dumps(graph),graph


def isolated_edits():
    if os.environ.get("NEXUS_PERSISTENT_EDIT_FIXTURE")!="1":
        pytest.skip("Persistent project settings/plugin tests require an isolated writable host")


def test_typed_project_settings_persistence_and_validation(mcp,require_tools):
    isolated_edits();require_tools("GetProjectSettings","ManageProjectSettings")
    selector=dict(Container="Project",Category="Project",Section="General")
    before=cap_first(mcp.call("GetProjectSettings",**selector,Sections=["Values"],PropertyNames=["ProjectName"]))
    rows=merge_with_defaults(before["Values"],before.get("Values_defaults",{}));previous=rows[0]["JsonValue"]
    value="NexusCompatibility_"+uuid.uuid4().hex[:8]
    try:
        result=manage(mcp,"ManageProjectSettings",selector,dict(Action="SetProperties",Properties={"ProjectName":value}))
        assert result["bSavedToDisk"],result
        values=cap_first(mcp.call("GetProjectSettings",**selector,Sections=["Values"],PropertyNames=["ProjectName"]))
        assert values["Values"][0]["JsonValue"]==value,values
        bad=mcp.try_call("ManageProjectSettings",**selector,Operations=[dict(Action="SetProperties",Properties={"ProjectName":"MustNotCommit","__MissingField":True})])
        assert bad.get("isError"),bad
        current=cap_first(mcp.call("GetProjectSettings",**selector,Sections=["Values"],PropertyNames=["ProjectName"]))
        assert current["Values"][0]["JsonValue"]==value,current
        manage(mcp,"ManageProjectSettings",selector,dict(Action="Save"))
    finally:
        manage(mcp,"ManageProjectSettings",selector,dict(Action="SetProperties",Properties={"ProjectName":previous}))


def test_project_plugin_content_lifecycle(mcp,require_tools):
    isolated_edits();require_tools("ManageProjectPlugin","GetProjectPlugins")
    name="NexusContentFixture"+uuid.uuid4().hex[:8];selector=dict(PluginName=name)
    created=manage(mcp,"ManageProjectPlugin",selector,dict(Action="Create",Description="Isolated content fixture"))
    assert Path(created["DescriptorPath"]).is_file(),created
    manage(mcp,"ManageProjectPlugin",selector,dict(Action="UpdateDescriptor",Properties={"Description":"Updated fixture","Category":"Compatibility"}))
    info=cap_first(mcp.call("GetProjectPlugins",**selector,Sections=["Info"]))
    assert info["Info"]["Description"]=="Updated fixture",info
    manage(mcp,"ManageProjectPlugin",selector,dict(Action="AddDependency",DependencyName="NexusLink",bEnabled=True,bOptional=True))
    dependencies=cap_first(mcp.call("GetProjectPlugins",**selector,Sections=["Dependencies"]))
    assert "NexusLink" in json.dumps(dependencies),dependencies
    manage(mcp,"ManageProjectPlugin",selector,dict(Action="RemoveDependency",DependencyName="NexusLink"))
    result=manage(mcp,"ManageProjectPlugin",selector,dict(Action="SetEnabled",bEnabled=False))
    assert result["bRestartRequired"] and result["bSavedToDisk"],result
    bad=mcp.try_call("ManageProjectPlugin",PluginName="../Invalid",Operations=[dict(Action="Create")])
    assert bad.get("isError"),bad


def test_sequence_folder_lifecycle(mcp,require_tools,test_ns):
    require_tools("ControlEditorAnimation","GetEditorAnimation")
    path=f"{test_ns}/LS_Folders";mcp.call("CreateAssetLevelSequence",AssetPath=path)
    parameters=dict(sequence=reference(path),folder_name="Compatibility")
    editor(mcp,"ControlEditorAnimation",Action="AddSequenceFolder",Parameters=parameters)
    data=editor(mcp,"GetEditorAnimation",Action="SequenceFolders",Parameters={"sequence":reference(path)})
    assert data["Items"][0]["Name"]=="Compatibility",data
    editor(mcp,"ControlEditorAnimation",Action="RemoveSequenceFolder",Parameters=parameters)
    assert not editor(mcp,"GetEditorAnimation",Action="SequenceFolders",Parameters={"sequence":reference(path)})["Items"]


def test_sequence_fbx_export(mcp,require_tools,test_ns,pytestconfig):
    isolated_edits();require_tools("ControlEditorAnimation","GetEditorAnimation","ExecPython")
    path=f"{test_ns}/LS_Fbx";mcp.call("CreateAssetLevelSequence",AssetPath=path)
    fixture=cap_first(mcp.call("ExecPython",Code=f"import unreal,json\nfbx_actor=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CameraActor,unreal.Vector())\nfbx_sequence=unreal.load_asset('{path}')\nfbx_binding=fbx_sequence.add_possessable(fbx_actor)\nprint(json.dumps({{'world':unreal.EditorLevelLibrary.get_editor_world().get_path_name(),'guid':fbx_binding.get_id().to_string()}}))"))
    data=json.loads(fixture["Output"].strip().splitlines()[-1])
    output=Path(pytestconfig.getoption("--uproject")).resolve().parent/"Saved"/("NexusFbx_"+uuid.uuid4().hex+".fbx")
    try:
        parameters=dict(world={"refPath":data["world"]},sequence=reference(path),bindings=[{"binding_id":data["guid"],"sequence":reference(path)}],fbx_file_path=str(output))
        editor(mcp,"ControlEditorAnimation",Action="ExportFbx",Parameters=parameters)
        assert output.is_file() and output.stat().st_size>0
        settings=cap_first(mcp.call("ExecPython",Code="fbx_import_settings=unreal.MovieSceneUserImportFBXSettings()\nprint(fbx_import_settings.get_path_name())"))["Output"].strip().splitlines()[-1]
        editor(mcp,"ControlEditorAnimation",Action="ImportFbx",Parameters=dict(parameters,import_settings={"refPath":settings}))
    finally:
        mcp.call("ExecPython",Code="unreal.EditorLevelLibrary.destroy_actor(fbx_actor)")


@pytest.mark.skipif_ue_below("5.5")
def test_sequence_conditions(mcp,require_tools,test_ns):
    require_tools("ControlEditorAnimation","GetEditorAnimation")
    path=f"{test_ns}/LS_Conditions";mcp.call("CreateAssetLevelSequence",AssetPath=path)
    track=editor(mcp,"ControlEditorAnimation",Action="AddSequenceTrack",Parameters={"sequence":reference(path),"track_type":{"refPath":"/Script/MovieSceneTracks.MovieSceneSlomoTrack"}})
    section=editor(mcp,"ControlEditorAnimation",Action="AddSection",Parameters={"track":track})
    condition="/Script/MovieScene.MovieSceneGroupCondition"
    editor(mcp,"ControlEditorAnimation",Action="SetSectionCondition",Parameters={"section":section,"condition_class":condition})
    value=editor(mcp,"GetEditorAnimation",Action="GetSectionCondition",Parameters={"section":section})
    assert condition in json.dumps(value),value
    editor(mcp,"ControlEditorAnimation",Action="ClearSectionCondition",Parameters={"section":section})
    assert condition not in json.dumps(editor(mcp,"GetEditorAnimation",Action="GetSectionCondition",Parameters={"section":section}))


@pytest.mark.skipif_ue_below("5.8")
def test_native_mixer_layers(mcp,require_tools,test_ns):
    require_tools("ControlEditorAnimation","GetEditorAnimation")
    path=f"{test_ns}/LS_Mixer";mcp.call("CreateAssetLevelSequence",AssetPath=path)
    track=editor(mcp,"ControlEditorAnimation",Action="AddSequenceTrack",Parameters={"sequence":reference(path),"track_type":{"refPath":"/Script/MovieSceneAnimMixer.MovieSceneAnimationMixerTrack"}})
    layer=editor(mcp,"ControlEditorAnimation",Action="MixerAddMixerLayer",Parameters={"track":track})
    editor(mcp,"ControlEditorAnimation",Action="MixerSetLayerName",Parameters={"layer":layer,"name":"CompatibilityLayer"})
    data=editor(mcp,"GetEditorAnimation",Action="MixerGetLayerName",Parameters={"layer":layer})
    assert "CompatibilityLayer" in json.dumps(data),data


@pytest.mark.requires_gui
@pytest.mark.skipif_ue_below("5.8")
def test_native_sequence_outliner_and_binding_conversion(mcp,require_tools,test_ns):
    require_tools("ControlEditorAnimation","GetEditorAnimation")
    path=f"{test_ns}/LS_Outliner";mcp.call("CreateAssetLevelSequence",AssetPath=path)
    mcp.call("ExecPython",Code=f"import unreal\noutliner_actor=unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CameraActor,unreal.Vector())\noutliner_actor_path=outliner_actor.get_path_name()\nunreal.load_asset('{path}').add_possessable(outliner_actor)")
    try:
        editor(mcp,"ControlEditorAnimation",Action="OpenSequence",Parameters={"sequence":reference(path)})
        tree=editor(mcp,"GetEditorAnimation",Action="GetOutlinerTree",Parameters={})
        assert tree,tree
        bindings=editor(mcp,"GetEditorAnimation",Action="Bindings",Parameters={"sequence":reference(path)})["Items"]
        assert bindings,bindings
        binding=bindings[0]
        editor(mcp,"ControlEditorAnimation",Action="ConvertToSpawnable",Parameters={"binding":binding})
    finally:
        editor(mcp,"ControlEditorAnimation",Action="CloseSequence",Parameters={})
        mcp.call("ExecPython",Code="outliner_original=unreal.find_object(None,outliner_actor_path)\nif outliner_original: unreal.EditorLevelLibrary.destroy_actor(outliner_original)")
