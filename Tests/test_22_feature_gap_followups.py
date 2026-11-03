# Copyright byteyang. All Rights Reserved.
"""功能缺口首批闭环：发现、结构计划、导入、多人、PCG、姿态、任务和源控。"""
import struct
import time
import wave
import zlib

import pytest

from _framework.asset_helpers import first_asset_path
from _framework.mcp_client import cap_first, cap_entries
from _framework.assertions import merge_with_defaults
from test_15_editor_operations import operation_result
from test_20_editor_compatibility import editor


def test_gap_action_schema_discovery(mcp, require_tools):
    require_tools("GetProjectToolsets")
    rows = cap_first(mcp.call("GetProjectToolsets", Sections=["Actions"],
                             Capability="ControlEditorAnimation", Action="AddFloatKey"))["Actions"]
    assert len(rows) == 1, rows
    action = rows[0]
    assert action["bSupported"] and action["Backend"] in ("EngineCompatibility", "OfficialToolset"), action
    schema = action["InputSchema"]
    assert {"section", "channel_name", "frame", "value"} <= schema["properties"].keys(), schema
    assert action["MinimumVersion"] and action["Prerequisites"], action
    rows = cap_first(mcp.call("GetProjectToolsets", Sections=["Actions"],
                             Capability="ControlEditorNiagara", Action="SetStackInputData"))["Actions"]
    assert len(rows) == 1 and isinstance(rows[0]["bSupported"], bool) and rows[0]["Reason"], rows
    for name, compatibility_minimum in (("SetSectionCondition", "5.5"), ("MixerAddMixerLayer", "5.8")):
        row = cap_first(mcp.call("GetProjectToolsets", Sections=["Actions"], Capability="ControlEditorAnimation", Action=name))["Actions"][0]
        assert row["MinimumVersion"] == ("5.8" if row["Backend"] == "OfficialToolset" else compatibility_minimum), row


def test_gap_widget_sequential_plan_and_preconditions(mcp, require_tools, test_ns):
    require_tools("GetAssetEditPreview", "CreateAssetUserWidget")
    path = f"{test_ns}/WBP_StructuralPlan"
    mcp.call("CreateAssetUserWidget", AssetPath=path)
    operations = [{"Action": "Add", "WidgetName": "Root", "WidgetClass": "CanvasPanel"},
                  {"Action": "Add", "WidgetName": "Label", "WidgetClass": "TextBlock", "ParentWidget": "Root"}]
    plan = mcp.call("GetAssetEditPreview", AssetPath=path, Capability="ManageAssetUserWidget", Operations=operations)
    assert all(entry["bValid"] for entry in cap_entries(plan)), plan
    assert len(plan["Added"]) == 2 and not plan["Removed"], plan
    empty = mcp.call("GetAssetEditPreview", AssetPath=path, Capability="ManageAssetUserWidget", Operations=operations)
    assert empty["StructureHash"] == plan["StructureHash"], empty
    written = mcp.call("ManageAssetUserWidget", AssetPath=path, ExpectedStructureHash=plan["StructureHash"],
                       bVerifyStructure=True, Operations=operations)
    assert all(entry["bStructureVerified"] for entry in cap_entries(written)), written
    rejected = mcp.try_call("ManageAssetUserWidget", AssetPath=path, ExpectedStructureHash=plan["StructureHash"],
                           Operations=[{"Action": "Remove", "WidgetName": "Root"}])
    assert rejected.get("isError"), rejected
    removal = mcp.call("GetAssetEditPreview", AssetPath=path, Capability="ManageAssetUserWidget",
                       Operations=[{"Action": "Remove", "WidgetName": "Root"}])
    assert len(removal["Removed"]) == 2, removal


def test_gap_scalar_preview_keeps_existing_batch_size(mcp, require_tools, test_ns):
    require_tools("GetAssetEditPreview", "CreateAssetBlueprint")
    path = f"{test_ns}/BP_LargeScalarPreview"
    mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="Actor")
    operation = {"Action": "SetDefaults", "PropertyPath": "bCanBeDamaged", "Value": "false"}
    result = mcp.call("GetAssetEditPreview", AssetPath=path, Capability="ManageAssetBlueprint", Operations=[operation] * 129)
    rows = merge_with_defaults(result["Results"], result.get("Results_defaults", {}))
    assert len(rows) == 129 and all(row["bValid"] for row in rows), result


def test_gap_pcg_structural_plan_and_readback(mcp, require_tools, test_ns):
    require_tools("CreateAssetPCGGraph", "ManageAssetPCGGraph")
    path = f"{test_ns}/PCG_StructuralPlan"
    mcp.call("CreateAssetPCGGraph", AssetPath=path)
    operation = {"Action": "AddNode", "SettingsClass": "PCGTransformPointsSettings"}
    plan = mcp.call("GetAssetEditPreview", AssetPath=path, Capability="ManageAssetPCGGraph", Operations=[operation])
    assert cap_first(plan)["bValid"] and len(plan["Added"]) == 1, plan
    written = cap_first(mcp.call("ManageAssetPCGGraph", AssetPath=path, bVerifyStructure=True,
                                 ExpectedStructureHash=plan["StructureHash"], Operations=[operation]))
    assert written["bStructureVerified"], written
    node = written["NodeId"]
    removed = cap_first(mcp.call("ManageAssetPCGGraph", AssetPath=path, bVerifyStructure=True,
                                Operations=[{"Action": "RemoveNode", "NodeId": node}]))
    assert removed["bStructureVerified"], removed


def test_gap_blueprint_remove_plan(mcp, require_tools, test_ns):
    require_tools("CreateAssetBlueprint", "GetAssetEditPreview")
    path = f"{test_ns}/BP_StructuralPlan"
    mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="Actor")
    mcp.call("ManageAssetBlueprint", AssetPath=path, Operations=[{"Action": "AddFunction", "FunctionName": "Plan"}])
    added = cap_first(mcp.call("ManageAssetBlueprint", AssetPath=path, Operations=[
        {"Action": "AddNode", "GraphName": "Plan", "NodeClass": "K2Node_ExecutionSequence"}]))
    operation = {"Action": "RemoveNode", "GraphName": "Plan", "NodeId": added["NodeId"]}
    plan = mcp.call("GetAssetEditPreview", AssetPath=path, Capability="ManageAssetBlueprint", Operations=[operation])
    assert cap_first(plan)["bValid"] and plan["Removed"], plan
    actual = cap_first(mcp.call("ManageAssetBlueprint", AssetPath=path, bVerifyStructure=True,
                                ExpectedStructureHash=plan["StructureHash"], Operations=[operation]))
    assert actual["bStructureVerified"], actual


@pytest.mark.parametrize("kind", ["Texture", "SoundWave"])
def test_gap_first_import_and_conflicts(mcp, require_tools, test_ns, tmp_path, kind):
    require_tools("ImportAsset")
    source = tmp_path / ("source.png" if kind == "Texture" else "source.wav")
    if kind == "Texture":
        def chunk(tag, data):
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
        source.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 6, 0, 0, 0)) +
                           chunk(b"IDAT", zlib.compress((b"\x00" + b"\xff\x00\x00\xff" * 8) * 8)) + chunk(b"IEND", b""))
    else:
        with wave.open(str(source), "wb") as output:
            output.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
            output.writeframes(b"\x00\x00" * 2205)
    arguments = dict(SourceFile=str(source), DestinationPath=test_ns, AssetName="Imported_" + kind, AssetType=kind)
    first = cap_first(mcp.call("ImportAsset", **arguments))
    assert first["bVerified"] and not first["bSaved"] and first["Path"].startswith(test_ns), first
    failed = mcp.try_call("ImportAsset", **arguments)
    assert failed.get("isError"), failed
    unique = cap_first(mcp.call("ImportAsset", **arguments, ConflictPolicy="Unique"))
    assert unique["Path"] != first["Path"], unique
    replacement = cap_first(mcp.call("ImportAsset", **arguments, ConflictPolicy="Replace"))
    assert replacement["Path"] == first["Path"], replacement


@pytest.mark.skipif_ue_below("5.2")
def test_gap_bone_pose_sampling(mcp, require_tools):
    require_tools("GetAssetAnimSequence")
    path = first_asset_path(mcp, "AnimSequence", path_filter="/Game/Characters/")
    assert path, "Animation fixture unavailable"
    metadata = cap_first(mcp.call("GetAssetAnimSequence", AssetPath=path))
    skeleton = cap_first(mcp.call("GetAssetSkeleton", AssetPath=metadata["Skeleton"]))
    bones = skeleton.get("Bones") or skeleton.get("Hierarchy") or []
    # 从实际骨架发现根骨骼，不依赖模板骨骼名称。
    bone = (bones[0].get("Name") or bones[0].get("name") or bones[0].get("BoneName")) if bones else None
    assert bone, skeleton
    sample = cap_first(mcp.call("GetAssetAnimSequence", AssetPath=path, BoneNames=[bone], SampleTimes=[0, 0.01]))
    assert sample["SampleSpace"] == "Local" and len(sample["BoneSamples"]) == 2, sample
    assert len(sample["BoneSamples"][0]["RotationQuaternion"]) == 4, sample
    assert mcp.try_call("GetAssetAnimSequence", AssetPath=path, BoneNames=[bone], SampleTimes=[-1]).get("isError")


def test_gap_first_fbx_import(mcp, require_tools, test_ns, tmp_path):
    require_tools("ImportAsset", "ExecPython")
    path = first_asset_path(mcp, "StaticMesh", path_filter="/Game/LevelPrototyping/")
    assert path, "StaticMesh export fixture unavailable"
    source = str(tmp_path / "mesh.fbx")
    mcp.call("ExecPython", Code="import unreal\n"
             "task=unreal.AssetExportTask()\n"
             f"task.object=unreal.load_asset({path!r})\n"
             f"task.filename={source!r}\n"
             "task.automated=True\ntask.prompt=False\ntask.replace_identical=True\n"
             "task.exporter=unreal.StaticMeshExporterFBX()\n"
             "task.options=unreal.FbxExportOption()\n"
             "assert unreal.Exporter.run_asset_export_task(task)")
    result = cap_first(mcp.call("ImportAsset", SourceFile=source, DestinationPath=test_ns,
                               AssetName="SM_FirstImport", AssetType="StaticMesh"))
    assert result["AssetClass"] == "StaticMesh" and result["bVerified"], result


@pytest.mark.parametrize("kind", ["SkeletalMesh", "AnimSequence"])
@pytest.mark.requires_gui
def test_gap_first_skeleton_fbx_import(mcp, require_tools, test_ns, tmp_path, kind):
    require_tools("ImportAsset", "ExecPython", "DuplicateAsset")
    path = first_asset_path(mcp, kind, path_filter="/Game/Characters/")
    assert path, f"{kind} export fixture unavailable"
    metadata = cap_first(mcp.call("GetAsset" + kind, AssetPath=path))
    skeleton = f"{test_ns}/SK_Import_{kind}"
    mcp.call("DuplicateAsset", AssetPath=metadata["Skeleton"], DestAssetPath=skeleton)
    source = str(tmp_path / "skeleton.fbx")
    exporter = "SkeletalMeshExporterFBX" if kind == "SkeletalMesh" else "AnimSequenceExporterFBX"
    mcp.call("ExecPython", Code="import unreal\n"
             "task=unreal.AssetExportTask()\n"
             f"task.object=unreal.load_asset({path!r})\n"
             f"task.filename={source!r}\n"
             "task.automated=True\ntask.prompt=False\ntask.replace_identical=True\n"
             f"task.exporter=unreal.{exporter}()\n"
             "task.options=unreal.FbxExportOption()\n"
             "task.options.level_of_detail=False\n"
             "assert unreal.Exporter.run_asset_export_task(task)")
    result = cap_first(mcp.call("ImportAsset", SourceFile=source, DestinationPath=test_ns,
                               AssetName="FirstImport_" + kind, AssetType=kind, SkeletonPath=skeleton))
    assert result["AssetClass"] == kind and result["bVerified"], result
    assert result["Path"] == f"{test_ns}/FirstImport_{kind}.FirstImport_{kind}", result
    readback = cap_first(mcp.call("GetAsset" + kind, AssetPath=result["Path"]))
    assert readback["Skeleton"].startswith(skeleton), readback


def test_gap_owned_task_history(mcp, require_tools):
    require_tools("GetEditorOperation", "ControlEditorOperation", "GetEditorPCG")
    created = cap_first(mcp.call("GetEditorPCG", Action="Instances"))
    operation_result(mcp, created)
    recent = cap_first(mcp.call("GetEditorOperation", Limit=128))
    rows = merge_with_defaults(recent["Operations"], recent.get("Operations_defaults", {}))
    matching = [row for row in rows if row["OperationId"] == created["OperationId"]]
    assert len(matching) == 1 and matching[0]["bHasResult"] and "Result" not in matching[0], recent
    assert mcp.try_call("ControlEditorOperation", OperationId=created["OperationId"]).get("isError")
    assert mcp.try_call("ControlEditorOperation", OperationId="unknown").get("isError")


def test_gap_schema_dump_and_owner_isolation(mcp, require_tools):
    require_tools("ControlEditorAutomation")
    operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Discover"))
    names = ["NexusLink.Smoke.PluginAndRegistry.SchemaDump", "NexusLink.EditorOperations.OwnerAndContract"]
    results = operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Run", TestNames=names))
    assert len(results["Tests"]) == 2, results
    assert all(test["Outcome"] == "Passed" for test in results["Tests"]), results


def test_gap_source_control_preflight(mcp, require_tools, test_ns):
    require_tools("GetAssetSourceControl")
    path = f"{test_ns}/DA_SourceControl"
    mcp.call("CreateAssetDataAsset", AssetPath=path, ParentClass="PrimaryAssetLabel")
    mcp.call("SaveAsset", AssetPath=path)
    result = cap_first(mcp.call("GetAssetSourceControl", AssetPaths=[path]))
    assert "bReadOnly" in result and "bStatusKnown" in result and result["FilePath"], result
    assert mcp.try_call("GetAssetSourceControl", AssetPaths=[f"{test_ns}/Missing"]).get("isError")


@pytest.mark.requires_gui
def test_gap_compat_pcg_execute_and_points(mcp, require_tools, test_ns):
    require_tools("ControlEditorPCG", "GetEditorPCG", "CreateAssetPCGGraph")
    path = f"{test_ns}/PCG_PointReadback"
    mcp.call("CreateAssetPCGGraph", AssetPath=path)
    mcp.call("ManageAssetPCGGraph", AssetPath=path, Operations=[{"Action": "AddNode", "SettingsClass": "PCGCreatePointsGridSettings"}])
    graph = cap_first(mcp.call("GetAssetPCGGraph", AssetPath=path))
    grid = graph["Nodes"][0]
    mcp.call("ManageAssetPCGGraph", AssetPath=path, bVerifyStructure=True, Operations=[{
        "Action": "AddEdge", "FromNodeId": grid["Id"], "FromPin": grid["OutputPins"][0],
        "ToNodeId": graph["OutputNode"]["Id"], "ToPin": graph["OutputNode"]["InputPins"][0]}])
    spawned = editor(mcp, "ControlEditorPCG", Action="Spawn", AssetPath=path, ActorName="NexusPcgGapProbe")
    actor = spawned.get("ActorPath")
    if not actor:
        pytest.skip("Native backend has a different actor-reference envelope; covered by native PCG tests")
    try:
        editor(mcp, "ControlEditorPCG", Action="Execute", ActorPath=actor)
        data = editor(mcp, "GetEditorPCG", Action="NodeData", ActorPath=actor, NodePath=grid["Path"], PinLabel=grid["OutputPins"][0], Limit=2)
        assert 0 < data["Returned"] <= 2 and data["Total"] >= data["Returned"], data
        assert "Density" in merge_with_defaults(data["Items"], data.get("Items_defaults", {}))[0], data
    finally:
        mcp.call("ExecPython", Code=f"import unreal\na=unreal.find_object(None,{actor!r})\nif a: unreal.EditorLevelLibrary.destroy_actor(a)")


@pytest.mark.requires_gui
@pytest.mark.l4_runtime
def test_gap_multiplayer_pie_worlds(mcp, require_tools):
    require_tools("ControlPie")
    mcp.call("ControlPie", Action="Stop") if cap_first(mcp.call("ControlPie", Action="Status"))["bIsPIERunning"] else None
    mcp.call("ControlPie", Action="Start", NetMode="ListenServer", NumberOfClients=2, bRunUnderOneProcess=True)
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            status = cap_first(mcp.call("ControlPie", Action="Status"))
            if len(status.get("PlayWorlds", [])) >= 2: break
            time.sleep(.2)
        modes = {world["NetMode"] for world in status.get("PlayWorlds", [])}
        assert {"ListenServer", "Client"} <= modes, status
    finally:
        mcp.call("ControlPie", Action="Stop")
