# Copyright byteyang. All Rights Reserved.
"""Real MCP previews and optimistic verified writes in isolated test assets."""
from pathlib import Path
import pytest
from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l3_asset


@pytest.fixture(params=["Blueprint", "DataTable", "UserWidget"])
def edit_target(mcp, test_ns, request):
    kind = request.param
    path = f"{test_ns}/Preview_{kind}_{request.node.originalname}"
    if kind == "Blueprint":
        mcp.call_capability("CreateAssetBlueprint", AssetPath=path, ParentClass="Actor")
        operation = {"Action": "SetDefaults", "PropertyPath": "bCanBeDamaged", "Value": "false"}
    elif kind == "DataTable":
        mcp.call_capability("CreateAssetDataTable", AssetPath=path, RowStructName="NexusReliabilityTestRow")
        mcp.call_capability("ManageAssetDataTable", AssetPath=path, Operations=[{"Action": "Add", "RowName": "Row"}])
        operation = {"Action": "Set", "RowName": "Row", "FieldName": "Count", "Value": "00012"}
    else:
        mcp.call_capability("CreateAssetUserWidget", AssetPath=path)
        mcp.call_capability("ManageAssetUserWidget", AssetPath=path, bCompile=True,
                            Operations=[{"Action": "Add", "WidgetClass": "TextBlock", "WidgetName": "Label"}])
        operation = {"Action": "SetProperty", "WidgetName": "Label", "PropertyPath": "RenderOpacity", "Value": "0.5"}
    mcp.call_capability("SaveAsset", AssetPath=path)
    return path, "ManageAsset" + kind, operation


def test_asset_edit_preview_and_verified_write(mcp, edit_target, pytestconfig):
    path, capability, operation = edit_target
    project = pytestconfig.getoption("--uproject")
    project_root = Path(project).resolve().parent if project else Path(__file__).resolve().parents[1]
    disk = project_root / "Content" / (path.removeprefix("/Game/") + ".uasset")
    before = disk.read_bytes()
    preview = cap_first(mcp.call_capability("GetAssetEditPreview", AssetPath=path, Capability=capability, Operations=[operation]))
    assert preview["bValid"] and preview["PropertyType"], preview
    assert disk.read_bytes() == before
    assert cap_first(mcp.call_capability("GetAssetEditPreview", AssetPath=path, Capability=capability, Operations=[operation])) == preview
    result = cap_first(mcp.call_capability(capability, AssetPath=path, bVerify=True, bSaveToDisk=True,
                                           Operations=[{**operation, "ExpectedValue": preview["CurrentValue"]}]))
    assert result["bVerified"] and result["ReadbackValue"] == preview["TargetValue"], result
    assert result["OldValue"] == preview["CurrentValue"] and result["bSaved"], result
    saved = disk.read_bytes()
    stale = mcp.try_call(capability, AssetPath=path, bVerify=True, bSaveToDisk=True,
                         Operations=[{**operation, "ExpectedValue": preview["CurrentValue"]}])
    assert stale["isError"] and "ExpectedValue mismatch" in str(stale), stale
    assert disk.read_bytes() == saved


def test_asset_edit_unsupported_operations_and_types(mcp, edit_target):
    path, capability, operation = edit_target
    preview = mcp.try_call("GetAssetEditPreview", AssetPath=path, Capability=capability,
                           Operations=[{**operation, "Value": "not-a-number-or-bool"}])
    assert preview["isError"], preview
    rejected = mcp.try_call(capability, AssetPath=path, bVerify=True, Operations=[{"Action": "Remove"}])
    assert rejected["isError"], rejected


def test_asset_edit_batch_rollback(mcp, test_ns):
    path = f"{test_ns}/Preview_Rollback"
    mcp.call_capability("CreateAssetDataTable", AssetPath=path, RowStructName="NexusReliabilityTestRow")
    mcp.call_capability("ManageAssetDataTable", AssetPath=path, Operations=[{"Action": "Add", "RowName": "Row"}])
    operation = {"Action": "Set", "RowName": "Row", "FieldName": "Count", "Value": "12"}
    response = mcp.try_call("CallCapability", Calls=[
        {"Capability": "ManageAssetDataTable", "Arguments": {"AssetPath": path, "bVerify": True, "bSaveToDisk": True,
                                                              "Operations": [{**operation, "ExpectedValue": "7"}]}},
        {"Capability": "ManageAssetDataTable", "Arguments": {"AssetPath": path, "bVerify": True,
                                                              "Operations": [{**operation, "ExpectedValue": "999"}]}}
    ])
    assert response["isError"] and response["structuredContent"]["bRolledBack"], response
    preview = cap_first(mcp.call_capability("GetAssetEditPreview", AssetPath=path, Capability="ManageAssetDataTable", Operations=[operation]))
    assert preview["CurrentValue"] == "7", preview
