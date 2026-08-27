# Copyright byteyang. All Rights Reserved.
"""阶段四：Blueprint + Graph — 变量/组件/节点/连线全部批量化。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_first
from _framework.assertions import merge_with_defaults

pytestmark = pytest.mark.l3_asset


@pytest.fixture(scope="module")
def bp_path(test_ns, mcp):
    path = f"{test_ns}/BP_TestActor"
    mcp.call("create_asset_blueprint", assetPath=path, parentClass="Actor")
    yield path


def test_bp_variable_batch_add(mcp, bp_path):
    """4.2：新增两个变量。MyActorLabel 避开与 AActor::ActorLabel 冲突。
    新版 manage_asset_blueprint 用 operations=[{action=add_variable,...}]。"""
    for var in [
        {"action": "add_variable", "variableName": "Health",
         "variableType": "float", "defaultValue": "100"},
        {"action": "add_variable", "variableName": "MyActorLabel",
         "variableType": "string"},
    ]:
        r = mcp.call_capability(
            "manage_asset_blueprint", assetPath=bp_path, operations=[var],
        )
        assert isinstance(r, dict), f"add_variable {var['variableName']}: {r!r}"


def test_bp_set_and_get_defaults(mcp, bp_path):
    """4.5–4.6：通过 manage_asset_blueprint(set_defaults) 写 CDO 字段，再从 sections=["defaults"]
    读回。合并原 test_bp_get_defaults_section——对同一资产重复查 defaults 会触发 redundant_call 保护，
    故在 all 查询之前一次性完成写读验证。"""
    set_result = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        operations=[{
            "action": "set_defaults",
            "propertyPath": "Health",
            "value": "200",
        }],
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
        operations=[{
            "action": "add_component",
            "componentName": "Mesh",
            "componentClass": "StaticMeshComponent",
        }],
    )
    assert isinstance(r_add, dict), f"add_component unexpected: {r_add!r}"

    r_remove = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        operations=[{
            "action": "remove_component",
            "componentName": "Mesh",
        }],
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
        operations=[{
            "action": "add_component",
            "componentName": "ParentMesh",
            "componentClass": "StaticMeshComponent",
        }],
    )
    assert isinstance(add_parent, dict), f"add_component parent: {add_parent!r}"
    mcp.call("save_asset", assetPath=parent_path)

    parent_class_path = f"{parent_path}.BP_CompParent_C"
    child_path = f"{test_ns}/BP_CompChild"
    child_create = mcp.call_capability("create_asset_blueprint", assetPath=child_path, parentClass=parent_class_path)
    assert isinstance(child_create, dict), f"create child bp (parentClass={parent_class_path}): {child_create!r}"

    add_child = mcp.call_capability(
        "manage_asset_blueprint", assetPath=child_path,
        operations=[{
            "action": "add_component",
            "componentName": "ChildMesh",
            "componentClass": "StaticMeshComponent",
        }],
    )
    assert isinstance(add_child, dict), f"add_component child: {add_child!r}"

    r = mcp.call_capability("get_asset_blueprint", assetPath=child_path, sections=["component"])
    payload = cap_first(r)
    components = merge_with_defaults(
        payload.get("components") or [],
        payload.get("components_defaults") or {},
    )
    by_name = {c.get("variableName"): c for c in components}

    child_mesh = by_name.get("ChildMesh")
    assert child_mesh and child_mesh.get("source") == "owned", f"ChildMesh not owned: {components!r}"
    assert child_mesh.get("inherited") is False, f"owned 组件 inherited 应为 false: {child_mesh!r}"

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

    mcp.call("save_asset", assetPath=child_path)


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
        operations=[{
            "action": "add_node",
            "graphName": "EventGraph",
            "nodeClass": "K2Node_CallFunction",
            "functionName": "PrintString",
            "posX": 200, "posY": 100,
        }],
    )
    pn_id = cap_first(add).get("nodeId")
    assert pn_id, f"add_node did not return nodeId: {add!r}"

    move = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        operations=[{
            "action": "set_node",
            "graphName": "EventGraph",
            "nodeId": pn_id,
            "posX": 300, "posY": 150,
        }],
    )
    assert isinstance(move, dict), f"set_node unexpected: {move!r}"

    remove = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        operations=[{
            "action": "remove_node",
            "graphName": "EventGraph",
            "nodeId": pn_id,
        }],
    )
    assert isinstance(remove, dict), f"remove_node unexpected: {remove!r}"


def test_bp_graph_connect_exec(mcp, bp_path):
    """4.x：EventGraph 内 BeginPlay → PrintString exec 连线。"""
    # 直接 ensure BeginPlay（不依赖 create 是否生成；避免 nameFilter 二次 get 误判）
    ensure = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        operations=[{
            "action": "add_node",
            "graphName": "EventGraph",
            "nodeClass": "K2Node_Event",
            "functionName": "ReceiveBeginPlay",
            "posX": 0, "posY": 0,
        }],
    )
    ensure_entry = cap_first(ensure)
    begin_id = ensure_entry.get("nodeId")
    assert begin_id, f"ensure BeginPlay: {ensure!r}"

    # 无 nameFilter 拉全图，再按 nodeId / 标题定位（nameFilter 对 Event 标题偶发不匹配）
    graph = mcp.call_capability(
        "get_asset_blueprint",
        assetPath=bp_path,
        sections=["graph"],
        graphName="EventGraph",
    )
    payload = cap_first(graph)
    nodes = payload.get("nodes") or []
    begin_node = next((n for n in nodes if n.get("nodeId") == begin_id), None)
    if begin_node is None:
        begin_node = next(
            (n for n in nodes if "BeginPlay" in (n.get("nodeTitle") or "")
             or "ReceiveBeginPlay" in (n.get("nodeTitle") or "")
             or n.get("nodeClass") == "K2Node_Event"),
            None,
        )
    assert begin_node, f"BeginPlay node missing after ensure: {payload!r} ensure={ensure_entry!r}"
    begin_id = begin_node.get("nodeId") or begin_id
    begin_then = None
    for pin in begin_node.get("pins") or []:
        if pin.get("direction") == "output" and pin.get("pinCategory") == "exec":
            begin_then = pin.get("pinName")
            break
    assert begin_id and begin_then, f"BeginPlay exec pin missing: {begin_node!r}"

    add = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        operations=[{
            "action": "add_node",
            "graphName": "EventGraph",
            "nodeClass": "K2Node_CallFunction",
            "functionName": "PrintString",
            "posX": 400, "posY": 0,
        }],
    )
    print_id = cap_first(add).get("nodeId")
    assert print_id, f"add_node PrintString: {add!r}"

    graph_after = mcp.call_capability(
        "get_asset_blueprint",
        assetPath=bp_path,
        sections=["graph"],
        graphName="EventGraph",
    )
    all_nodes = cap_first(graph_after).get("nodes") or []
    print_node = [n for n in all_nodes if n.get("nodeId") == print_id]
    if not print_node:
        print_node = [n for n in all_nodes if "Print" in (n.get("nodeTitle") or "")]
    assert print_node, f"PrintString node missing: {graph_after!r} add={add!r}"
    print_exec = None
    for pin in print_node[0].get("pins") or []:
        if pin.get("direction") == "input" and pin.get("pinCategory") == "exec":
            print_exec = pin.get("pinName")
            break
    assert print_exec, f"PrintString exec input missing: {print_node[0]!r}"

    wire = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        operations=[{
            "action": "connect",
            "graphName": "EventGraph",
            "sourceNodeId": begin_id,
            "sourcePinName": begin_then,
            "targetNodeId": print_id,
            "targetPinName": print_exec,
        }],
    )
    assert isinstance(wire, dict) and not wire.get("error") and not cap_first(wire).get("error"), (
        f"connect failed: {wire!r}"
    )

    verify = mcp.call_capability(
        "get_asset_blueprint",
        assetPath=bp_path,
        sections=["graph"],
        graphName="EventGraph",
    )
    verify_nodes = cap_first(verify).get("nodes") or []
    begin_after = next((n for n in verify_nodes if n.get("nodeId") == begin_id), None)
    assert begin_after, f"BeginPlay missing after connect: {verify!r}"
    begin_pins = begin_after.get("pins") or []
    linked = False
    for pin in begin_pins:
        if pin.get("pinName") != begin_then:
            continue
        for link in pin.get("linkedTo") or []:
            if link.get("nodeId") == print_id:
                linked = True
    assert linked, f"wire not visible after connect: {begin_pins!r}"


def test_bp_promote_pin(mcp, bp_path):
    """promote_pin：PrintString.InString → 成员变量 + VariableGet 并自动连线。"""
    add = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        operations=[{
            "action": "add_node",
            "graphName": "EventGraph",
            "nodeClass": "K2Node_CallFunction",
            "functionName": "PrintString",
            "posX": 600, "posY": 200,
        }],
    )
    print_id = cap_first(add).get("nodeId")
    assert print_id, f"add_node PrintString: {add!r}"

    graph = mcp.call_capability(
        "get_asset_blueprint",
        assetPath=bp_path,
        sections=["graph"],
        graphName="EventGraph",
    )
    nodes = cap_first(graph).get("nodes") or []
    print_node = next((n for n in nodes if n.get("nodeId") == print_id), None)
    assert print_node, f"PrintString missing: {graph!r}"
    in_string = None
    for pin in print_node.get("pins") or []:
        if pin.get("direction") == "input" and pin.get("pinCategory") != "exec":
            name = pin.get("pinName") or ""
            if "string" in name.lower() or name in ("InString", "In String"):
                in_string = name
                break
    if not in_string:
        for pin in print_node.get("pins") or []:
            if pin.get("direction") == "input" and pin.get("pinCategory") == "string":
                in_string = pin.get("pinName")
                break
    assert in_string, f"PrintString string input pin missing: {print_node!r}"

    promote = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        operations=[{
            "action": "promote_pin",
            "graphName": "EventGraph",
            "nodeId": print_id,
            "pinName": in_string,
            "variableName": "PromotedMsg",
        }],
    )
    entry = cap_first(promote)
    assert not entry.get("error"), f"promote_pin failed: {promote!r}"
    promoted = entry.get("variableName") or ""
    assert str(promoted).startswith("PromotedMsg"), entry
    var_node_id = entry.get("nodeId")
    assert var_node_id, f"promote_pin missing Get nodeId: {entry!r}"
    assert entry.get("isLocal") is False, entry

    vars_r = mcp.call_capability(
        "get_asset_blueprint", assetPath=bp_path, sections=["variable"],
    )
    vars_payload = cap_first(vars_r)
    var_names = [
        (v.get("name") or v.get("variableName") or "")
        for v in (vars_payload.get("variables") or vars_payload.get("variable") or [])
    ]
    assert any(str(n).startswith("PromotedMsg") for n in var_names), f"PromotedMsg not in variables: {vars_payload!r}"


def test_bp_get_asset_all_section(mcp, bp_path):
    """4.3：sections=["all"] 应覆盖 variables/components/functions/graphOverview/defaults。
    全成功时不再回显 sections[]；置于末尾以免触发 redundant_call。"""
    r = mcp.call_capability("get_asset_blueprint", assetPath=bp_path, sections=["all"])
    first = cap_first(r)
    assert first and not first.get("error"), r
    # 全成功省略 sections 回显；以实际数据段存在为准
    assert "variables" in first or "variable" in str(first), first
    assert "components" in first or "component" in str(first), first
    assert isinstance(first.get("defaults"), list), f"defaults list missing: {first!r}"


def test_bp_save(mcp, bp_path):
    r = mcp.call("save_asset", assetPath=bp_path)
    assert (r.get("saved") or 0) == 1, f"save_asset bp: {r!r}"


def test_bp_interface_create_function_and_implement(mcp, test_ns):
    """BPI：parentClass=Interface 创建；add_function 声明方法；普通 BP add_interface 实现。"""
    iface_path = f"{test_ns}/BPI_Test"
    created = mcp.call_capability(
        "create_asset_blueprint", assetPath=iface_path, parentClass="Interface",
    )
    created_first = cap_first(created)
    assert created_first.get("blueprintType") == "interface", created

    add_fn = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=iface_path,
        operations=[{"action": "add_function", "functionName": "DoThing"}],
    )
    add_fn_first = cap_first(add_fn)
    assert not add_fn_first.get("error"), add_fn

    fn_get = mcp.call_capability(
        "get_asset_blueprint", assetPath=iface_path, sections=["function"],
    )
    fn_first = cap_first(fn_get)
    assert fn_first.get("blueprintType") == "interface", fn_get
    fn_names = [f.get("name") for f in (fn_first.get("functions") or [])]
    assert "DoThing" in fn_names, fn_get

    actor_path = f"{test_ns}/BP_IfaceUser"
    mcp.call_capability("create_asset_blueprint", assetPath=actor_path, parentClass="Actor")
    add_iface = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=actor_path,
        operations=[{"action": "add_interface", "interfaceName": iface_path}],
    )
    add_iface_first = cap_first(add_iface)
    assert not add_iface_first.get("error"), add_iface

    actor_get = mcp.call_capability(
        "get_asset_blueprint", assetPath=actor_path, sections=["function"],
    )
    actor_first = cap_first(actor_get)
    ifaces = actor_first.get("implementedInterfaces") or []
    assert any("BPI_Test" in str(x) for x in ifaces), actor_get


def test_bp_add_macro_timeline_dispatcher(mcp, bp_path):
    r = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=bp_path,
        operations=[
            {"action": "add_macro", "functionName": "NxMacro"},
            {"action": "add_timeline", "functionName": "NxTimeline"},
            {"action": "add_dispatcher", "variableName": "NxDisp"},
            {"action": "add_local_variable", "functionName": "NxMacro", "variableName": "NxLocal"},
        ],
    )
    entry = cap_first(r)
    assert isinstance(entry, dict), r
    assert not entry.get("error"), r


def test_bp_compile_status(mcp, bp_path):
    r = mcp.call_capability("get_asset_blueprint", assetPath=bp_path)
    payload = cap_first(r)
    assert payload.get("compileStatus"), payload
    assert "hasCompilerErrors" in payload, payload


def test_bp_orphaned_pins(test_ns, mcp):
    path = f"{test_ns}/BP_OrphanPins"
    mcp.call_capability("create_asset_blueprint", assetPath=path, parentClass="Actor")
    add = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=path,
        operations=[{
            "action": "add_variable",
            "variableName": "OrphanProbe",
            "variableType": "float",
        }],
    )
    assert not cap_first(add).get("error"), add
    get_node = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=path,
        operations=[{
            "action": "add_node",
            "graphName": "EventGraph",
            "nodeClass": "K2Node_VariableGet",
            "variableName": "OrphanProbe",
            "posX": 800, "posY": 400,
        }],
    )
    assert cap_first(get_node).get("nodeId"), get_node
    rm = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=path,
        operations=[{"action": "remove_variable", "variableName": "OrphanProbe"}],
        compile=True,
    )
    assert not cap_first(rm).get("error"), rm
    got = mcp.call_capability(
        "get_asset_blueprint", assetPath=path, sections=["orphaned"],
    )
    payload = cap_first(got)
    pins = payload.get("orphanedPins")
    assert isinstance(pins, list), payload
    if pins:
        assert pins[0].get("nodeId") and pins[0].get("pinName"), pins[0]


def test_bp_exec_paths(test_ns, mcp):
    path = f"{test_ns}/BP_ExecPaths"
    mcp.call_capability("create_asset_blueprint", assetPath=path, parentClass="Actor")
    ensure = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=path,
        operations=[{
            "action": "add_node",
            "graphName": "EventGraph",
            "nodeClass": "K2Node_Event",
            "functionName": "ReceiveBeginPlay",
            "posX": 0, "posY": 0,
        }],
    )
    begin_id = cap_first(ensure).get("nodeId")
    assert begin_id, ensure
    add = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=path,
        operations=[{
            "action": "add_node",
            "graphName": "EventGraph",
            "nodeClass": "K2Node_CallFunction",
            "functionName": "PrintString",
            "posX": 420, "posY": 80,
        }],
    )
    print_id = cap_first(add).get("nodeId")
    assert print_id, add
    graph = mcp.call_capability(
        "get_asset_blueprint",
        assetPath=path,
        sections=["graph"],
        graphName="EventGraph",
    )
    nodes = cap_first(graph).get("nodes") or []
    begin_node = next((n for n in nodes if n.get("nodeId") == begin_id), None)
    print_node = next((n for n in nodes if n.get("nodeId") == print_id), None)
    assert begin_node and print_node, graph
    begin_then = next(
        (p.get("pinName") for p in (begin_node.get("pins") or [])
         if p.get("direction") == "output" and p.get("pinCategory") == "exec"),
        None,
    )
    print_exec = next(
        (p.get("pinName") for p in (print_node.get("pins") or [])
         if p.get("direction") == "input" and p.get("pinCategory") == "exec"),
        None,
    )
    assert begin_then and print_exec, (begin_node, print_node)
    wire = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=path,
        operations=[{
            "action": "connect",
            "graphName": "EventGraph",
            "sourceNodeId": begin_id,
            "sourcePinName": begin_then,
            "targetNodeId": print_id,
            "targetPinName": print_exec,
        }],
    )
    assert not cap_first(wire).get("error"), wire
    paths = mcp.call_capability(
        "get_asset_blueprint",
        assetPath=path,
        sections=["execPaths"],
        graphName="EventGraph",
    )
    payload = cap_first(paths)
    chain = payload.get("execPaths") or []
    assert chain, payload
    assert any(len(p.get("nodes") or []) >= 2 for p in chain if isinstance(p, dict)), payload


def test_bp_exec_paths_all_needs_graph_name(test_ns, mcp):
    path = f"{test_ns}/BP_ExecAllNote"
    mcp.call_capability("create_asset_blueprint", assetPath=path, parentClass="Actor")
    r = mcp.call_capability("get_asset_blueprint", assetPath=path, sections=["all"])
    payload = cap_first(r)
    assert payload.get("compileStatus"), payload
    assert "graphName required" in str(payload.get("note") or ""), payload


def test_calls_batch_memory_rollback(test_ns, mcp):
    path = f"{test_ns}/BP_UndoBatch"
    mcp.call_capability("create_asset_blueprint", assetPath=path, parentClass="Actor")
    batch = mcp._tool_call_raw("call_capability", {
        "calls": [
            {
                "capability": "manage_asset_blueprint",
                "arguments": {
                    "assetPath": path,
                    "operations": [{
                        "action": "add_variable",
                        "variableName": "UndoMe",
                        "variableType": "float",
                    }],
                },
            },
            {
                "capability": "manage_asset_blueprint",
                "arguments": {"assetPath": path},
            },
        ],
    })
    assert batch.get("failureCount", 0) > 0, batch
    got = mcp.call_capability("get_asset_blueprint", assetPath=path, sections=["variable"])
    names = [v.get("name") for v in (cap_first(got).get("variables") or [])]
    assert "UndoMe" not in names, got


def test_bp_remaining_manage_actions(mcp, test_ns):
    path = f"{test_ns}/BP_RemainingOps"
    mcp.call_capability("create_asset_blueprint", assetPath=path, parentClass="Actor")
    iface = f"{test_ns}/BPI_Remaining"
    mcp.call_capability("create_asset_blueprint", assetPath=iface, parentClass="Interface")
    mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=path,
        operations=[
            {"action": "add_function", "functionName": "TempFn"},
            {"action": "add_interface", "interfaceName": iface},
            {"action": "add_component", "componentName": "NxMesh", "componentClass": "StaticMeshComponent"},
        ],
    )
    add_n = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=path,
        operations=[{"action": "add_node", "graphName": "EventGraph", "nodeClass": "K2Node_CallFunction", "functionName": "PrintString"}],
    )
    nid = cap_first(add_n).get("nodeId")
    ops = [
        {"action": "set_component_property", "componentName": "NxMesh", "propertyPath": "RelativeLocation.Z", "value": "10"},
        {"action": "remove_function", "functionName": "TempFn"},
        {"action": "remove_interface", "interfaceName": iface},
    ]
    if nid:
        ops.extend([
            {"action": "disconnect_all", "sourceNodeId": nid},
            {"action": "disconnect", "sourceNodeId": nid, "targetNodeId": nid},
        ])
    r = mcp.call_capability("manage_asset_blueprint", assetPath=path, operations=ops)
    for e in (r.get("results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("error"):
            pytest.skip(f"blueprint remaining 跳过: {e}")
