# Copyright byteyang. All Rights Reserved.
"""默认值、类引用、旧式 Retarget 和导航写入的反馈回归。"""
import json
import pytest
from _framework.mcp_client import cap_first
from _framework.asset_helpers import first_asset_path
from test_15_editor_operations import operation_result


@pytest.fixture
def feedback_level(mcp, require_tools, test_ns, request):
    require_tools("CreateAssetLevel", "ControlEditorLevel", "GetEditorContext", "SaveAsset")
    original = cap_first(mcp.call("GetEditorContext", Sections=["CurrentMap"]))["AssetPath"]
    path = f"{test_ns}/L_{request.node.name}"
    mcp.call("CreateAssetLevel", AssetPath=path)
    result = mcp.try_call("ControlEditorLevel", AssetPath=path)
    if result.get("isError"):
        pytest.skip(f"Cannot switch away from current editor map: {result}")
    try:
        yield path
    finally:
        mcp.call("SaveAsset", AssetPath=path)
        mcp.call("ControlEditorLevel", AssetPath=original)


def test_feedback_defaults_class_references(mcp, require_tools, test_ns, feedback_level):
    require_tools("CreateAssetBlueprint", "ManageAssetBlueprint", "GetAssetBlueprint", "ManageAssetLevel", "GetAssetLevel", "GetAssetEditPreview")
    parent, child = f"{test_ns}/BP_Parent", f"{test_ns}/BP_Child"
    mcp.call("CreateAssetBlueprint", AssetPath=parent, ParentClass="Actor")
    mcp.call("CompileBlueprint", AssetPath=parent)
    mcp.call("CreateAssetBlueprint", AssetPath=child, ParentClass=parent)
    mcp.call("CompileBlueprint", AssetPath=child)
    actor = cap_first(mcp.call("ManageAssetLevel", AssetPath=feedback_level, Operations=[{"Action": "SpawnActor", "AssetPath": child}]))["ActorName"]
    mcp.call("ManageAssetBlueprint", AssetPath=parent, bCompile=True, Operations=[{
        "Action": "AddVariable", "VariableName": "Distance", "VariableType": "float", "DefaultValue": "120", "bIsPublic": True,
    }])
    mcp.call("CompileBlueprint", AssetPath=child)
    values = cap_first(mcp.call("GetAssetLevel", AssetPath=feedback_level, Sections=["ActorProperties"], ActorName=actor, PropertyPaths=["Distance"]))
    assert float(values["Properties"][0]["Value"]) == 120, values
    assert float(values["Properties"][0]["DefaultValue"]) == 120, values
    mcp.call("ManageAssetBlueprint", AssetPath=child, bCompile=True, Operations=[{
        "Action": "AddVariable", "VariableName": "ActorClass", "VariableType": "ClassReference</Script/Engine.Actor>",
    }])
    variables = cap_first(mcp.call("GetAssetBlueprint", AssetPath=child, Sections=["Variable"]))["Variables"]
    assert next(v for v in variables if v["Name"] == "ActorClass")["Type"] == "class", variables
    operation = {"Action": "SetDefaults", "PropertyPath": "ActorClass", "Value": "Class'/Script/Engine.Character'", "ExpectedValue": "None"}
    preview = cap_first(mcp.call("GetAssetEditPreview", AssetPath=child, Capability="ManageAssetBlueprint", Operations=[operation]))
    assert preview["bValid"], preview
    mcp.call("ManageAssetBlueprint", AssetPath=child, bCompile=True, bVerify=True, Operations=[operation])


def test_feedback_legacy_retarget(mcp, require_tools, test_ns):
    require_tools("DuplicateAsset", "CreateAssetAnimBlueprint", "ManageAssetAnimBlueprint", "ManageAssetAnimSequence")
    sequence = first_asset_path(mcp, "AnimSequence")
    if not sequence:
        pytest.skip("No animation sequence fixture")
    metadata = cap_first(mcp.call("GetAssetAnimSequence", AssetPath=sequence))
    source = metadata["Skeleton"]
    target = f"{test_ns}/SK_Target"
    mcp.call("DuplicateAsset", AssetPath=source, DestAssetPath=target)
    path = f"{test_ns}/A_Retarget"
    mcp.call("DuplicateAsset", AssetPath=sequence, DestAssetPath=path)
    operation = {"Action": "Retarget", "TargetSkeleton": target, "bValidateOnly": True}
    preview = cap_first(mcp.call("ManageAssetAnimSequence", AssetPath=path, Operations=[operation]))
    assert preview["bValid"] and not preview["bChanged"], preview
    operation.update(bValidateOnly=False, bAllowPotentialDataLoss=True)
    mcp.call("ManageAssetAnimSequence", AssetPath=path, Operations=[operation])
    read = cap_first(mcp.call("GetAssetAnimSequence", AssetPath=path))
    assert read["Skeleton"].split(".")[0] == target, read
    blueprint = f"{test_ns}/ABP_Retarget"
    mcp.call("CreateAssetAnimBlueprint", AssetPath=blueprint, SkeletonPath=source)
    mcp.call("ManageAssetAnimBlueprint", AssetPath=blueprint, bCompile=True, Operations=[{
        "Action": "AddNode", "GraphName": "AnimGraph", "NodeClass": "SequencePlayer", "SequencePath": sequence,
    }])
    missing = mcp.try_call("ManageAssetAnimBlueprint", AssetPath=blueprint, Operations=[dict(operation, bValidateOnly=True)])
    assert missing.get("isError"), missing
    operation["AnimationRemaps"] = [{"SourceAssetPath": sequence, "TargetAssetPath": path}]
    mcp.call("ManageAssetAnimBlueprint", AssetPath=blueprint, bCompile=True, Operations=[operation])
    read = cap_first(mcp.call("GetAssetAnimBlueprint", AssetPath=blueprint, Sections=["Variables"]))
    assert read["Skeleton"].split(".")[0] == target, read
    unchanged = cap_first(mcp.call("GetAssetAnimSequence", AssetPath=sequence))
    assert unchanged["Skeleton"] == source, unchanged


def test_feedback_delete_reference_diagnostics(mcp, require_tools, test_ns):
    require_tools("CreateAssetBlueprint", "CompileBlueprint", "DeleteAsset")
    parent, child = f"{test_ns}/BP_DeleteParent", f"{test_ns}/BP_DeleteChild"
    mcp.call("CreateAssetBlueprint", AssetPath=parent, ParentClass="Actor")
    mcp.call("CompileBlueprint", AssetPath=parent, bSaveToDisk=True)
    mcp.call("CreateAssetBlueprint", AssetPath=child, ParentClass=parent)
    mcp.call("CompileBlueprint", AssetPath=child, bSaveToDisk=True)
    error = mcp.try_call("DeleteAsset", AssetPath=parent)
    assert error.get("isError"), error
    detail = cap_first(error.get("structuredContent") or json.loads(error["content"][0]["text"]))
    assert child in detail["DiskReferencers"], detail
    assert isinstance(detail["MemoryReferencers"], list) and isinstance(detail["OpenAssetEditors"], list), detail
    assert isinstance(detail["bReferencedByUndo"], bool) and isinstance(detail["bFileReadOnly"], bool), detail


def test_feedback_navigation_bounds_and_build(mcp, require_tools, feedback_level, test_ns):
    require_tools("ManageAssetLevel", "GetEditorContext", "ControlEditorScene", "GetEditorOperation")
    context = cap_first(mcp.call("GetEditorContext", Sections=["CurrentMap"]))
    assert any(level["bCurrent"] and level["AssetPath"] == feedback_level for level in context["Levels"]), context
    listing = mcp.call("SearchAsset", AssetType="StaticMesh", PathFilter="/Engine/BasicShapes/", Query="Cube", Limit=1)
    cube = cap_first(listing)["Assets"][0]["Path"]
    cube_object = cube if "." in cube.rsplit("/", 1)[-1] else f"{cube}.{cube.rsplit('/', 1)[-1]}"
    floor = f"{test_ns}/BP_NavigationFloor"
    mcp.call("CreateAssetBlueprint", AssetPath=floor, ParentClass="Actor")
    mcp.call("ManageAssetBlueprint", AssetPath=floor, bCompile=True, Operations=[
        {"Action": "AddComponent", "ComponentName": "Floor", "ComponentClass": "StaticMeshComponent"},
        {"Action": "SetComponentProperty", "ComponentName": "Floor", "PropertyPath": "StaticMesh", "Value": f"StaticMesh'{cube_object}'"},
        {"Action": "SetComponentProperty", "ComponentName": "Floor", "PropertyPath": "RelativeScale3D", "Value": "(X=10,Y=10,Z=1)"},
    ])
    mcp.call("ManageAssetLevel", AssetPath=feedback_level, Operations=[{"Action": "SpawnActor", "AssetPath": floor, "Location": "0,0,-50"}])
    minimum, maximum = {"X": -1000, "Y": -1000, "Z": -200}, {"X": 1000, "Y": 1000, "Z": 500}
    operation = {"Action": "CreateNavMeshBoundsVolume", "BoundsMin": minimum, "BoundsMax": maximum}
    bounds = cap_first(mcp.call("ManageAssetLevel", AssetPath=feedback_level, Operations=[operation], bSaveToDisk=True))
    assert bounds["bBrushCreated"], bounds
    for axis in "XYZ":
        assert bounds["BoundsMin"][axis] == pytest.approx(minimum[axis]), bounds
        assert bounds["BoundsMax"][axis] == pytest.approx(maximum[axis]), bounds
    result = operation_result(mcp, mcp.call("ControlEditorScene", Action="BuildNavigation", bSaveToDisk=True))
    data = result["CompatibilityResult"]
    assert data["bBuildComplete"] and data["bHasNavigationData"] and data["bSaved"], data
    point = cap_first(mcp.call("GetNavigationPoint", World="Editor", Point={"X": 0, "Y": 0, "Z": 10}))
    assert point["bProjected"], point


@pytest.mark.parametrize("query,expected", [("Retarget", "ManageAssetAnimSequence"), ("actor collision", "GetRuntimeActorProperty"), ("Lua inspect", "GetRuntimeLuaObject")])
def test_feedback_search_terms(mcp, require_tools, query, expected):
    require_tools(expected)
    result = mcp.call("SearchCapabilities", Query=query)
    names = [row["name"] for row in result.get("Capabilities", [])]
    if "Capability" in result:
        names.append(result["Capability"]["name"])
    assert expected in names, result
