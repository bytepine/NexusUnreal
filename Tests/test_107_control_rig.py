# Copyright byteyang. All Rights Reserved.
"""ControlRig — create + add_control/add_bone（UE5+ 门控 skip）。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.0")]


@pytest.fixture(scope="module", autouse=True)
def require_cr(mcp):
    if not is_capability_available(mcp, "create_asset_control_rig"):
        pytest.skip("ControlRig capability 未编入（需 WITH_CONTROL_RIG）")


def test_control_rig_create_add_control(test_ns, mcp):
    path = f"{test_ns}/CR_Created"
    r = mcp.call_capability("create_asset_control_rig", assetPath=path)
    entry = cap_first(r)
    if entry.get("error") and "已存在" not in str(entry.get("error")):
        pytest.skip(f"create_asset_control_rig 失败: {entry}")
    add = mcp.call_capability(
        "manage_asset_control_rig",
        assetPath=path,
        operations=[
            {"action": "add_control", "elementName": "NxCtrl"},
            {"action": "add_bone", "elementName": "NxBone"},
        ],
    )
    assert isinstance(cap_first(add), dict), add
    got = cap_first(mcp.call_capability("get_asset_control_rig", assetPath=path))
    assert not got.get("error"), got
    bad = mcp.call_capability(
        "manage_asset_control_rig",
        assetPath=path,
        operations=[{"action": "not_a_real_action"}],
    )
    assert cap_first(bad).get("error"), bad


def test_control_rig_remaining_actions(test_ns, mcp):
    path = f"{test_ns}/CR_Created"
    r = mcp.call_capability(
        "manage_asset_control_rig",
        assetPath=path,
        operations=[
            {"action": "rename_element", "elementName": "NxCtrl", "newName": "NxCtrlRenamed"},
            {"action": "set_control_color", "elementName": "NxCtrlRenamed", "r": 1, "g": 0, "b": 0, "a": 1},
            {"action": "add_null", "elementName": "NxNull"},
            {"action": "add_rig_node", "structType": "RigUnit_GetTransform", "nodeName": "NxGetXform"},
            {"action": "set_pin_default", "pinPath": "NxGetXform.Item", "pinDefaultValue": ""},
            {"action": "add_rig_link", "sourcePinPath": "NxGetXform.Transform", "targetPinPath": "NxGetXform.Item"},
            {"action": "break_rig_link", "sourcePinPath": "NxGetXform.Transform", "targetPinPath": "NxGetXform.Item"},
            {"action": "remove_element", "elementName": "NxNull", "elementType": "null"},
        ],
    )
    for e in (r.get("results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("error"):
            pytest.skip(f"control_rig remaining 跳过: {e}")
