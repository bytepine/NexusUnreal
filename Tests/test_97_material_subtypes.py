# Copyright byteyang. All Rights Reserved.
"""阶段九七：材质子类型 — MaterialFunction / MaterialParameterCollection。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.l3_asset


# ── MaterialFunction ──────────────────────────────────────────────────────────

def test_create_material_function(test_ns, mcp):
    path = f"{test_ns}/MF_TestFunc"
    r = mcp.call_capability(
        "create_asset_material_function",
        assetPath=path,
        description="测试函数",
        exposeToLibrary=False,
    )
    results = r.get("results") or []
    assert len(results) == 1, r
    assert not results[0].get("error"), r
    assert results[0].get("success"), r
    assert results[0].get("assetType") == "MaterialFunction", r


def test_get_material_function(test_ns, mcp):
    """get_asset_material 应能读取 MaterialFunction 类型。"""
    path = f"{test_ns}/MF_TestFunc"
    r = mcp.call_capability(
        "get_asset_material",
        assetPath=path,
        sections=["overview"],
    )
    results = r.get("results") or []
    assert len(results) >= 1, r


# ── MaterialParameterCollection ───────────────────────────────────────────────

def test_create_mpc(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability("create_asset_material_parameter_collection", assetPath=path)
    results = r.get("results") or []
    assert len(results) == 1, r
    assert not results[0].get("error"), r
    assert results[0].get("success"), r


def test_manage_mpc_add_scalar(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability(
        "manage_asset_material_parameter_collection",
        assetPath=path,
        operations=[{"action": "add_scalar", "paramName": "GlobalBrightness", "defaultValue": 1.0}],
    )
    results = r.get("results") or []
    assert len(results) == 1, r
    assert not results[0].get("error"), r


def test_manage_mpc_add_vector(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability(
        "manage_asset_material_parameter_collection",
        assetPath=path,
        operations=[{"action": "add_vector", "paramName": "GlobalTint", "r": 1.0, "g": 0.5, "b": 0.0, "a": 1.0}],
    )
    results = r.get("results") or []
    assert len(results) == 1, r
    assert not results[0].get("error"), r


def test_get_mpc(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability("get_asset_material_parameter_collection", assetPath=path)
    results = r.get("results") or []
    assert len(results) == 1, r
    entry = results[0]
    assert entry.get("assetType") == "MaterialParameterCollection", entry
    assert entry.get("scalarParametersCount", 0) >= 1, entry
    assert entry.get("vectorParametersCount", 0) >= 1, entry


def test_manage_mpc_set_scalar_default(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability(
        "manage_asset_material_parameter_collection",
        assetPath=path,
        operations=[{"action": "set_scalar_default", "paramName": "GlobalBrightness", "defaultValue": 2.0}],
    )
    results = r.get("results") or []
    assert len(results) == 1, r
    assert not results[0].get("error"), r


def test_manage_mpc_remove(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability(
        "manage_asset_material_parameter_collection",
        assetPath=path,
        operations=[{"action": "remove", "paramName": "GlobalBrightness"}],
    )
    results = r.get("results") or []
    assert len(results) == 1, r
    assert results[0].get("removedCount", 0) >= 1, r
