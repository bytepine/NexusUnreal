# Copyright byteyang. All Rights Reserved.
"""阶段六：Material — 批量节点 + 连线 + 节点反射穿透。"""

from __future__ import annotations

import pytest

from _framework.assertions import assert_success_count, ids_of

pytestmark = pytest.mark.l3_asset


@pytest.fixture(scope="module")
def mat_path(test_ns, mcp):
    p = f"{test_ns}/M_TestMat"
    mcp.call("create_material", assetPath=p)
    yield p


def test_create_decal(test_ns, mcp):
    p = f"{test_ns}/M_TestDecal"
    mcp.call("create_material", assetPath=p, materialDomain="DeferredDecal")


def test_material_node_add_connect_remove(mcp, mat_path):
    add = mcp.call(
        "manage_material",
        assetPath=mat_path,
        operations=[{"action": "add_node", "expressionClass": "Constant3Vector"}],
    )
    node_ids = ids_of(add, "nodeId")
    assert node_ids, f"add_node missing nodeId: {add!r}"
    nid = node_ids[0]

    connect = mcp.call_capability(
        "manage_asset_material",
        assetPath=mat_path,
        operations=[{
            "action": "connect",
            "sourceNodeId": nid,
            "targetNodeId": "Material",
            "targetInputName": "BaseColor",
        }],
    )
    assert_success_count(connect, 1, context="material connect")

    recompile = mcp.call(
        "manage_material",
        assetPath=mat_path,
        operations=[{"action": "recompile"}],
    )
    assert_success_count(recompile, 1, context="material recompile")

    disconnect = mcp.call_capability(
        "manage_asset_material",
        assetPath=mat_path,
        operations=[
            {"action": "disconnect", "targetNodeId": "Material", "targetInputName": "BaseColor"},
            {"action": "disconnect_all", "sourceNodeId": nid},
        ],
    )
    assert_success_count(disconnect, 2, context="material disconnect batch")

    remove = mcp.call(
        "manage_material",
        assetPath=mat_path,
        operations=[{"action": "remove_node", "nodeId": nid}],
    )
    assert_success_count(remove, 1, context="material remove node")


def test_material_two_step_texture_param(mcp, mat_path):
    """6.9：两步法关键用例：add_node + set_node + recompile 一次批量完成。
    置于 overview 之前：overview 的 sections=["all"] 会令后续 section 查询触发
    redundant_call 保护，故 parameters 校验先于 all。"""
    r = mcp.call(
        "manage_material",
        assetPath=mat_path,
        operations=[
            {"action": "add_node",
             "expressionClass": "TextureSampleParameter2D",
             "posX": -400, "posY": 0},
        ],
    )
    ids = ids_of(r, "nodeId")
    assert ids, f"add_node texture missing nodeId: {r!r}"
    nid = ids[0]

    r2 = mcp.call(
        "manage_material",
        assetPath=mat_path,
        operations=[
            {"action": "set_node", "nodeId": nid, "parameterName": "BaseTex"},
            {"action": "recompile"},
        ],
    )
    assert_success_count(r2, 2, context="material two-step")

    # 6.10：set_node 应已应用 parameterName=BaseTex（r2 results[0] 的 appliedFields 确认）
    set_entry = (r2.get("results") or [{}])[0]
    assert set_entry.get("parameterName") == "BaseTex" or \
           "parameterName" in (set_entry.get("appliedFields") or []), \
           f"set_node did not apply parameterName BaseTex: {r2!r}"

    # get_asset_material params section 软校验：set_node 写入的参数名在部分版本下
    # 需材质保存后才在 params 列出，此处仅验证查询链路不报错
    r3 = mcp.call_capability("get_asset_material", assetPath=mat_path, sections=["params"])
    assert isinstance(r3, dict), f"get_asset_material params: {r3!r}"

    # 6.11：用 manage_asset_material set_node 修改参数名（等价于旧 set_property 节点反射写路径）
    r4 = mcp.call_capability(
        "manage_asset_material",
        assetPath=mat_path,
        operations=[{"action": "set_node", "nodeId": nid, "parameterName": "DiffuseTex"}],
    )
    assert_success_count(r4, 1, context="material node param rename")


def test_material_overview(mcp, mat_path):
    """6.x：material 全量概览。置于末尾：all 查询会令后续子 section 查询触发
    redundant_call 保护，故放在 parameters 校验之后。"""
    r = mcp.call_capability("get_asset_material", assetPath=mat_path, sections=["all"])
    assert r, r


def test_material_save_all(mcp, mat_path, test_ns):
    paths = [mat_path, f"{test_ns}/M_TestDecal"]
    r = mcp.call("save_asset", assetPaths=paths)
    assert (r.get("saved") or 0) >= 1, f"material save: {r!r}"
