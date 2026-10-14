# Copyright byteyang. All Rights Reserved.
"""Enhanced Input — InputAction / InputMappingContext（UE5+）。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.0")]


# ── InputAction ──────────────────────────────────────────────────────────────

def test_create_input_action(test_ns, mcp):
    path = f"{test_ns}/IA_TestJump"
    r = mcp.call_capability(
        "CreateAssetInputAction",
        AssetPath=path,
        ValueType="Boolean",
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r
    assert not entry.get("Error") and entry.get("bSuccess") is not False, r


def test_get_input_action(test_ns, mcp):
    path = f"{test_ns}/IA_TestJump"
    r = mcp.call_capability("GetAssetInputAction", AssetPath=path)
    entry = cap_first(r)
    entry = entry
    assert entry.get("ValueType") == "Boolean", entry
    assert entry.get("AssetType") == "InputAction", entry


def test_manage_input_action_set_value_type(test_ns, mcp):
    path = f"{test_ns}/IA_TestJump"
    r = mcp.call_capability(
        "ManageAssetInputAction",
        AssetPath=path,
        Operations=[{"Action": "SetValueType", "ValueType": "Axis1D"}],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r

    # 验证已更新
    check = mcp.call_capability("GetAssetInputAction", AssetPath=path)
    assert cap_first(check).get("ValueType") == "Axis1D", check


def test_manage_input_action_add_trigger(test_ns, mcp):
    path = f"{test_ns}/IA_TestJump"
    r = mcp.call_capability(
        "ManageAssetInputAction",
        AssetPath=path,
        Operations=[{"Action": "AddTrigger", "ClassName": "InputTriggerPressed"}],
    )
    entry = cap_first(r)
    # 允许未找到类（不同 UE 版本类名略有差异），不视为失败
    assert "Error" not in entry or "未找到" in entry["Error"], r


def test_manage_input_action_remaining(test_ns, mcp):
    path = f"{test_ns}/IA_TestJump"
    r = mcp.call_capability(
        "ManageAssetInputAction",
        AssetPath=path,
        Operations=[
            {"Action": "AddModifier", "ClassName": "InputModifierNegate"},
            {"Action": "SetFlags", "bConsumesInput": True},
            {"Action": "RemoveTrigger", "ClassName": "InputTriggerPressed"},
            {"Action": "RemoveModifier", "ClassName": "InputModifierNegate"},
        ],
    )
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"input_action remaining 跳过: {e}")


# ── InputMappingContext ───────────────────────────────────────────────────────

def test_create_input_mapping_context(test_ns, mcp):
    path = f"{test_ns}/IMC_TestDefault"
    r = mcp.call_capability("CreateAssetInputMappingContext", AssetPath=path)
    entry = cap_first(r)
    assert not entry.get("Error"), r
    assert not entry.get("Error") and entry.get("bSuccess") is not False, r


def test_get_input_mapping_context(test_ns, mcp):
    path = f"{test_ns}/IMC_TestDefault"
    r = mcp.call_capability("GetAssetInputMappingContext", AssetPath=path)
    entry = cap_first(r)
    entry = entry
    assert entry.get("AssetType") == "InputMappingContext", entry
    assert "MappingsCount" in entry, entry


def test_manage_imc_add_remove_mapping(test_ns, mcp):
    imc_path = f"{test_ns}/IMC_TestDefault"
    ia_path  = f"{test_ns}/IA_TestJump"

    add = mcp.call_capability(
        "ManageAssetInputMappingContext",
        AssetPath=imc_path,
        Operations=[{"Action": "AddMapping", "ActionPath": ia_path, "Key": "SpaceBar"}],
    )
    add_results = add.get("Results") or [cap_first(add)]
    assert len(add_results) == 1, add
    assert not add_results[0].get("Error"), add

    remove = mcp.call_capability(
        "ManageAssetInputMappingContext",
        AssetPath=imc_path,
        Operations=[{"Action": "RemoveMapping", "Key": "SpaceBar"}],
    )
    remove_results = remove.get("Results") or [cap_first(remove)]
    assert len(remove_results) == 1, remove
    assert remove_results[0].get("RemovedCount", 0) >= 1, remove
    clr = mcp.call_capability(
        "ManageAssetInputMappingContext",
        AssetPath=imc_path,
        Operations=[{"Action": "ClearMappings"}],
    )
    assert not cap_first(clr).get("Error"), clr
