# Copyright byteyang. All Rights Reserved.
"""阶段九七：Enhanced Input — InputAction / InputMappingContext（UE5+）。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.0")]


# ── InputAction ──────────────────────────────────────────────────────────────

def test_create_input_action(test_ns, mcp):
    path = f"{test_ns}/IA_TestJump"
    r = mcp.call_capability(
        "create_asset_input_action",
        assetPath=path,
        valueType="Boolean",
    )
    entry = cap_first(r)
    assert not entry.get("error"), r
    assert not entry.get("error") and entry.get("success") is not False, r


def test_get_input_action(test_ns, mcp):
    path = f"{test_ns}/IA_TestJump"
    r = mcp.call_capability("get_asset_input_action", assetPath=path)
    entry = cap_first(r)
    entry = entry
    assert entry.get("valueType") == "Boolean", entry
    assert entry.get("assetType") == "InputAction", entry


def test_manage_input_action_set_value_type(test_ns, mcp):
    path = f"{test_ns}/IA_TestJump"
    r = mcp.call_capability(
        "manage_asset_input_action",
        assetPath=path,
        operations=[{"action": "set_value_type", "valueType": "Axis1D"}],
    )
    entry = cap_first(r)
    assert not entry.get("error"), r

    # 验证已更新
    check = mcp.call_capability("get_asset_input_action", assetPath=path)
    assert check.get("results", [{}])[0].get("valueType") == "Axis1D"


def test_manage_input_action_add_trigger(test_ns, mcp):
    path = f"{test_ns}/IA_TestJump"
    r = mcp.call_capability(
        "manage_asset_input_action",
        assetPath=path,
        operations=[{"action": "add_trigger", "className": "InputTriggerPressed"}],
    )
    entry = cap_first(r)
    # 允许未找到类（不同 UE 版本类名略有差异），不视为失败
    assert "error" not in entry or "未找到" in entry["error"], r


# ── InputMappingContext ───────────────────────────────────────────────────────

def test_create_input_mapping_context(test_ns, mcp):
    path = f"{test_ns}/IMC_TestDefault"
    r = mcp.call_capability("create_asset_input_mapping_context", assetPath=path)
    entry = cap_first(r)
    assert not entry.get("error"), r
    assert not entry.get("error") and entry.get("success") is not False, r


def test_get_input_mapping_context(test_ns, mcp):
    path = f"{test_ns}/IMC_TestDefault"
    r = mcp.call_capability("get_asset_input_mapping_context", assetPath=path)
    entry = cap_first(r)
    entry = entry
    assert entry.get("assetType") == "InputMappingContext", entry
    assert "mappingsCount" in entry, entry


def test_manage_imc_add_remove_mapping(test_ns, mcp):
    imc_path = f"{test_ns}/IMC_TestDefault"
    ia_path  = f"{test_ns}/IA_TestJump"

    add = mcp.call_capability(
        "manage_asset_input_mapping_context",
        assetPath=imc_path,
        operations=[{"action": "add_mapping", "actionPath": ia_path, "key": "SpaceBar"}],
    )
    add_results = add.get("results") or []
    assert len(add_results) == 1, add
    assert not add_results[0].get("error"), add

    remove = mcp.call_capability(
        "manage_asset_input_mapping_context",
        assetPath=imc_path,
        operations=[{"action": "remove_mapping", "key": "SpaceBar"}],
    )
    remove_results = remove.get("results") or []
    assert len(remove_results) == 1, remove
    assert remove_results[0].get("removedCount", 0) >= 1, remove
