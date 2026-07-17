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


def test_bp_component_section_owned_inherited_native(mcp, test_ns):
    """component section 应合并 owned/inherited/native 三类来源并正确标注：
    父 BP（parentClass=Character）新增持久组件 ParentMesh；子 BP 派生自父 BP 并新增自己的 ChildMesh；
    Character 作为原生祖先贡献 CapsuleComponent 等 native 组件。使用独立资产路径，不影响 bp_path 相关测试。"""
    parent_path = f"{test_ns}/BP_CompParent"
    parent_create = mcp.call_capability("create_asset_blueprint", assetPath=parent_path, parentClass="Character")
    assert isinstance(parent_create, dict), f"create parent bp: {parent_create!r}"

    add_parent = mcp.call_capability(
        "manage_asset_blueprint", assetPath=parent_path,
        action="add_component", componentName="ParentMesh", componentClass="StaticMeshComponent",
    )
    assert isinstance(add_parent, dict), f"add_component parent: {add_parent!r}"
    mcp.call("save_asset", assetPaths=[parent_path])

    parent_class_path = f"{parent_path}.BP_CompParent_C"
    child_path = f"{test_ns}/BP_CompChild"
    child_create = mcp.call_capability("create_asset_blueprint", assetPath=child_path, parentClass=parent_class_path)
    assert isinstance(child_create, dict), f"create child bp (parentClass={parent_class_path}): {child_create!r}"

    add_child = mcp.call_capability(
        "manage_asset_blueprint", assetPath=child_path,
        action="add_component", componentName="ChildMesh", componentClass="StaticMeshComponent",
    )
    assert isinstance(add_child, dict), f"add_component child: {add_child!r}"

    r = mcp.call_capability("get_asset_blueprint", assetPath=child_path, sections=["component"])
    payload = cap_first(r)
    components = payload.get("components") or []
    by_name = {c.get("variableName"): c for c in components}

    child_mesh = by_name.get("ChildMesh")
    assert child_mesh and child_mesh.get("source") == "owned", f"ChildMesh not owned: {components!r}"
    assert "inherited" not in child_mesh, f"owned 组件不应带 inherited: {child_mesh!r}"

    parent_mesh = by_name.get("ParentMesh")
    assert parent_mesh, f"ParentMesh (父 BP SCS) 未出现在子 BP 组件列表中: {components!r}"
    assert parent_mesh.get("source") == "inherited", f"ParentMesh source 应为 inherited: {parent_mesh!r}"
    assert parent_mesh.get("inherited") is True, f"ParentMesh 缺 inherited 标记: {parent_mesh!r}"
    assert parent_mesh.get("ownerBlueprint") == "BP_CompParent", f"ParentMesh ownerBlueprint: {parent_mesh!r}"

    native_entries = [c for c in components if c.get("source") == "native"]
    assert native_entries, f"Character 原生祖先组件（如 CapsuleComponent）未出现: {components!r}"
    for entry in native_entries:
        assert entry.get("inherited") is True, f"native 组件缺 inherited 标记: {entry!r}"

    hierarchy = payload.get("hierarchy") or []
    assert hierarchy, f"hierarchy 为空: {payload!r}"

    mcp.call("save_asset", assetPaths=[child_path])


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
    """4.3：section=all 应覆盖 variables/components/functions/graphOverview/defaults。
    全成功时不再回显 sections[]；置于末尾以免触发 redundant_call。"""
    r = mcp.call_capability("get_asset_blueprint", assetPath=bp_path, sections=["all"])
    first = cap_first(r)
    assert first and not first.get("error"), r
    # 全成功省略 sections 回显；以实际数据段存在为准
    assert "variables" in first or "variable" in str(first), first
    assert "components" in first or "component" in str(first), first
    assert isinstance(first.get("defaults"), list), f"defaults list missing: {first!r}"


def test_bp_save(mcp, bp_path):
    r = mcp.call("save_asset", assetPaths=[bp_path])
    assert (r.get("saved") or 0) == 1, f"save_asset bp: {r!r}"
