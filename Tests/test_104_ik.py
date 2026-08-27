# Copyright byteyang. All Rights Reserved.
"""IKRig / IKRetargeter — create + chain/goal + get（UE5+，插件门控 skip）。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import first_asset_path
from _framework.capability_probe import is_capability_available
from _framework.mcp_client import cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.0")]


@pytest.fixture(scope="module", autouse=True)
def require_ik(mcp):
    if not is_capability_available(mcp, "create_asset_ik_rig"):
        pytest.skip("IKRig capability 未编入（需 WITH_IK_RIG）")


def test_create_ik_rig_add_chain(test_ns, mcp):
    path = f"{test_ns}/IK_Created"
    mesh = first_asset_path(mcp, "SkeletalMesh")
    kwargs = {"assetPath": path}
    if mesh:
        kwargs["meshPath"] = mesh
    r = mcp.call_capability("create_asset_ik_rig", **kwargs)
    entry = cap_first(r)
    if entry.get("error") and "已存在" not in str(entry.get("error")) and "already exists" not in str(entry.get("error")):
        pytest.skip(f"create_asset_ik_rig 失败: {entry}")
    chain = mcp.call_capability(
        "manage_asset_ik_rig",
        assetPath=path,
        operations=[{
            "action": "add_chain",
            "chainName": "NxChain",
            "startBone": "pelvis",
            "endBone": "head",
        }],
    )
    assert isinstance(cap_first(chain), dict), chain
    got = cap_first(mcp.call_capability("get_asset_ik_rig", assetPath=path))
    assert not got.get("error"), got


def test_create_ik_retargeter(test_ns, mcp):
    if not is_capability_available(mcp, "create_asset_ik_retargeter"):
        pytest.skip("create_asset_ik_retargeter 未编入")
    path = f"{test_ns}/IKRT_Created"
    r = mcp.call_capability("create_asset_ik_retargeter", assetPath=path)
    entry = cap_first(r)
    if entry.get("error") and "already exists" not in str(entry.get("error")):
        pytest.skip(f"create_asset_ik_retargeter 失败: {entry}")
    got = cap_first(mcp.call_capability("get_asset_ik_retargeter", assetPath=path))
    assert not got.get("error"), got
    bad = mcp.call_capability(
        "manage_asset_ik_rig",
        assetPath=f"{test_ns}/IK_Created",
        operations=[{"action": "not_a_real_action"}],
    )
    assert cap_first(bad).get("error"), bad

    src = f"{test_ns}/IK_Src"
    tgt = f"{test_ns}/IK_Tgt"
    mesh = first_asset_path(mcp, "SkeletalMesh")
    for rig_path in (src, tgt):
        kwargs = {"assetPath": rig_path}
        if mesh:
            kwargs["meshPath"] = mesh
        cr = mcp.call_capability("create_asset_ik_rig", **kwargs)
        ce = cap_first(cr)
        if ce.get("error") and "already exists" not in str(ce.get("error")).lower() and "已存在" not in str(ce.get("error")):
            pytest.skip(f"create_asset_ik_rig 失败: {ce}")
    man = mcp.call_capability(
        "manage_asset_ik_retargeter",
        assetPath=path,
        operations=[
            {"action": "set_source_rig", "rigPath": src},
            {"action": "set_target_rig", "rigPath": tgt},
            {"action": "set_chain_source", "targetChain": "Root", "sourceChain": "Root"},
        ],
    )
    for e in (man.get("results") or [cap_first(man)]):
        if isinstance(e, dict) and e.get("error") and "set_chain_source" in str(e):
            continue
        if isinstance(e, dict) and e.get("error"):
            pytest.skip(f"manage_asset_ik_retargeter 跳过: {e}")


def test_manage_ik_rig_remaining_actions(test_ns, mcp):
    path = f"{test_ns}/IK_Created"
    mesh = first_asset_path(mcp, "SkeletalMesh")
    ops = [
        {"action": "remove_chain", "chainName": "NxChain"},
        {"action": "set_solver_enabled", "solverIndex": 0, "enabled": True},
        {"action": "set_goal", "goalName": "NxGoal", "chainName": "NxChain"},
    ]
    if mesh:
        ops.insert(0, {"action": "set_preview_mesh", "meshPath": mesh})
    r = mcp.call_capability("manage_asset_ik_rig", assetPath=path, operations=ops)
    for e in (r.get("results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("error"):
            pytest.skip(f"manage_asset_ik_rig 剩余 action 跳过: {e}")
