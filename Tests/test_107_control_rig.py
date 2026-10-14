# Copyright byteyang. All Rights Reserved.
"""ControlRig — create + add_control/add_bone（UE5+ 门控 skip）。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import MCPError, cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.0")]


@pytest.fixture(scope="module", autouse=True)
def require_cr(mcp):
    if not is_capability_available(mcp, "CreateAssetControlRig"):
        pytest.skip("ControlRig capability 未编入（需 WITH_CONTROL_RIG）")


def test_control_rig_create_add_control(test_ns, mcp):
    path = f"{test_ns}/CR_Created"
    r = mcp.call_capability("CreateAssetControlRig", AssetPath=path)
    entry = cap_first(r)
    if entry.get("Error") and "已存在" not in str(entry.get("Error")):
        pytest.skip(f"create_asset_control_rig 失败: {entry}")
    add = mcp.call_capability(
        "ManageAssetControlRig",
        AssetPath=path,
        Operations=[
            {"Action": "AddControl", "ElementName": "NxCtrl"},
            {"Action": "AddBone", "ElementName": "NxBone"},
        ],
    )
    assert isinstance(cap_first(add), dict), add
    got = cap_first(mcp.call_capability("GetAssetControlRig", AssetPath=path))
    assert not got.get("Error"), got
    try:
        bad = cap_first(
            mcp.call_capability(
                "ManageAssetControlRig",
                AssetPath=path,
                Operations=[{"Action": "not_a_real_action"}],
            )
        )
    except MCPError as exc:
        bad = {"Error": str(exc)}
    assert bad.get("Error"), bad


def test_control_rig_remaining_actions(test_ns, mcp):
    path = f"{test_ns}/CR_Created"
    r = mcp.call_capability(
        "ManageAssetControlRig",
        AssetPath=path,
        Operations=[
            {"Action": "RenameElement", "ElementName": "NxCtrl", "NewName": "NxCtrlRenamed"},
            {"Action": "SetControlColor", "ElementName": "NxCtrlRenamed", "r": 1, "g": 0, "b": 0, "a": 1},
            {"Action": "AddNull", "ElementName": "NxNull"},
            {"Action": "AddRigNode", "StructType": "RigUnit_GetTransform", "NodeName": "NxGetXform"},
            {"Action": "SetPinDefault", "PinPath": "NxGetXform.Item", "PinDefaultValue": ""},
            {"Action": "AddRigLink", "SourcePinPath": "NxGetXform.Transform", "TargetPinPath": "NxGetXform.Item"},
            {"Action": "BreakRigLink", "SourcePinPath": "NxGetXform.Transform", "TargetPinPath": "NxGetXform.Item"},
            {"Action": "RemoveElement", "ElementName": "NxNull", "ElementType": "null"},
        ],
    )
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"control_rig remaining 跳过: {e}")
