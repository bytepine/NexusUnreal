# Copyright byteyang. All Rights Reserved.
"""导航诊断、实时碰撞与逐帧只读批次的反馈回归。"""
import json
import time
from pathlib import Path
import uuid

import pytest
from _framework.mcp_client import cap_first
from _framework.assertions import merge_with_defaults
from test_15_editor_operations import operation_result


def test_feedback_navigation_scene_diagnostics(mcp, require_tools):
    require_tools("GetEditorScene", "GetEditorOperation")
    status = operation_result(mcp, mcp.call("GetEditorScene", Action="NavigationStatus", WaitSeconds=.1))["CompatibilityResult"]
    assert isinstance(status["bNavigationAvailable"], bool) and status["RemainingTasks"] >= 0, status
    bounds = dict(BoundsMin={"X": -1000, "Y": -1000, "Z": -1000},
                  BoundsMax={"X": 1000, "Y": 1000, "Z": 1000}, Limit=2)
    for action in ("NavigationContributors", "NavigationTiles"):
        data = operation_result(mcp, mcp.call("GetEditorScene", Action=action, **bounds))["CompatibilityResult"]
        assert len(data["Items"]) <= 2, data
    geometry = operation_result(mcp, mcp.call("GetEditorScene", Action="LevelGeometry", Limit=2))["CompatibilityResult"]
    assert geometry["LevelPath"] and len(geometry["Items"]) <= 2, geometry
    invalid = mcp.try_call("GetEditorScene", Action="NavigationContributors", Limit=2)
    assert invalid.get("isError"), invalid


def test_feedback_async_navigation_batch(mcp, require_tools):
    require_tools("GetNavigationPoint", "GetEditorOperation")
    calls = [{"Capability": "GetNavigationPoint", "Arguments": {
        "World": "Editor", "Point": {"X": index * 10, "Y": 0, "Z": 0}}} for index in range(16)]
    pending = mcp.call("CallCapability", Calls=calls, bAsyncReadOnly=True, TimeoutSeconds=30)
    assert pending["State"] == "Running" and pending["OperationId"], pending
    data = operation_result(mcp, pending)["CompatibilityResult"]
    assert data["CompletedCount"] == 16 and data["FailureCount"] == 0 and not data["bTimedOut"], data
    assert len(data["Results"]) == 16 and all("Data" in item for item in data["Results"]), data
    for rejected_calls in (calls * 5, calls + [{"Capability": "ControlEditorScene", "Arguments": {"Action": "BuildNavigation"}}]):
        rejected = mcp.try_call("CallCapability", Calls=rejected_calls, bAsyncReadOnly=True)
        assert rejected.get("isError"), rejected


def test_feedback_async_batch_cancel_and_timeout(mcp, require_tools):
    require_tools("GetEditorInfo", "GetEditorOperation", "ControlEditorOperation")
    calls = [{"Capability": "GetEditorInfo", "Arguments": {}} for _ in range(64)]
    pending = mcp.call("CallCapability", Calls=calls, bAsyncReadOnly=True, TimeoutSeconds=30)
    stopped = cap_first(mcp.call("ControlEditorOperation", OperationId=pending["OperationId"]))
    assert stopped["State"] == "Cancelled", stopped
    pending = mcp.call("CallCapability", Calls=calls, bAsyncReadOnly=True, TimeoutSeconds=.01)
    time.sleep(.05)
    raw = mcp.try_call("GetEditorOperation", OperationId=pending["OperationId"])
    result = raw.get("structuredContent") or json.loads(raw["content"][0]["text"])
    assert result["State"] == "Failed" and result["Result"]["CompatibilityResult"]["bTimedOut"], result


def test_feedback_static_mesh_diagnostics(mcp, require_tools, test_ns):
    require_tools("GetAssetStaticMesh", "ManageAssetStaticMesh", "DuplicateAsset")
    assets = mcp.call("SearchAsset", AssetType="StaticMesh", PathFilter="/Game/", Limit=1)["Assets"]
    assert assets, "StaticMesh fixture is required in the test host"
    source = assets[0]["Path"]
    path = f"{test_ns}/SM_CollisionDiagnostics"
    mcp.call("DuplicateAsset", AssetPath=source, DestAssetPath=path)
    mesh = cap_first(mcp.call("GetAssetStaticMesh", AssetPath=path, MaxTriangles=2))
    assert "bHasNavigationData" in mesh["Navigation"] and "Sections" in mesh, mesh
    sections = merge_with_defaults(mesh["Sections"], mesh.get("Sections_defaults", {}))
    assert len(mesh["Triangles"]) <= 2 and all("bEnableCollision" in section for section in sections), mesh
    refreshed = cap_first(mcp.call("ManageAssetStaticMesh", AssetPath=path, Operations=[{"Action": "RefreshCollision"}]))
    assert "RefreshedComponentCount" in refreshed, refreshed


def test_feedback_level_export_diagnostics(mcp, require_tools, pytestconfig):
    require_tools("GetEditorContext", "ExportAsset")
    current = cap_first(mcp.call("GetEditorContext", Sections=["CurrentMap"]))
    project = Path(pytestconfig.getoption("--uproject") or Path(__file__).resolve().parents[1] / "Nexus.uproject").parent
    output = project / "Saved/NexusCaptures" / ("FeedbackBsp_" + uuid.uuid4().hex + ".obj")
    try:
        raw = mcp.try_call("ExportAsset", AssetPath=current["AssetPath"], OutputPath=str(output), ConflictPolicy="Fail")
        result = raw.get("structuredContent") or json.loads(raw["content"][0]["text"])
        data = cap_first(result)
        assert data["Exporter"] and isinstance(data["ExporterDiagnostics"], list), data
        assert isinstance(data["ExporterErrors"], list) and "BspNodeCount" in data["LevelGeometry"], data
    finally:
        for path in (output, output.with_suffix(".mtl")):
            path.unlink(missing_ok=True)


@pytest.mark.parametrize("name", ["NexusLink.FeedbackNov12.LiveCollision", "NexusLink.Review.DirtyLevelProtection"])
def test_feedback_native_collision_and_dirty_packages(mcp, require_tools, name):
    require_tools("ControlEditorAutomation", "GetEditorOperation")
    operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Discover"))
    result = operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Run", TestNames=[name]))
    assert result["Tests"][0]["Outcome"] == "Passed", result


@pytest.mark.requires_gui
def test_feedback_searchable_combo(mcp, require_tools):
    require_tools("ControlEditorAutomation", "GetEditorOperation")
    operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Discover"))
    result = operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Run", TestNames=["NexusLink.EditorOperations.SearchableCombo"]))
    assert result["Tests"][0]["Outcome"] == "Passed", result
