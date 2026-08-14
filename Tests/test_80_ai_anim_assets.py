# Copyright byteyang. All Rights Reserved.
"""阶段九：AI + 动画资产 — BehaviorTree / AnimBlueprint / AnimMontage。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import resolve_skeleton, first_asset_path
from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l3_asset


@pytest.fixture(scope="module")
def template_skeleton(mcp):
    """Mannequin Skeleton；search 失败时回退已知路径。"""
    return resolve_skeleton(mcp)


def test_behavior_tree_create(test_ns, mcp):
    bt = f"{test_ns}/BT_TestAI"
    bb = f"{test_ns}/BB_TestAI"
    # create_asset_behavior_tree 仅 assetPath；BB 另建后可用 manage set_blackboard 关联
    mcp.call("create_asset_blackboard", assetPath=bb)
    r = mcp.call("create_asset_behavior_tree", assetPath=bt)
    assert r, f"create_asset_behavior_tree returned empty: {r!r}"


def test_create_blackboard_capability(test_ns, mcp, require_tools):
    """`create_asset_blackboard` 经全局 `call_capability` 调用。"""
    require_tools("call_capability")
    bb = f"{test_ns}/BB_CreateBlackboardCap"
    r = mcp.call_capability("create_asset_blackboard", assetPath=bb)
    entry = cap_first(r)
    assert not entry.get("error"), r
    assert entry.get("path"), r


def test_behavior_tree_asset(test_ns, mcp):
    r = mcp.call("get_asset_behavior_tree",
                 assetPath=f"{test_ns}/BT_TestAI")
    assert isinstance(r, dict)


def test_behavior_tree_blackboard(test_ns, mcp):
    r = mcp.call("get_asset_blackboard", assetPath=f"{test_ns}/BB_TestAI")
    assert isinstance(r, dict)


def test_anim_blueprint_create(test_ns, mcp, template_skeleton):
    path = f"{test_ns}/ABP_TestAnim"
    r = mcp.call("create_asset_anim_blueprint", assetPath=path,
                 skeletonPath=template_skeleton)
    assert r, f"create_asset_anim_blueprint returned empty: {r!r}"


def test_anim_blueprint_animgraph_sequence_player(test_ns, mcp, template_skeleton):
    """SM + SequencePlayer 往返（AnimGraph，不走 K2）。"""
    _ = template_skeleton
    path = f"{test_ns}/ABP_TestAnim"
    add_sm = mcp.call_capability(
        "manage_asset_anim_blueprint",
        assetPath=path,
        operations=[{"action": "add_state_machine", "stateMachineName": "Locomotion", "posX": 0, "posY": 0}],
    )
    sm_entry = cap_first(add_sm)
    assert not sm_entry.get("error"), add_sm

    add_node = mcp.call_capability(
        "manage_asset_anim_blueprint",
        assetPath=path,
        operations=[{
            "action": "add_node",
            "nodeClass": "SequencePlayer",
            "posX": 400,
            "posY": 0,
        }],
    )
    node_entry = cap_first(add_node)
    assert not node_entry.get("error"), add_node
    node_id = node_entry.get("nodeId")
    assert node_id, add_node

    graph = mcp.call_capability(
        "get_asset_anim_blueprint",
        assetPath=path,
        sections=["graph"],
    )
    g_entry = cap_first(graph)
    assert not g_entry.get("error"), graph
    nodes = g_entry.get("nodes") or []
    assert any(n.get("nodeId") == node_id for n in nodes if isinstance(n, dict)), g_entry


def test_anim_blueprint_animgraph_slot_and_blend(test_ns, mcp, template_skeleton):
    """Slot / Blend / LayeredBoneBlend / ApplyAdditive / CachedPose 可 spawn。"""
    _ = template_skeleton
    path = f"{test_ns}/ABP_TestAnim"
    classes = ["Slot", "Blend", "LayeredBoneBlend", "ApplyAdditive", "SaveCachedPose", "UseCachedPose"]
    for i, node_class in enumerate(classes):
        add = mcp.call_capability(
            "manage_asset_anim_blueprint",
            assetPath=path,
            operations=[{
                "action": "add_node",
                "nodeClass": node_class,
                "posX": 200,
                "posY": 80 * (i + 1),
            }],
        )
        entry = cap_first(add)
        assert not entry.get("error"), f"{node_class}: {add!r}"
        assert entry.get("nodeId"), add
        if node_class == "Slot":
            setr = mcp.call_capability(
                "manage_asset_anim_blueprint",
                assetPath=path,
                operations=[{
                    "action": "set_node",
                    "nodeId": entry["nodeId"],
                    "slotName": "DefaultSlot",
                }],
            )
            assert not cap_first(setr).get("error"), setr


def test_anim_blueprint_animgraph_ik_and_aimoffset(test_ns, mcp, template_skeleton):
    """TwoBoneIK / LookAt / ModifyBone / AimOffset 可 spawn；IK 可写 boneName。"""
    path = f"{test_ns}/ABP_TestAnim"
    created = mcp.call(
        "create_asset_anim_blueprint",
        assetPath=path,
        skeletonPath=template_skeleton,
    )
    create_entry = cap_first(created) if isinstance(created, dict) else {}
    if create_entry.get("error") and "already exists" not in str(create_entry.get("error")).lower() and "已存在" not in str(create_entry.get("error")):
        assert not create_entry.get("error"), created
    classes = ["TwoBoneIK", "LookAt", "ModifyBone", "AimOffset"]
    for i, node_class in enumerate(classes):
        add = mcp.call_capability(
            "manage_asset_anim_blueprint",
            assetPath=path,
            operations=[{
                "action": "add_node",
                "nodeClass": node_class,
                "posX": 480,
                "posY": 80 * (i + 1),
                "boneName": "pelvis",
            }],
        )
        entry = cap_first(add)
        assert not entry.get("error"), f"{node_class}: {add!r}"
        assert entry.get("nodeId"), add
        if node_class == "TwoBoneIK":
            setr = mcp.call_capability(
                "manage_asset_anim_blueprint",
                assetPath=path,
                operations=[{
                    "action": "set_node",
                    "nodeId": entry["nodeId"],
                    "boneName": "hand_r",
                }],
            )
            assert not cap_first(setr).get("error"), setr


def test_get_asset_anim_blueprint_graph_overview(test_ns, mcp, template_skeleton):
    """get_asset_anim_blueprint sections=graphOverview。"""
    _ = template_skeleton
    path = f"{test_ns}/ABP_TestAnim"
    r = mcp.call_capability(
        "get_asset_anim_blueprint",
        assetPath=path,
        sections=["graphOverview"],
    )
    entry = cap_first(r)
    assert not entry.get("error"), entry
    assert isinstance(entry.get("graphs"), list), f"expected graphs[]: {entry!r}"


def test_anim_montage_create(test_ns, mcp, template_skeleton):
    path = f"{test_ns}/AM_TestAttack"
    r = mcp.call("create_asset_anim_montage", assetPath=path,
                 skeletonPath=template_skeleton)
    assert r, f"create_asset_anim_montage returned empty: {r!r}"
    # 空白 Montage 时长为 0；补一段 Idle 才能 play_montage
    seq = first_asset_path(mcp, "AnimSequence", path_filter="/Game/Mannequin")
    assert seq, "无法定位 AnimSequence 样本以填充 Montage"
    add = mcp.call_capability(
        "manage_asset_anim_montage",
        assetPath=path,
        operations=[{
            "action": "add_segment",
            "animSequencePath": seq,
        }],
    )
    entry = cap_first(add)
    assert not entry.get("error"), entry
    mcp.call("save_asset", assetPath=path)


def test_get_asset_anim_montage(test_ns, mcp, template_skeleton):
    path = f"{test_ns}/AM_TestAttack"
    r = mcp.call_capability("get_asset_anim_montage", assetPath=path)
    entry = cap_first(r)
    assert not entry.get("error"), entry
    assert entry.get("duration", 0) > 0, entry


def test_get_actor_animation_error_path(mcp, require_tools):
    """覆盖 `get_runtime_actor_animation` —— 不存在的 Actor：`totalCount/results[].error`，
    而非 top-level `MCPError`。"""
    require_tools("get_runtime_actor_animation")
    r = mcp.call(
        "get_runtime_actor_animation",
        actorName="__NonExistentActor_Animation__",
        sections=["state"],
    )
    assert isinstance(r, dict), r
    entry = cap_first(r)
    assert entry.get("error"), f"expected per-result error: {entry!r}"


def test_save_all_anim_assets(test_ns, mcp):
    paths = [
        f"{test_ns}/BT_TestAI",
        f"{test_ns}/BB_TestAI",
        f"{test_ns}/BB_CreateBlackboardCap",
        f"{test_ns}/ABP_TestAnim",
        f"{test_ns}/AM_TestAttack",
    ]
    results = [mcp.call("save_asset", assetPath=path) for path in paths]
    # Some may be skipped if create_asset_anim_* was skipped; just assert shape.
    assert all("saved" in r or "results" in r for r in results), results


def test_search_asset_animmontage_shortcut(test_ns, mcp, template_skeleton):
    """`search_asset` assetType=AnimMontage 快捷类型。"""
    _ = template_skeleton
    r = mcp.call_capability(
        "search_asset",
        assetType="AnimMontage",
        pathFilter=test_ns,
        nameFilter="AM_",
        limit=20,
    )
    assets = cap_first(r).get("assets") or []
    assert assets, r


def test_search_asset_type_aliases(mcp, test_ns):
    """search_asset 归一化 Blueprints/Widgets 等常见别名。"""
    bp = mcp.call_capability(
        "search_asset",
        assetType="Blueprint",
        pathFilter=test_ns,
        limit=10,
    )
    bps = mcp.call_capability(
        "search_asset",
        assetType="Blueprints",
        pathFilter=test_ns,
        limit=10,
    )
    assert (bp.get("assets") or []) == (bps.get("assets") or []), (bp, bps)


def test_manage_behavior_tree_add_child(test_ns, mcp):
    """manage_asset_behavior_tree set_root + add_node 后 get_asset_behavior_tree 可读子节点。"""
    bt = f"{test_ns}/BT_TestAI"
    mcp.call_capability(
        "manage_asset_behavior_tree",
        assetPath=bt,
        operations=[{
            "action": "set_root",
            "nodeClass": "BTComposite_Selector",
        }],
    )
    mcp.call_capability(
        "manage_asset_behavior_tree",
        assetPath=bt,
        operations=[{
            "action": "add_node",
            "nodeClass": "BTTask_Wait",
            "parentPath": "",
        }],
    )
    r = mcp.call_capability("get_asset_behavior_tree", assetPath=bt)
    entry = cap_first(r)
    root = entry.get("rootNode") or {}
    children = root.get("children") or []
    assert children, f"expected child under root: {entry!r}"

    # ── 新断言：flatIndex 先序连续 ──────────────────────────────
    # 根节点 flatIndex=0
    assert root.get("flatIndex") == 0, f"root flatIndex expected 0: {root!r}"
    # 第一个子节点 flatIndex=1（先序 DFS：父节点分配后立即递归子节点）
    assert children[0].get("flatIndex") == 1, f"child[0] flatIndex expected 1: {children[0]!r}"


def test_manage_behavior_tree_move_node(test_ns, mcp):
    """move_node 将子节点移到指定 childIndex。"""
    bt = f"{test_ns}/BT_MoveNode"
    mcp.call("create_asset_behavior_tree", assetPath=bt)
    mcp.call_capability(
        "manage_asset_behavior_tree",
        assetPath=bt,
        operations=[{
            "action": "set_root",
            "nodeClass": "BTComposite_Selector",
        }],
    )
    for _ in range(2):
        mcp.call_capability(
            "manage_asset_behavior_tree",
            assetPath=bt,
            operations=[{
                "action": "add_node",
                "nodeClass": "BTTask_Wait",
                "parentPath": "",
            }],
        )
    move = mcp.call_capability(
        "manage_asset_behavior_tree",
        assetPath=bt,
        operations=[{
            "action": "move_node",
            "targetPath": "1",
            "parentPath": "",
            "childIndex": 0,
        }],
    )
    move_entry = cap_first(move)
    assert not move_entry.get("error"), move_entry
    assert move_entry.get("movedPath") == "0", move_entry

    r = mcp.call_capability("get_asset_behavior_tree", assetPath=bt)
    entry = cap_first(r)
    root = entry.get("rootNode") or {}
    children = root.get("children") or []
    assert len(children) >= 2, entry
    assert (children[0].get("path") or children[0].get("childIndex")) in (0, "0", 0.0), (
        f"expected moved node at index 0: {children[0]!r}"
    )

    # flatIndex 兄弟节点连续性：root=0，child[0]=1，child[1]=2（先序 DFS 无跳号）
    assert root.get("flatIndex") == 0, f"root flatIndex expected 0: {root!r}"
    fi0 = children[0].get("flatIndex")
    fi1 = children[1].get("flatIndex")
    assert fi0 is not None and fi1 is not None, f"siblings missing flatIndex: {children!r}"
    assert fi1 == fi0 + 1, f"sibling flatIndex not consecutive: {fi0}, {fi1}"


def test_manage_asset_blackboard_enum_key(test_ns, mcp):
    """manage_asset_blackboard 支持 keyType=enum。"""
    bb = f"{test_ns}/BB_EnumKey"
    mcp.call("create_asset_blackboard", assetPath=bb)
    add = mcp.call_capability(
        "manage_asset_blackboard",
        assetPath=bb,
        operations=[{"action": "add", "keyName": "TestEnumKey", "keyType": "enum"}],
    )
    add_entry = cap_first(add)
    assert not add_entry.get("error"), add_entry

    r = mcp.call_capability("get_asset_blackboard", assetPath=bb, nameFilter="TestEnum")
    entry = cap_first(r)
    keys = entry.get("keys") or []
    assert keys, entry
    enum_keys = [k for k in keys if (k.get("name") or "") == "TestEnumKey"]
    assert enum_keys, f"enum key not found: {keys!r}"
    assert enum_keys[0].get("type") == "Enum", enum_keys[0]


# ─────────────────────────────────────────────────────────────
# interact_runtime_actor_animation
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def _anim_actor(mcp, pie, test_ns):
    """找一个带 SkeletalMeshComponent 的 Actor（或跳过）。"""
    try:
        r = mcp.call("list_runtime_actors", limit=50)
    except MCPError as e:
        pytest.skip(f"list_runtime_actors 失败：{e}")

    actors = r.get("actors") or []
    for a in actors:
        if isinstance(a, dict):
            cls = a.get("class", "")
            if "Character" in cls or "Pawn" in cls:
                return a.get("name") or a.get("actorName")
    pytest.skip("PIE 世界中无 Character/Pawn Actor，跳过 interact_runtime_actor_animation 测试")


@pytest.mark.l4_runtime
def test_interact_runtime_actor_animation_play_montage(mcp, _anim_actor, test_ns, require_tools):
    """`interact_runtime_actor_animation` action=play_montage。"""
    require_tools("interact_runtime_actor_animation")
    montage = f"{test_ns}/AM_TestAttack"
    r = mcp.call_capability(
        "interact_runtime_actor_animation",
        action="play_montage",
        actorName=_anim_actor,
        montagePath=montage,
        playRate=1.0,
    )
    entry = cap_first(r)
    assert not entry.get("error"), entry
    assert entry.get("playing") is True, entry


@pytest.mark.l4_runtime
def test_interact_runtime_actor_animation_stop_montage(mcp, _anim_actor, test_ns, require_tools):
    """`interact_runtime_actor_animation` action=stop_montage。"""
    require_tools("interact_runtime_actor_animation")
    montage = f"{test_ns}/AM_TestAttack"
    play = mcp.call_capability(
        "interact_runtime_actor_animation",
        action="play_montage",
        actorName=_anim_actor,
        montagePath=montage,
    )
    assert not cap_first(play).get("error"), play
    stop = mcp.call_capability(
        "interact_runtime_actor_animation",
        action="stop_montage",
        actorName=_anim_actor,
        montagePath=montage,
    )
    entry = cap_first(stop)
    assert not entry.get("error"), entry
    assert entry.get("stopped") is True, entry
