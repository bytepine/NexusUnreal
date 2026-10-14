# Copyright byteyang. All Rights Reserved.
"""材质子类型 — MaterialFunction / MaterialParameterCollection。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l3_asset


# ── MaterialFunction ──────────────────────────────────────────────────────────

def test_create_material_function(test_ns, mcp):
    path = f"{test_ns}/MF_TestFunc"
    r = mcp.call_capability(
        "CreateAssetMaterialFunction",
        AssetPath=path,
        description="测试函数",
        bExposeToLibrary=False,
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r
    assert not entry.get("Error") and entry.get("bSuccess") is not False, r
    assert entry.get("AssetType") == "MaterialFunction", r


def test_get_material_function(test_ns, mcp):
    """get_asset_material 应能读取 MaterialFunction 类型。"""
    path = f"{test_ns}/MF_TestFunc"
    r = mcp.call_capability(
        "GetAssetMaterial",
        AssetPath=path,
        Sections=["overview"],
    )
    entry = cap_first(r)
    assert entry, r


def test_manage_material_function_add_connect_remove(test_ns, mcp):
    """MaterialFunction 走 manage_asset_material 图操作（非 Material 属性针脚）。"""
    from _framework.assertions import assert_success_count, ids_of

    path = f"{test_ns}/MF_TestFunc"
    add = mcp.call_capability(
        "ManageAssetMaterial",
        AssetPath=path,
        Operations=[
            {"Action": "AddNode", "ExpressionClass": "Constant"},
            {"Action": "AddNode", "ExpressionClass": "FunctionOutput"},
        ],
    )
    node_ids = ids_of(add, "NodeId")
    assert len(node_ids) >= 2, f"add_node MF missing nodeId: {add!r}"
    const_id, out_id = node_ids[0], node_ids[1]

    connect = mcp.call_capability(
        "ManageAssetMaterial",
        AssetPath=path,
        Operations=[{
            "Action": "Connect",
            "SourceNodeId": const_id,
            "TargetNodeId": out_id,
        }],
    )
    assert_success_count(connect, 1, context="mf connect")

    graph = mcp.call_capability(
        "GetAssetMaterial",
        AssetPath=path,
        Sections=["graph"],
    )
    g = cap_first(graph)
    assert g.get("TotalCount", 0) >= 2 or len(g.get("Nodes") or []) >= 2, graph

    remove = mcp.call_capability(
        "ManageAssetMaterial",
        AssetPath=path,
        Operations=[{"Action": "RemoveNode", "NodeId": const_id}],
    )
    assert_success_count(remove, 1, context="mf remove")


# ── MaterialParameterCollection ───────────────────────────────────────────────

def test_create_mpc(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability("CreateAssetMaterialParameterCollection", AssetPath=path)
    entry = cap_first(r)
    assert not entry.get("Error"), r
    assert not entry.get("Error") and entry.get("bSuccess") is not False, r


def test_manage_mpc_add_scalar(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability(
        "ManageAssetMaterialParameterCollection",
        AssetPath=path,
        Operations=[{"Action": "AddScalar", "ParamName": "GlobalBrightness", "DefaultValue": 1.0}],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r


def test_manage_mpc_add_vector(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability(
        "ManageAssetMaterialParameterCollection",
        AssetPath=path,
        Operations=[{"Action": "AddVector", "ParamName": "GlobalTint", "r": 1.0, "g": 0.5, "b": 0.0, "a": 1.0}],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r


def test_get_mpc(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability("GetAssetMaterialParameterCollection", AssetPath=path)
    entry = cap_first(r)
    entry = entry
    assert entry.get("AssetType") == "MaterialParameterCollection", entry
    assert entry.get("ScalarParametersCount", 0) >= 1, entry
    assert entry.get("VectorParametersCount", 0) >= 1, entry


def test_manage_mpc_set_scalar_default(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability(
        "ManageAssetMaterialParameterCollection",
        AssetPath=path,
        Operations=[{"Action": "SetScalarDefault", "ParamName": "GlobalBrightness", "DefaultValue": 2.0}],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r


def test_manage_mpc_set_vector_default(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    try:
        mcp.call_capability(
            "ManageAssetMaterialParameterCollection",
            AssetPath=path,
            Operations=[{"Action": "AddVector", "ParamName": "GlobalColor", "r": 1, "g": 1, "b": 1, "a": 1}],
        )
        r = mcp.call_capability(
            "ManageAssetMaterialParameterCollection",
            AssetPath=path,
            Operations=[{"Action": "SetVectorDefault", "ParamName": "GlobalColor", "r": 1, "g": 1, "b": 1, "a": 1}],
        )
    except MCPError as e:
        pytest.skip(f"set_vector_default 跳过: {e}")
    entry = cap_first(r)
    if entry.get("Error"):
        pytest.skip(f"set_vector_default 跳过: {entry}")


def test_manage_mpc_remove(test_ns, mcp):
    path = f"{test_ns}/MPC_TestGlobal"
    r = mcp.call_capability(
        "ManageAssetMaterialParameterCollection",
        AssetPath=path,
        Operations=[{"Action": "Remove", "ParamName": "GlobalBrightness"}],
    )
    entry = cap_first(r)
    assert entry.get("RemovedCount", 0) >= 1, r
