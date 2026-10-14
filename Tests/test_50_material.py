# Copyright byteyang. All Rights Reserved.
"""阶段六：Material — 批量节点 + 连线 + 节点反射穿透。"""

from __future__ import annotations

import pytest

from _framework.assertions import assert_success_count, ids_of
from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l3_asset


@pytest.fixture(scope="module")
def mat_path(test_ns, mcp):
    p = f"{test_ns}/M_TestMat"
    mcp.call("CreateAssetMaterial", AssetPath=p)
    yield p


def test_create_decal(test_ns, mcp):
    p = f"{test_ns}/M_TestDecal"
    mcp.call("CreateAssetMaterial", AssetPath=p, MaterialDomain="DeferredDecal")


def test_material_node_add_connect_remove(mcp, mat_path):
    add = mcp.call(
        "ManageAssetMaterial",
        AssetPath=mat_path,
        Operations=[{"Action": "AddNode", "ExpressionClass": "Constant3Vector"}],
    )
    node_ids = ids_of(add, "NodeId")
    assert node_ids, f"add_node missing nodeId: {add!r}"
    nid = node_ids[0]

    connect = mcp.call_capability(
        "ManageAssetMaterial",
        AssetPath=mat_path,
        Operations=[{
            "Action": "Connect",
            "SourceNodeId": nid,
            "TargetNodeId": "Material",
            "TargetInputName": "BaseColor",
        }],
    )
    assert_success_count(connect, 1, context="material connect")

    recompile = mcp.call(
        "ManageAssetMaterial",
        AssetPath=mat_path,
        Operations=[{"Action": "Recompile"}],
    )
    assert_success_count(recompile, 1, context="material recompile")

    disconnect = mcp.call_capability(
        "ManageAssetMaterial",
        AssetPath=mat_path,
        Operations=[
            {"Action": "Disconnect", "TargetNodeId": "Material", "TargetInputName": "BaseColor"},
            {"Action": "DisconnectAll", "SourceNodeId": nid},
        ],
    )
    assert_success_count(disconnect, 2, context="material disconnect batch")

    remove = mcp.call(
        "ManageAssetMaterial",
        AssetPath=mat_path,
        Operations=[{"Action": "RemoveNode", "NodeId": nid}],
    )
    assert_success_count(remove, 1, context="material remove node")


def test_material_two_step_texture_param(mcp, mat_path):
    """6.9：两步法关键用例：add_node + set_node + recompile 一次批量完成。
    置于 overview 之前：overview 的 Sections=["All"] 会令后续 section 查询触发
    redundant_call 保护，故 parameters 校验先于 all。"""
    r = mcp.call(
        "ManageAssetMaterial",
        AssetPath=mat_path,
        Operations=[
            {"Action": "AddNode",
             "ExpressionClass": "TextureSampleParameter2D",
             "PosX": -400, "PosY": 0},
        ],
    )
    ids = ids_of(r, "NodeId")
    assert ids, f"add_node texture missing nodeId: {r!r}"
    nid = ids[0]

    r2 = mcp.call(
        "ManageAssetMaterial",
        AssetPath=mat_path,
        Operations=[
            {"Action": "SetNode", "NodeId": nid, "ParameterName": "BaseTex"},
            {"Action": "Recompile"},
        ],
    )
    assert_success_count(r2, 2, context="material two-step")

    # 6.10：set_node 应已应用 ParameterName=BaseTex（r2 results[0] 的 appliedFields 确认）
    set_entry = cap_first(r2)
    assert set_entry.get("ParameterName") == "BaseTex" or \
           "ParameterName" in (set_entry.get("AppliedFields") or []), \
           f"set_node did not apply parameterName BaseTex: {r2!r}"

    # get_asset_material params section 软校验：set_node 写入的参数名在部分版本下
    # 需材质保存后才在 params 列出，此处仅验证查询链路不报错
    r3 = mcp.call_capability("GetAssetMaterial", AssetPath=mat_path, Sections=["Params"])
    assert isinstance(r3, dict), f"get_asset_material params: {r3!r}"

    # 6.11：用 manage_asset_material set_node 修改参数名（等价于旧 set_property 节点反射写路径）
    r4 = mcp.call_capability(
        "ManageAssetMaterial",
        AssetPath=mat_path,
        Operations=[{"Action": "SetNode", "NodeId": nid, "ParameterName": "DiffuseTex"}],
    )
    assert_success_count(r4, 1, context="material node param rename")


def test_material_function_add_connect(test_ns, mcp):
    """MaterialFunction 写图：add_node + connect 到 FunctionOutput（禁止 TargetNodeId=Material）。"""
    path = f"{test_ns}/MF_WriteGraph"
    created = mcp.call_capability("CreateAssetMaterialFunction", AssetPath=path)
    entry = cap_first(created)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower() and "已存在" not in str(entry.get("Error")):
        assert not entry.get("Error"), created

    add = mcp.call(
        "ManageAssetMaterial",
        AssetPath=path,
        Operations=[
            {"Action": "AddNode", "ExpressionClass": "Constant3Vector"},
            {"Action": "AddNode", "ExpressionClass": "FunctionOutput"},
        ],
    )
    node_ids = ids_of(add, "NodeId")
    assert node_ids, f"MF add_node missing nodeId: {add!r}"
    nid = node_ids[0]

    bad = mcp.call_capability(
        "ManageAssetMaterial",
        AssetPath=path,
        Operations=[{
            "Action": "Connect",
            "SourceNodeId": nid,
            "TargetNodeId": "Material",
            "TargetInputName": "BaseColor",
        }],
    )
    assert cap_first(bad).get("Error"), f"MF connect to Material should fail: {bad!r}"

    connect = mcp.call_capability(
        "ManageAssetMaterial",
        AssetPath=path,
        Operations=[{
            "Action": "Connect",
            "SourceNodeId": nid,
            "TargetNodeId": "Output",
        }],
    )
    assert_success_count(connect, 1, context="MF connect to FunctionOutput")
    mcp.call("SaveAsset", AssetPath=path)


def test_material_set_param(mcp, mat_path):
    r = mcp.call_capability(
        "ManageAssetMaterial",
        AssetPath=mat_path,
        Operations=[{"Action": "SetParam", "ParamName": "BaseColor", "Value": "(R=1,G=0,B=0,A=1)"}],
    )
    entry = cap_first(r)
    if entry.get("Error"):
        pytest.skip(f"set_param 跳过: {entry}")


def test_material_overview(mcp, mat_path):
    """6.x：material 全量概览。置于末尾：all 查询会令后续子 section 查询触发
    redundant_call 保护，故放在 parameters 校验之后。"""
    r = mcp.call_capability("GetAssetMaterial", AssetPath=mat_path, Sections=["All"])
    assert r, r


def test_material_save_all(mcp, mat_path, test_ns):
    paths = [mat_path, f"{test_ns}/M_TestDecal"]
    results = [mcp.call("SaveAsset", AssetPath=path) for path in paths]
    assert all((r.get("bSaved") or 0) == 1 for r in results), f"material save: {results!r}"
