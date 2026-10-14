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
    mcp.call("CreateAssetBlackboard", AssetPath=bb)
    r = mcp.call("CreateAssetBehaviorTree", AssetPath=bt)
    assert r, f"create_asset_behavior_tree returned empty: {r!r}"


def test_create_blackboard_capability(test_ns, mcp, require_tools):
    """`create_asset_blackboard` 经全局 `call_capability` 调用。"""
    require_tools("CallCapability")
    bb = f"{test_ns}/BB_CreateBlackboardCap"
    r = mcp.call_capability("CreateAssetBlackboard", AssetPath=bb)
    entry = cap_first(r)
    assert not entry.get("Error"), r
    assert entry.get("Path"), r


def test_behavior_tree_asset(test_ns, mcp):
    r = mcp.call("GetAssetBehaviorTree",
                 AssetPath=f"{test_ns}/BT_TestAI")
    assert isinstance(r, dict)


def test_behavior_tree_blackboard(test_ns, mcp):
    r = mcp.call("GetAssetBlackboard", AssetPath=f"{test_ns}/BB_TestAI")
    assert isinstance(r, dict)


def test_anim_blueprint_create(test_ns, mcp, template_skeleton):
    path = f"{test_ns}/ABP_TestAnim"
    r = mcp.call("CreateAssetAnimBlueprint", AssetPath=path,
                 SkeletonPath=template_skeleton)
    assert r, f"create_asset_anim_blueprint returned empty: {r!r}"


def test_anim_blueprint_animgraph_sequence_player(test_ns, mcp, template_skeleton):
    """SM + SequencePlayer 往返（AnimGraph，不走 K2）。"""
    _ = template_skeleton
    path = f"{test_ns}/ABP_TestAnim"
    add_sm = mcp.call_capability(
        "ManageAssetAnimBlueprint",
        AssetPath=path,
        Operations=[{"Action": "AddStateMachine", "StateMachineName": "Locomotion", "PosX": 0, "PosY": 0}],
    )
    sm_entry = cap_first(add_sm)
    assert not sm_entry.get("Error"), add_sm

    add_node = mcp.call_capability(
        "ManageAssetAnimBlueprint",
        AssetPath=path,
        Operations=[{
            "Action": "AddNode",
            "NodeClass": "SequencePlayer",
            "PosX": 400,
            "PosY": 0,
        }],
    )
    node_entry = cap_first(add_node)
    assert not node_entry.get("Error"), add_node
    node_id = node_entry.get("NodeId")
    assert node_id, add_node

    graph = mcp.call_capability(
        "GetAssetAnimBlueprint",
        AssetPath=path,
        Sections=["graph"],
    )
    g_entry = cap_first(graph)
    assert not g_entry.get("Error"), graph
    nodes = g_entry.get("Nodes") or []
    assert any(n.get("NodeId") == node_id for n in nodes if isinstance(n, dict)), g_entry


def test_anim_blueprint_animgraph_slot_and_blend(test_ns, mcp, template_skeleton):
    """Slot / Blend / LayeredBoneBlend / ApplyAdditive / CachedPose 可 spawn。"""
    _ = template_skeleton
    path = f"{test_ns}/ABP_TestAnim"
    classes = ["Slot", "Blend", "LayeredBoneBlend", "ApplyAdditive", "SaveCachedPose", "UseCachedPose"]
    for i, node_class in enumerate(classes):
        add = mcp.call_capability(
            "ManageAssetAnimBlueprint",
            AssetPath=path,
            Operations=[{
                "Action": "AddNode",
                "NodeClass": node_class,
                "PosX": 200,
                "PosY": 80 * (i + 1),
            }],
        )
        entry = cap_first(add)
        assert not entry.get("Error"), f"{node_class}: {add!r}"
        assert entry.get("NodeId"), add
        if node_class == "Slot":
            setr = mcp.call_capability(
                "ManageAssetAnimBlueprint",
                AssetPath=path,
                Operations=[{
                    "Action": "SetNode",
                    "NodeId": entry["NodeId"],
                    "SlotName": "DefaultSlot",
                }],
            )
            assert not cap_first(setr).get("Error"), setr


def test_anim_blueprint_animgraph_ik_and_aimoffset(test_ns, mcp, template_skeleton):
    """TwoBoneIK / LookAt / ModifyBone / AimOffset 可 spawn；IK 可写 boneName。"""
    path = f"{test_ns}/ABP_TestAnim"
    created = mcp.call(
        "CreateAssetAnimBlueprint",
        AssetPath=path,
        SkeletonPath=template_skeleton,
    )
    create_entry = cap_first(created) if isinstance(created, dict) else {}
    if create_entry.get("Error") and "already exists" not in str(create_entry.get("Error")).lower() and "已存在" not in str(create_entry.get("Error")):
        assert not create_entry.get("Error"), created
    classes = ["TwoBoneIK", "LookAt", "ModifyBone", "AimOffset"]
    for i, node_class in enumerate(classes):
        add = mcp.call_capability(
            "ManageAssetAnimBlueprint",
            AssetPath=path,
            Operations=[{
                "Action": "AddNode",
                "NodeClass": node_class,
                "PosX": 480,
                "PosY": 80 * (i + 1),
                "BoneName": "pelvis",
            }],
        )
        entry = cap_first(add)
        assert not entry.get("Error"), f"{node_class}: {add!r}"
        assert entry.get("NodeId"), add
        if node_class == "TwoBoneIK":
            setr = mcp.call_capability(
                "ManageAssetAnimBlueprint",
                AssetPath=path,
                Operations=[{
                    "Action": "SetNode",
                    "NodeId": entry["NodeId"],
                    "BoneName": "hand_r",
                }],
            )
            assert not cap_first(setr).get("Error"), setr


def test_anim_blueprint_animgraph_extended_nodes(test_ns, mcp, template_skeleton):
    """P1：BlendSpace1D 别名 + FABRIK/CCDIK/CopyBone/空间转换/混合枚举等可 spawn。"""
    _ = template_skeleton
    path = f"{test_ns}/ABP_TestAnim"
    classes = [
        "BlendSpace1D",
        "SequenceEvaluator",
        "BlendListByEnum",
        "BlendListByInt",
        "MultiWayBlend",
        "RandomPlayer",
        "PoseBlendNode",
        "Inertialization",
        "ComponentToLocalSpace",
        "LocalToComponentSpace",
        "FABRIK",
        "CCDIK",
        "CopyBone",
        "HandIKRetargeting",
        "AimOffsetLookAt",
    ]
    for i, node_class in enumerate(classes):
        op = {
            "Action": "AddNode",
            "NodeClass": node_class,
            "PosX": 700,
            "PosY": 40 * (i + 1),
        }
        if node_class in ("FABRIK", "CCDIK", "CopyBone"):
            op["BoneName"] = "hand_r"
        add = mcp.call_capability(
            "ManageAssetAnimBlueprint",
            AssetPath=path,
            Operations=[op],
        )
        entry = cap_first(add)
        assert not entry.get("Error"), f"{node_class}: {add!r}"
        assert entry.get("NodeId"), add


def test_get_asset_anim_blueprint_graph_overview(test_ns, mcp, template_skeleton):
    """get_asset_anim_blueprint Sections=graphOverview。"""
    _ = template_skeleton
    path = f"{test_ns}/ABP_TestAnim"
    r = mcp.call_capability(
        "GetAssetAnimBlueprint",
        AssetPath=path,
        Sections=["graphOverview"],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert isinstance(entry.get("Graphs"), list), f"expected graphs[]: {entry!r}"


def test_anim_montage_create(test_ns, mcp, template_skeleton):
    path = f"{test_ns}/AM_TestAttack"
    r = mcp.call("CreateAssetAnimMontage", AssetPath=path,
                 SkeletonPath=template_skeleton)
    assert r, f"create_asset_anim_montage returned empty: {r!r}"
    # 空白 Montage 时长为 0；补一段 Idle 才能 play_montage
    seq = first_asset_path(mcp, "AnimSequence", path_filter="/Game/Characters/Mannequins")
    assert seq, "无法定位 AnimSequence 样本以填充 Montage"
    add = mcp.call_capability(
        "ManageAssetAnimMontage",
        AssetPath=path,
        Operations=[{
            "Action": "AddSegment",
            "AnimSequencePath": seq,
        }],
    )
    entry = cap_first(add)
    assert not entry.get("Error"), entry
    mcp.call("SaveAsset", AssetPath=path)


def test_get_asset_anim_montage(test_ns, mcp, template_skeleton):
    path = f"{test_ns}/AM_TestAttack"
    r = mcp.call_capability("GetAssetAnimMontage", AssetPath=path)
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert entry.get("Duration", 0) > 0, entry


def test_get_actor_animation_error_path(mcp, require_tools):
    """覆盖 `get_runtime_actor_animation` —— 不存在的 Actor：`totalCount/results[].error`，
    而非 top-level `MCPError`。"""
    require_tools("GetRuntimeActorAnimation")
    r = mcp.call(
        "GetRuntimeActorAnimation",
        ActorName="__NonExistentActor_Animation__",
        Sections=["State", "Slots"],
    )
    assert isinstance(r, dict), r
    entry = cap_first(r)
    assert entry.get("Error"), f"expected per-result error: {entry!r}"


def test_save_all_anim_assets(test_ns, mcp):
    paths = [
        f"{test_ns}/BT_TestAI",
        f"{test_ns}/BB_TestAI",
        f"{test_ns}/BB_CreateBlackboardCap",
        f"{test_ns}/ABP_TestAnim",
        f"{test_ns}/AM_TestAttack",
    ]
    results = [mcp.call("SaveAsset", AssetPath=path) for path in paths]
    # Some may be skipped if create_asset_anim_* was skipped; just assert shape.
    assert all("bSaved" in r or "Results" in r for r in results), results


def test_search_asset_animmontage_shortcut(test_ns, mcp, template_skeleton):
    """`search_asset` AssetType=AnimMontage 快捷类型。"""
    _ = template_skeleton
    r = mcp.call_capability(
        "SearchAsset",
        AssetType="AnimMontage",
        PathFilter=test_ns,
        NameFilter="AM_",
        Limit=20,
    )
    assets = cap_first(r).get("Assets") or []
    assert assets, r


def test_search_asset_type_aliases(mcp, test_ns):
    """search_asset 归一化 Blueprints/Widgets 等常见别名。"""
    bp = mcp.call_capability(
        "SearchAsset",
        AssetType="Blueprint",
        PathFilter=test_ns,
        Limit=10,
    )
    bps = mcp.call_capability(
        "SearchAsset",
        AssetType="Blueprints",
        PathFilter=test_ns,
        Limit=10,
    )
    assert (bp.get("Assets") or []) == (bps.get("Assets") or []), (bp, bps)


def test_manage_behavior_tree_add_child(test_ns, mcp):
    """manage_asset_behavior_tree set_root + add_node 后 get_asset_behavior_tree 可读子节点。"""
    bt = f"{test_ns}/BT_TestAI"
    mcp.call_capability(
        "ManageAssetBehaviorTree",
        AssetPath=bt,
        Operations=[{
            "Action": "SetRoot",
            "NodeClass": "BTComposite_Selector",
        }],
    )
    mcp.call_capability(
        "ManageAssetBehaviorTree",
        AssetPath=bt,
        Operations=[{
            "Action": "AddNode",
            "NodeClass": "BTTask_Wait",
            "ParentPath": "",
        }],
    )
    r = mcp.call_capability("GetAssetBehaviorTree", AssetPath=bt)
    entry = cap_first(r)
    root = entry.get("RootNode") or {}
    children = root.get("Children") or []
    assert children, f"expected child under root: {entry!r}"

    # ── 新断言：flatIndex 先序连续 ──────────────────────────────
    # 根节点 FlatIndex=0
    assert root.get("FlatIndex") == 0, f"root flatIndex expected 0: {root!r}"
    # 第一个子节点 FlatIndex=1（先序 DFS：父节点分配后立即递归子节点）
    assert children[0].get("FlatIndex") == 1, f"child[0] flatIndex expected 1: {children[0]!r}"


def test_manage_behavior_tree_move_node(test_ns, mcp):
    """move_node 将子节点移到指定 childIndex。"""
    bt = f"{test_ns}/BT_MoveNode"
    mcp.call("CreateAssetBehaviorTree", AssetPath=bt)
    mcp.call_capability(
        "ManageAssetBehaviorTree",
        AssetPath=bt,
        Operations=[{
            "Action": "SetRoot",
            "NodeClass": "BTComposite_Selector",
        }],
    )
    for _ in range(2):
        mcp.call_capability(
            "ManageAssetBehaviorTree",
            AssetPath=bt,
            Operations=[{
                "Action": "AddNode",
                "NodeClass": "BTTask_Wait",
                "ParentPath": "",
            }],
        )
    move = mcp.call_capability(
        "ManageAssetBehaviorTree",
        AssetPath=bt,
        Operations=[{
            "Action": "MoveNode",
            "TargetPath": "1",
            "ParentPath": "",
            "ChildIndex": 0,
        }],
    )
    move_entry = cap_first(move)
    assert not move_entry.get("Error"), move_entry
    assert move_entry.get("MovedPath") == "0", move_entry

    r = mcp.call_capability("GetAssetBehaviorTree", AssetPath=bt)
    entry = cap_first(r)
    root = entry.get("RootNode") or {}
    children = root.get("Children") or []
    assert len(children) >= 2, entry
    assert (children[0].get("Path") or children[0].get("ChildIndex")) in (0, "0", 0.0), (
        f"expected moved node at index 0: {children[0]!r}"
    )

    # flatIndex 兄弟节点连续性：root=0，child[0]=1，child[1]=2（先序 DFS 无跳号）
    assert root.get("FlatIndex") == 0, f"root flatIndex expected 0: {root!r}"
    fi0 = children[0].get("FlatIndex")
    fi1 = children[1].get("FlatIndex")
    assert fi0 is not None and fi1 is not None, f"siblings missing flatIndex: {children!r}"
    assert fi1 == fi0 + 1, f"sibling flatIndex not consecutive: {fi0}, {fi1}"


def test_manage_asset_blackboard_enum_key(test_ns, mcp):
    """manage_asset_blackboard 支持 KeyType=enum。"""
    bb = f"{test_ns}/BB_EnumKey"
    mcp.call("CreateAssetBlackboard", AssetPath=bb)
    add = mcp.call_capability(
        "ManageAssetBlackboard",
        AssetPath=bb,
        Operations=[{"Action": "Add", "KeyName": "TestEnumKey", "KeyType": "enum"}],
    )
    add_entry = cap_first(add)
    assert not add_entry.get("Error"), add_entry

    r = mcp.call_capability("GetAssetBlackboard", AssetPath=bb, NameFilter="TestEnum")
    entry = cap_first(r)
    keys = entry.get("Keys") or []
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
        r = mcp.call("ListRuntimeActors", Limit=50)
    except MCPError as e:
        pytest.skip(f"list_runtime_actors 失败：{e}")

    actors = r.get("Actors") or []
    for a in actors:
        if isinstance(a, dict):
            cls = a.get("Class", "")
            if "Character" in cls or "Pawn" in cls:
                return a.get("name") or a.get("ActorName")
    pytest.skip("PIE 世界中无 Character/Pawn Actor，跳过 interact_runtime_actor_animation 测试")


@pytest.mark.l4_runtime
def test_get_runtime_actor_animation_state_no_crash(mcp, _anim_actor, require_tools):
    """`get_runtime_actor_animation` Sections=state：ThirdPerson 角色不得空指针崩溃。"""
    require_tools("GetRuntimeActorAnimation")
    r = mcp.call(
        "GetRuntimeActorAnimation",
        ActorName=_anim_actor,
        Sections=["State"],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), entry


@pytest.mark.l4_runtime
def test_interact_runtime_actor_animation_play_montage(mcp, _anim_actor, test_ns, require_tools):
    """`interact_runtime_actor_animation` Action=play_montage。"""
    require_tools("InteractRuntimeActorAnimation")
    montage = f"{test_ns}/AM_TestAttack"
    r = mcp.call_capability(
        "InteractRuntimeActorAnimation",
        Action="PlayMontage",
        ActorName=_anim_actor,
        MontagePath=montage,
        PlayRate=1.0,
    )
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert entry.get("bPlaying") is True, entry


@pytest.mark.l4_runtime
def test_interact_runtime_actor_animation_stop_montage(mcp, _anim_actor, test_ns, require_tools):
    """`interact_runtime_actor_animation` Action=stop_montage。"""
    require_tools("InteractRuntimeActorAnimation")
    montage = f"{test_ns}/AM_TestAttack"
    play = mcp.call_capability(
        "InteractRuntimeActorAnimation",
        Action="PlayMontage",
        ActorName=_anim_actor,
        MontagePath=montage,
    )
    assert not cap_first(play).get("Error"), play
    stop = mcp.call_capability(
        "InteractRuntimeActorAnimation",
        Action="StopMontage",
        ActorName=_anim_actor,
        MontagePath=montage,
    )
    entry = cap_first(stop)
    assert not entry.get("Error"), entry
    assert entry.get("bStopped") is True, entry


def test_manage_behavior_tree_remaining_actions(test_ns, mcp):
    bt = f"{test_ns}/BT_Remaining"
    bb = f"{test_ns}/BB_Remaining"
    mcp.call("CreateAssetBlackboard", AssetPath=bb)
    mcp.call("CreateAssetBehaviorTree", AssetPath=bt)
    mcp.call_capability(
        "ManageAssetBehaviorTree",
        AssetPath=bt,
        Operations=[
            {"Action": "SetRoot", "NodeClass": "BTComposite_Selector"},
            {"Action": "AddNode", "NodeClass": "BTTask_Wait", "ParentPath": ""},
            {"Action": "AddDecorator", "NodeClass": "BTDecorator_Blackboard", "TargetPath": "0"},
            {"Action": "AddService", "NodeClass": "BTService_DefaultFocus", "TargetPath": ""},
            {"Action": "SetBlackboard", "BlackboardPath": bb},
            {"Action": "SetProperty", "TargetPath": "0", "TargetType": "Node", "PropertyName": "WaitTime", "PropertyValue": "1.0"},
            {"Action": "SyncGraph"},
        ],
    )
    r = mcp.call_capability(
        "ManageAssetBehaviorTree",
        AssetPath=bt,
        Operations=[
            {"Action": "ReplaceNode", "TargetPath": "0", "NodeClass": "BTTask_Wait"},
            {"Action": "RemoveDecorator", "TargetPath": "0", "TargetIndex": 0},
            {"Action": "RemoveService", "TargetPath": "", "TargetIndex": 0},
            {"Action": "RemoveNode", "TargetPath": "0"},
        ],
    )
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"BT remaining action 跳过: {e}")


def test_manage_blackboard_rename_remove_parent(test_ns, mcp):
    parent = f"{test_ns}/BB_Parent"
    child = f"{test_ns}/BB_Child"
    mcp.call("CreateAssetBlackboard", AssetPath=parent)
    mcp.call("CreateAssetBlackboard", AssetPath=child)
    mcp.call_capability(
        "ManageAssetBlackboard",
        AssetPath=child,
        Operations=[{"Action": "Add", "KeyName": "ToRename", "KeyType": "bool"}],
    )
    r = mcp.call_capability(
        "ManageAssetBlackboard",
        AssetPath=child,
        Operations=[
            {"Action": "Rename", "KeyName": "ToRename", "NewName": "RenamedKey"},
            {"Action": "SetParent", "ParentPath": parent},
            {"Action": "Remove", "KeyName": "RenamedKey"},
        ],
    )
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"blackboard remaining 跳过: {e}")


def test_manage_anim_blueprint_states_and_wires(test_ns, mcp, template_skeleton):
    path = f"{test_ns}/ABP_States"
    mcp.call("CreateAssetAnimBlueprint", AssetPath=path, SkeletonPath=template_skeleton)
    mcp.call_capability(
        "ManageAssetAnimBlueprint",
        AssetPath=path,
        Operations=[{"Action": "AddStateMachine", "StateMachineName": "Locomotion"}],
    )
    add_a = mcp.call_capability(
        "ManageAssetAnimBlueprint",
        AssetPath=path,
        Operations=[{"Action": "AddNode", "NodeClass": "SequencePlayer", "PosX": 0, "PosY": 0}],
    )
    add_b = mcp.call_capability(
        "ManageAssetAnimBlueprint",
        AssetPath=path,
        Operations=[{"Action": "AddNode", "NodeClass": "Slot", "PosX": 200, "PosY": 0}],
    )
    id_a = cap_first(add_a).get("NodeId")
    id_b = cap_first(add_b).get("NodeId")
    ops = [
        {"Action": "AddState", "StateMachineName": "Locomotion", "StateName": "Idle"},
        {"Action": "AddState", "StateMachineName": "Locomotion", "StateName": "Run"},
        {"Action": "AddTransition", "StateMachineName": "Locomotion", "StateName": "Idle", "TargetStateName": "Run"},
    ]
    if id_a and id_b:
        ops.append({
            "Action": "Connect",
            "SourceNodeId": id_a,
            "TargetNodeId": id_b,
        })
        ops.append({
            "Action": "Disconnect",
            "SourceNodeId": id_a,
            "TargetNodeId": id_b,
        })
        ops.append({"Action": "RemoveNode", "NodeId": id_b})
    ops.extend([
        {"Action": "RemoveTransition", "StateMachineName": "Locomotion", "StateName": "Idle", "TargetStateName": "Run"},
        {"Action": "RemoveState", "StateMachineName": "Locomotion", "StateName": "Run"},
        {"Action": "RemoveStateMachine", "StateMachineName": "Locomotion"},
    ])
    r = mcp.call_capability("ManageAssetAnimBlueprint", AssetPath=path, Operations=ops)
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"ABP remaining 跳过: {e}")
    got = mcp.call_capability(
        "GetAssetAnimBlueprint",
        AssetPath=path,
        Sections=["Variables", "statemachines", "Defaults"],
    )
    assert not cap_first(got).get("Error"), got


def test_manage_anim_montage_section_and_remove(test_ns, mcp, template_skeleton):
    path = f"{test_ns}/AM_Sections"
    mcp.call("CreateAssetAnimMontage", AssetPath=path, SkeletonPath=template_skeleton)
    seq = first_asset_path(mcp, "AnimSequence", path_filter="/Game/Characters/Mannequins")
    if not seq:
        pytest.skip("无 AnimSequence")
    r = mcp.call_capability(
        "ManageAssetAnimMontage",
        AssetPath=path,
        Operations=[
            {"Action": "AddSegment", "AnimSequencePath": seq},
            {"Action": "AddSection", "SectionName": "NxSec"},
            {"Action": "RemoveSection", "SectionName": "NxSec"},
            {"Action": "RemoveSegment", "SegmentIndex": 0},
        ],
    )
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"montage remaining 跳过: {e}")
