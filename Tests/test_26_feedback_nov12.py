# Copyright byteyang. All Rights Reserved.
"""UE4 BlendSpace1D 持久化与跨目标蓝图写入反馈回归。"""
import pytest
from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l3_asset


def test_feedback_blendspace1d_roundtrip(mcp, require_tools, test_ns):
    require_tools("CreateAssetBlendSpace", "ManageAssetBlendSpace", "GetAssetBlendSpace")
    assets = []
    for prefix in ("/Game/", "/Engine/"):
        assets = mcp.call("SearchAsset", AssetType="Skeleton", PathFilter=prefix, Limit=1).get("Assets") or []
        if assets:
            break
    if not assets:
        pytest.skip("No skeleton fixture")
    skeleton = assets[0]["Path"]
    path = f"{test_ns}/BS1D_Roundtrip"
    mcp.call("CreateAssetBlendSpace", AssetPath=path, SkeletonPath=skeleton, BlendSpaceType="BlendSpace1D")
    mcp.call("SearchAsset", AssetType="BlendSpace1D", PathFilter=test_ns)
    mcp.call("ManageAssetBlendSpace", AssetPath=path, Operations=[{
        "Action": "SetAxis", "AxisIndex": 0, "DisplayName": "Speed", "Min": 0, "Max": 500, "GridNum": 5,
    }])
    saved = cap_first(mcp.call("SaveAsset", AssetPath=path))
    assert saved["bSaved"], saved
    mcp.call("UnloadAsset", AssetPath=path)
    read = cap_first(mcp.call("GetAssetBlendSpace", AssetPath=path))
    assert read["AssetType"] == "BlendSpace1D" and len(read["Axes"]) == 1, read
    assert read["Axes"][0]["Max"] == 500 and read["Axes"][0]["GridNum"] == 5, read
    assert mcp.try_call("ManageAssetBlendSpace", AssetPath=path, Operations=[{
        "Action": "SetAxis", "Min": 100, "Max": 0,
    }]).get("isError")
    after = cap_first(mcp.call("GetAssetBlendSpace", AssetPath=path))
    assert after["Axes"] == read["Axes"], after


def test_feedback_blueprint_cross_target_batch(mcp, require_tools, test_ns):
    require_tools("CreateAssetBlueprint", "ManageAssetBlueprint", "GetAssetBlueprint")
    paths = [f"{test_ns}/BP_Native_{index}" for index in range(7)]
    for path in paths:
        mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="Character")
    mcp.call("CallCapability", Calls=[{
        "Capability": "ManageAssetBlueprint", "Arguments": {
            "AssetPath": path, "bCompile": True, "Operations": [{
                "Action": "AddVariable", "VariableName": "FeedbackValue", "VariableType": "bool", "DefaultValue": "true",
            }],
        },
    } for path in paths])
    for path in paths:
        variables = cap_first(mcp.call("GetAssetBlueprint", AssetPath=path, Sections=["Variable"]))["Variables"]
        assert any(variable["Name"] == "FeedbackValue" for variable in variables), variables
    path = paths[0]
    for verify in (False, True):
        mcp.call("ManageAssetBlueprint", AssetPath=path, bCompile=True, bVerify=verify, Operations=[{
            "Action": "SetComponentProperty", "ComponentName": "CharacterMesh0", "PropertyPath": "bHiddenInGame", "Value": "true",
        }])
