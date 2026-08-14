# Copyright byteyang. All Rights Reserved.
"""阶段九七：材质子类型 — MaterialFunction / MaterialParameterCollection。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_first

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
    entry = cap_first(r)
    assert not entry.get("error"), r
    assert not entry.get("error") and entry.get("success") is not False, r
    assert entry.get("assetType") == "MaterialFunction", r


def test_get_material_function(test_ns, mcp):
    """get_asset_material 应能读取 MaterialFunction 类型。"""
    path = f"{test_ns}/MF_TestFunc"
    r = mcp.call_capability(
        "get_asset_material",
        assetPath=path,
        sections=["overview"],
    )
    entry = cap_first(r)
    assert entry, r


def test_manage_material_function_add_connect_remove(test_ns, mcp):
    """MaterialFunction 走 manage_asset_material 图操作（非 Material 属性针脚）。"""
    from _framework.assertions import assert_success_count, ids_of

    path = f"{test_ns}/MF_TestFunc"
    add = mcp.call_capability(
        "manage_asset_material",
        assetPath=path,
        operations=[
            {"action": "add_node", "expressionClass": "Constant"},
            {"action": "add_node", "expressionClass": "FunctionOutput"},
        ],
    )
    node_ids = ids_of(add, "nodeId")
    assert len(node_ids) >= 2, f"add_node MF missing nodeId: {add!r}"
    const_id, out_id = node_ids[0], node_ids[1]

    connect = mcp.call_capability(
        "manage_asset_material",
        assetPath=path,
        operations=[{
            "action": "connect",
            "sourceNodeId": const_id,
            "targetNodeId": out_id,
        }],
    )
    assert_success_count(connect, 1, context="mf connect")

    graph = mcp.call_capability(
        "get_asset_material",
        assetPath=path,
        sections=["graph"],
    )
    g = cap_first(graph)
    assert g.get("totalCount", 0) >= 2 or len(g.get("nodes") or []) >= 2, graph

    remove = mcp.call_capability(
        "manage_asset_material",
        assetPath=path,
        operations=[{"action": "remove_node", "nodeId": const_id}],
    )
    assert_success_count(remove, 1, context="mf remove")


# ── MaterialParameterCollection ───────────────────────────────────────────────

def test_create_mpc(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability("create_asset_material_parameter_collection", assetPath=path)
    entry = cap_first(r)
    assert not entry.get("error"), r
    assert not entry.get("error") and entry.get("success") is not False, r


def test_manage_mpc_add_scalar(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability(
        "manage_asset_material_parameter_collection",
        assetPath=path,
        operations=[{"action": "add_scalar", "paramName": "GlobalBrightness", "defaultValue": 1.0}],
    )
    entry = cap_first(r)
    assert not entry.get("error"), r


def test_manage_mpc_add_vector(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability(
        "manage_asset_material_parameter_collection",
        assetPath=path,
        operations=[{"action": "add_vector", "paramName": "GlobalTint", "r": 1.0, "g": 0.5, "b": 0.0, "a": 1.0}],
    )
    entry = cap_first(r)
    assert not entry.get("error"), r


def test_get_mpc(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability("get_asset_material_parameter_collection", assetPath=path)
    entry = cap_first(r)
    entry = entry
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
    entry = cap_first(r)
    assert not entry.get("error"), r


def test_manage_mpc_remove(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability(
        "manage_asset_material_parameter_collection",
        assetPath=path,
        operations=[{"action": "remove", "paramName": "GlobalBrightness"}],
    )
    entry = cap_first(r)
    assert entry.get("removedCount", 0) >= 1, r
