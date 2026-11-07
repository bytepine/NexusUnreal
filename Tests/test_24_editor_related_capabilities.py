# Copyright byteyang. All Rights Reserved.
"""待发布关联能力：类型回读、预览、导出、编辑器生命周期与 AI 状态。"""
import pytest
from _framework.mcp_client import cap_first
from _framework.runtime_helpers import spawn_runtime_actors, destroy_runtime_actors
from test_15_editor_operations import operation_result


def test_related_blueprint_renames_and_component_reset(mcp, require_tools, test_ns):
    require_tools("CreateAssetBlueprint", "ManageAssetBlueprint", "GetAssetBlueprint")
    parent, child = f"{test_ns}/BP_ResetParent", f"{test_ns}/BP_ResetChild"
    mcp.call("CreateAssetBlueprint", AssetPath=parent, ParentClass="Actor")
    mcp.call("ManageAssetBlueprint", AssetPath=parent, bCompile=True, Operations=[
        {"Action": "AddVariable", "VariableName": "Original", "VariableType": "int", "DefaultValue": "17"},
        {"Action": "AddFunction", "FunctionName": "Compute"},
        {"Action": "AddComponent", "ComponentName": "Probe", "ComponentClass": "SceneComponent"},
    ])
    mcp.call("ManageAssetBlueprint", AssetPath=parent, bCompile=True, Operations=[
        {"Action": "AddLocalVariable", "FunctionName": "Compute", "VariableName": "LocalValue", "VariableType": "int"},
        {"Action": "SetComponentProperty", "ComponentName": "Probe", "PropertyPath": "RelativeLocation.X", "Value": "31"},
    ])
    before = cap_first(mcp.call("GetAssetBlueprint", AssetPath=parent, Sections=["Variable", "Function"]))
    member = next(item for item in before["Variables"] if item["Name"] == "Original")
    local = next(item for item in before["Functions"] if item["Name"] == "Compute")["LocalVariables"][0]
    mcp.call("ManageAssetBlueprint", AssetPath=parent, bCompile=True, Operations=[
        {"Action": "RenameVariable", "VariableName": "Original", "NewVariableName": "Renamed"},
        {"Action": "RenameLocalVariable", "FunctionName": "Compute", "VariableName": "LocalValue", "NewVariableName": "RenamedLocal"},
    ])
    after = cap_first(mcp.call("GetAssetBlueprint", AssetPath=parent, Sections=["Variable", "Function"]))
    renamed = next(item for item in after["Variables"] if item["Name"] == "Renamed")
    renamed_local = next(item for item in after["Functions"] if item["Name"] == "Compute")["LocalVariables"][0]
    assert renamed["Guid"] == member["Guid"] and renamed_local["Guid"] == local["Guid"], after
    assert renamed_local["Name"] == "RenamedLocal" and all(item["Name"] != "Original" for item in after["Variables"]), after
    mcp.call("CreateAssetBlueprint", AssetPath=child, ParentClass=parent)
    mcp.call("ManageAssetBlueprint", AssetPath=child, bVerify=True, Operations=[
        {"Action": "SetComponentProperty", "ComponentName": "Probe", "PropertyPath": "RelativeLocation.X", "Value": "72", "ExpectedValue": "31"},
    ])
    mcp.call("ManageAssetBlueprint", AssetPath=child, Operations=[
        {"Action": "ResetComponentPropertyToDefault", "ComponentName": "Probe", "PropertyPath": "RelativeLocation.X", "Baseline": "ParentTemplate"},
    ])
    reset = cap_first(mcp.call("GetAssetBlueprint", AssetPath=child, Sections=["Component"], ComponentName="Probe",
                               Baseline="ParentTemplate", PropertyPaths=["RelativeLocation.X"]))["Properties"][0]
    assert float(reset["Value"]) == 31 and not reset["bDiffersFromDefault"], reset


def test_related_level_actor_properties_and_reset(mcp, require_tools, test_ns):
    require_tools("CreateAssetLevel", "ManageAssetLevel", "GetAssetLevel")
    path = f"{test_ns}/LV_ActorDefaults"
    mcp.call("CreateAssetLevel", AssetPath=path)
    mcp.call("ManageAssetLevel", AssetPath=path, Operations=[{"Action": "SpawnActor", "ClassName": "Actor"}])
    actor = cap_first(mcp.call("GetAssetLevel", AssetPath=path, Sections=["Actors"]))["Actors"]
    name = next(item["Name"] for item in actor if item["Class"] == "Actor")
    mcp.call("ManageAssetLevel", AssetPath=path, bVerify=True, Operations=[
        {"Action": "SetActorProperty", "ActorName": name, "PropertyPath": "InitialLifeSpan", "Value": "12"},
    ])
    changed = cap_first(mcp.call("GetAssetLevel", AssetPath=path, Sections=["ActorProperties"], ActorName=name,
                                 PropertyPaths=["InitialLifeSpan"]))["Properties"][0]
    assert float(changed["Value"]) == 12 and changed["bDiffersFromDefault"], changed
    mcp.call("ManageAssetLevel", AssetPath=path, Operations=[
        {"Action": "ResetActorPropertyToDefault", "ActorName": name, "PropertyPath": "InitialLifeSpan"},
    ])
    reset = cap_first(mcp.call("GetAssetLevel", AssetPath=path, Sections=["ActorProperties"], ActorName=name,
                               PropertyPaths=["InitialLifeSpan"]))["Properties"][0]
    assert reset["Value"] == reset["DefaultValue"] and not reset["bDiffersFromDefault"], reset


def test_related_variable_type_roundtrip(mcp, require_tools, test_ns):
    require_tools("CreateAssetBlueprint", "ManageAssetBlueprint", "GetAssetBlueprint", "GetAssetEditPreview")
    path = f"{test_ns}/BP_RelatedTypes"
    mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="Actor")
    mcp.call("ManageAssetBlueprint", AssetPath=path, bCompile=True,
             Operations=[{"Action": "AddVariable", "VariableName": "Items", "VariableType": "Map<name,vector>"}])
    mcp.call("SearchAsset", AssetType="Blueprint", PathFilter=test_ns)
    variables = cap_first(mcp.call("GetAssetBlueprint", AssetPath=path, Sections=["Variable"]))["Variables"]
    variable = next(value for value in variables if value["Name"] == "Items")
    assert variable["ContainerType"] == "Map" and variable["KeyType"] == "name", variable
    assert variable["ValueTypeObjectPath"].endswith(".Vector") and variable["Guid"], variable
    preview = cap_first(mcp.call("GetAssetEditPreview", AssetPath=path, Capability="ManageAssetBlueprint",
                                Operations=[{"Action": "ChangeVariableType", "VariableName": "Items", "VariableType": "int"}]))
    assert preview["bValid"] and preview["bPotentialDataLoss"], preview
    mcp.call("ManageAssetBlueprint", AssetPath=path, bCompile=True,
             Operations=[{"Action": "ChangeVariableType", "VariableName": "Items", "VariableType": "int", "bAllowPotentialDataLoss": True}])


def test_related_dataasset_preview(mcp, require_tools, test_ns):
    require_tools("CreateAssetDataAsset", "GetAssetEditPreview", "ManageAssetDataAsset")
    path = f"{test_ns}/DA_Related"
    mcp.call("CreateAssetDataAsset", AssetPath=path, ParentClass="NexusRelatedDataAsset")
    operation = {"Action": "Set", "PropertyName": "Label", "Value": "after", "ExpectedValue": "before"}
    preview = cap_first(mcp.call("GetAssetEditPreview", AssetPath=path, Capability="ManageAssetDataAsset", Operations=[operation]))
    assert preview["bValid"] and preview["CurrentValue"] == "before", preview
    written = cap_first(mcp.call("ManageAssetDataAsset", AssetPath=path, bVerify=True, Operations=[operation]))
    assert written["bVerified"] and written["ReadbackValue"] == "after", written
    assert mcp.try_call("ManageAssetDataAsset", AssetPath=path, bVerify=True, Operations=[operation]).get("isError")


def test_related_struct_type_metadata(mcp, require_tools, test_ns):
    require_tools("CreateAssetStruct", "GetAssetStruct")
    path = f"{test_ns}/ST_TypeMetadata"
    mcp.call("CreateAssetStruct", AssetPath=path)
    mcp.call("SearchAsset", AssetType="UserDefinedStruct", PathFilter=test_ns)
    fields = cap_first(mcp.call("GetAssetStruct", AssetPath=path))["Fields"]
    assert fields, fields
    assert all(field["ContainerType"] == "None" and field["CanonicalType"] and field["Guid"] for field in fields), fields


def test_related_scientific_numeric_text(mcp, require_tools, test_ns):
    require_tools("CreateAssetDataAsset", "GetAssetEditPreview", "ManageAssetDataAsset")
    path = f"{test_ns}/DA_NumericText"
    mcp.call("CreateAssetDataAsset", AssetPath=path, ParentClass="NexusRelatedDataAsset")
    operation = {"Action": "Set", "PropertyName": "Location.X", "Value": "1e3", "ExpectedValue": "0e0"}
    preview = cap_first(mcp.call("GetAssetEditPreview", AssetPath=path, Capability="ManageAssetDataAsset", Operations=[operation]))
    assert preview["bValid"] and float(preview["CurrentValue"]) == 0 and float(preview["TargetValue"]) == 1000, preview
    written = cap_first(mcp.call("ManageAssetDataAsset", AssetPath=path, bVerify=True, Operations=[operation]))
    assert written["bVerified"] and float(written["ReadbackValue"]) == 1000, written
    invalid = {"Action": "Set", "PropertyName": "Location.X", "Value": "1e3junk"}
    assert mcp.try_call("ManageAssetDataAsset", AssetPath=path, Operations=[invalid]).get("isError")
    preview = cap_first(mcp.call("GetAssetEditPreview", AssetPath=path, Capability="ManageAssetDataAsset",
                                Operations=[{**invalid, "Value": "2e3"}]))
    assert preview["bValid"] and float(preview["CurrentValue"]) == 1000, preview


def test_related_export_discovery_and_dry_run(mcp, require_tools, test_ns, tmp_path):
    require_tools("GetAssetExportOptions", "ExportAsset", "CreateAssetDataAsset")
    path = f"{test_ns}/DA_Export"
    mcp.call("CreateAssetDataAsset", AssetPath=path, ParentClass="NexusRelatedDataAsset")
    formats = cap_first(mcp.call("GetAssetExportOptions", AssetPath=path))
    assert formats["bExportAvailable"] and formats["Formats"], formats
    extension = next(item["Extension"] for item in formats["Formats"] if item["Extension"] == "t3d")
    destination = tmp_path / "not-created" / f"export.{extension}"
    preview = cap_first(mcp.call("ExportAsset", AssetPath=path, OutputPath=str(destination), bValidateOnly=True))
    assert preview["bValidateOnly"] and not preview["bWritten"], preview
    assert not destination.parent.exists()
    destination.parent.mkdir()
    destination.write_bytes(b"original")
    failed = mcp.try_call("ExportAsset", AssetPath=path, OutputPath=str(destination), ConflictPolicy="Fail")
    assert failed.get("isError") and destination.read_bytes() == b"original", failed
    unique = cap_first(mcp.call("ExportAsset", AssetPath=path, OutputPath=str(destination), ConflictPolicy="Unique"))
    unique_path = destination.with_stem(destination.stem + "_1")
    assert unique["bWritten"] and unique_path.is_file() and destination.read_bytes() == b"original", unique
    expected = unique_path.read_bytes()
    assert b"Begin Object" in expected
    replaced = cap_first(mcp.call("ExportAsset", AssetPath=path, OutputPath=str(destination), ConflictPolicy="Replace"))
    assert replaced["bWritten"] and destination.read_bytes() == expected, replaced


def test_related_navigation_point(mcp, require_tools):
    require_tools("GetNavigationPoint")
    result = cap_first(mcp.call("GetNavigationPoint", World="Editor", Point={"X": 0, "Y": 0, "Z": 100}))
    assert isinstance(result["bProjected"], bool) and isinstance(result["bNavigationAvailable"], bool), result
    assert result["WorldType"] == "Editor", result


@pytest.mark.requires_gui
def test_related_editor_list_and_safe_close(mcp, require_tools, test_ns):
    require_tools("ControlEditorAssetEditor", "GetEditorContext", "CreateAssetBlueprint", "ManageAssetBlueprint", "SaveAsset")
    path = f"{test_ns}/BP_Lifecycle"
    other = f"{test_ns}/BP_UnrelatedEditor"
    mcp.call("CreateAssetBlueprint", AssetPath=other, ParentClass="Actor")
    mcp.call("CompileBlueprint", AssetPath=other, bSaveToDisk=True)
    assert cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=other))["bIsOpen"]
    mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="Actor")
    mcp.call("ManageAssetBlueprint", AssetPath=path, Operations=[{"Action": "AddVariable", "VariableName": "Probe", "VariableType": "int"}])
    opened = cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=path))
    assert opened["bIsOpen"], opened
    editors = cap_first(mcp.call("GetEditorContext", Sections=["AssetEditors"]))
    assert any(item["AssetPath"].split(".")[0] == path for item in editors["Assets"]), editors
    rejected = mcp.try_call("ControlEditorAssetEditor", AssetPath=path, Action="Close")
    assert rejected.get("isError"), rejected
    mcp.call("CompileBlueprint", AssetPath=path, bSaveToDisk=True)
    closed = cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=path, Action="Close"))
    assert not closed["bIsOpen"], closed
    assert cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=other, Action="Status"))["bIsOpen"]
    assert not cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=other, Action="Close"))["bIsOpen"]


@pytest.mark.requires_gui
def test_related_shared_editor_protection(mcp, require_tools):
    require_tools("ControlEditorAutomation")
    operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Discover"))
    result = operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Run", TestNames=["NexusLink.EditorGaps.SharedEditorProtection"]))
    assert result["Tests"][0]["Outcome"] == "Passed", result


@pytest.mark.requires_gui
def test_related_behavior_tree_editor_reopen(mcp, require_tools, test_ns):
    require_tools("CreateAssetBehaviorTree", "ManageAssetBehaviorTree", "ControlEditorAssetEditor", "SaveAsset")
    path = f"{test_ns}/BT_Lifecycle"
    mcp.call("CreateAssetBehaviorTree", AssetPath=path)
    assert cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=path))["bIsOpen"]
    changed = mcp.call("ManageAssetBehaviorTree", AssetPath=path, bSaveToDisk=True,
                       Operations=[{"Action": "SetRoot", "NodeClass": "BTComposite_Sequence"}])
    assert changed["bEditorClosed"], changed
    reopened = cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=path))
    assert reopened["bIsOpen"], reopened
    mcp.call("SaveAsset", AssetPath=path)
    assert not cap_first(mcp.call("ControlEditorAssetEditor", AssetPath=path, Action="Close"))["bIsOpen"]


@pytest.mark.requires_gui
def test_related_runtime_ai_status_and_stop(mcp, require_tools, pie):
    require_tools("SpawnRuntimeActor", "GetRuntimeActorAI", "InteractRuntimeActorAI", "DestroyRuntimeActor")
    actors = spawn_runtime_actors(mcp, [{"ClassName": "AIController"}])
    assert len(actors) == 1
    try:
        state = cap_first(mcp.call("GetRuntimeActorAI", ActorName=actors[0]))
        assert state["bHasAIController"] and state["MoveStatus"] == "Idle", state
        stopped = cap_first(mcp.call("InteractRuntimeActorAI", ActorName=actors[0], Action="Stop"))
        assert stopped["MoveStatus"] == "Idle", stopped
    finally:
        destroy_runtime_actors(mcp, actors)
