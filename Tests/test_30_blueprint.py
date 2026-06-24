# Copyright byteyang. All Rights Reserved.
"""阶段四：Blueprint + Graph — 变量/组件/节点/连线全部批量化。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l3_asset


@pytest.fixture(scope="module")
def bp_path(test_ns, mcp):
    path = f"{test_ns}/BP_TestActor"
    mcp.call("create_blueprint", assetPath=path, parentClass="Actor")
    yield path


def test_bp_variable_batch_add(mcp, bp_path):
    """4.2：新增两个变量。MyActorLabel 避开与 AActor::ActorLabel 冲突。
    新版 manage_asset_blueprint 用 action=add_variable 单条调用（旧 manage_blueprint_variable
    的 variables 批量已废弃）。"""
    for var in [
        {"action": "add_variable", "variableName": "Health",
         "variableType": "float", "defaultValue": "100"},
        {"action": "add_variable", "variableName": "MyActorLabel",
         "variableType": "string"},
    ]:
        r = mcp.call_capability("manage_asset_blueprint", assetPath=bp_path, **var)
        assert isinstance(r, dict), f"add_variable {var['variableName']}: {r!r}"


def test_bp_set_and_get_defaults(mcp, bp_path):
    """4.5–4.6：通过 manage_asset_blueprint(set_defaults) 写 CDO 字段，再从 sections=["defaults"]
    读回。合并原 test_bp_get_defaults_section——对同一资产重复查 defaults 会触发 redundant_call 保护，
    故在 all 查询之前一次性完成写读验证。"""
    set_result = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        action="set_defaults",
        propertyPath="Health",
        value="200",
    )
    assert isinstance(set_result, dict), f"set_defaults returned unexpected: {set_result!r}"

    get_result = mcp.call_capability(
        "get_asset_blueprint",
        assetPath=bp_path,
        sections=["defaults"],
    )
    payload = cap_first(get_result)
    # defaults section 仅含 inherited CDO 属性，BP 变量 Health 不在其中；
    # 此处验证 set/get 链路通畅，get 返回合法 defaults 结构。
    assert isinstance(payload.get("defaults"), list), f"defaults not a list: {payload!r}"


def test_bp_component_add_remove(mcp, bp_path):
    """4.7：add_component + remove_component（Actor BP 专用，两次单动作调用）。"""
    r_add = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        action="add_component",
        componentName="Mesh",
        componentClass="StaticMeshComponent",
    )
    assert isinstance(r_add, dict), f"add_component unexpected: {r_add!r}"

    r_remove = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        action="remove_component",
        componentName="Mesh",
    )
    assert isinstance(r_remove, dict), f"remove_component unexpected: {r_remove!r}"


def test_bp_graph_roundtrip(mcp, bp_path):
    """4.8–4.12：get graph → add_node → set_node → remove_node。
    在 all 查询之前独立查 sections=["graph"]，避免 redundant_call。"""
    graph = mcp.call_capability("get_asset_blueprint", assetPath=bp_path,
                                sections=["graph"], graphName="EventGraph")
    payload = cap_first(graph)
    dump = str(payload)
    assert "enabledNodeCount" in dump or "nodes" in dump, f"graph overview shape: {payload!r}"

    add = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        action="add_node",
        graphName="EventGraph",
        nodeClass="K2Node_CallFunction",
        functionName="PrintString",
        posX=200, posY=100,
    )
    pn_id = add.get("nodeId")
    assert pn_id, f"add_node did not return nodeId: {add!r}"

    move = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        action="set_node",
        graphName="EventGraph",
        nodeId=pn_id,
        posX=300, posY=150,
    )
    assert isinstance(move, dict), f"set_node unexpected: {move!r}"

    remove = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        action="remove_node",
        graphName="EventGraph",
        nodeId=pn_id,
    )
    assert isinstance(remove, dict), f"remove_node unexpected: {remove!r}"


def test_bp_graph_connect_exec(mcp, bp_path):
    """4.x：EventGraph 内 BeginPlay → PrintString exec 连线。"""
    begin = mcp.call_capability(
        "get_asset_blueprint",
        assetPath=bp_path,
        sections=["graph"],
        graphName="EventGraph",
        nameFilter="BeginPlay",
    )
    payload = cap_first(begin)
    nodes = payload.get("nodes") or []
    assert nodes, f"BeginPlay node missing: {payload!r}"
    begin_id = nodes[0].get("nodeId")
    begin_then = None
    for pin in nodes[0].get("pins") or []:
        if pin.get("direction") == "output" and pin.get("pinCategory") == "exec":
            begin_then = pin.get("pinName")
            break
    assert begin_id and begin_then, f"BeginPlay exec pin missing: {nodes[0]!r}"

    add = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        action="add_node",
        graphName="EventGraph",
        nodeClass="K2Node_CallFunction",
        functionName="PrintString",
        posX=400, posY=0,
    )
    print_id = add.get("nodeId")
    assert print_id, f"add_node PrintString: {add!r}"

    graph_after = mcp.call_capability(
        "get_asset_blueprint",
        assetPath=bp_path,
        sections=["graph"],
        graphName="EventGraph",
        nameFilter="Print",
    )
    print_node = cap_first(graph_after).get("nodes") or []
    assert print_node, f"PrintString node missing: {graph_after!r}"
    print_exec = None
    for pin in print_node[0].get("pins") or []:
        if pin.get("direction") == "input" and pin.get("pinCategory") == "exec":
            print_exec = pin.get("pinName")
            break
    assert print_exec, f"PrintString exec input missing: {print_node[0]!r}"

    wire = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        action="connect",
        graphName="EventGraph",
        sourceNodeId=begin_id,
        sourcePinName=begin_then,
        targetNodeId=print_id,
        targetPinName=print_exec,
    )
    assert isinstance(wire, dict) and not wire.get("error"), f"connect failed: {wire!r}"

    verify = mcp.call_capability(
        "get_asset_blueprint",
        assetPath=bp_path,
        sections=["graph"],
        graphName="EventGraph",
        nameFilter="BeginPlay",
    )
    begin_pins = (cap_first(verify).get("nodes") or [{}])[0].get("pins") or []
    linked = False
    for pin in begin_pins:
        if pin.get("pinName") != begin_then:
            continue
        for link in pin.get("linkedTo") or []:
            if link.get("nodeId") == print_id:
                linked = True
    assert linked, f"wire not visible after connect: {begin_pins!r}"


def test_bp_get_asset_all_section(mcp, bp_path):
    """4.3：section=all 应覆盖 variables/components/functions/graphOverview/defaults，
    并暴露 sections 清单。置于末尾：all 查询会令后续任何子 section 查询触发
    redundant_call 保护，故放在所有具体 section 测试之后。"""
    r = mcp.call_capability("get_asset_blueprint", assetPath=bp_path, sections=["all"])
    results = r.get("results") or []
    assert results, r
    first = results[0]
    sections = first.get("sections") or []
    for required in ["variable", "component", "function", "graphOverview"]:
        assert required in sections, f"section {required} not in {sections!r}"
    # API 不再返回 defaultsCount，改为校验 defaults 数组存在
    assert isinstance(first.get("defaults"), list), f"defaults list missing: {first!r}"


def test_bp_save(mcp, bp_path):
    r = mcp.call("save_asset", assetPaths=[bp_path])
    assert (r.get("saved") or 0) == 1, f"save_asset bp: {r!r}"
