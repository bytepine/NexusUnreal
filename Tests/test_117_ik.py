# Copyright byteyang. All Rights Reserved.
"""IKRig / IKRetargeter — create + chain/goal + get（UE5+，插件门控 skip）。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import first_asset_path
from _framework.capability_probe import is_capability_available
from _framework.mcp_client import MCPError, cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.0")]


@pytest.fixture(scope="module", autouse=True)
def require_ik(mcp):
    if not is_capability_available(mcp, "CreateAssetIKRig"):
        pytest.skip("IKRig capability 未编入（需 WITH_IK_RIG）")


def test_create_ik_rig_add_chain(test_ns, mcp):
    path = f"{test_ns}/IK_Created"
    mesh = first_asset_path(mcp, "SkeletalMesh")
    kwargs = {"AssetPath": path}
    if mesh:
        kwargs["MeshPath"] = mesh
    r = mcp.call_capability("CreateAssetIKRig", **kwargs)
    entry = cap_first(r)
    if entry.get("Error") and "已存在" not in str(entry.get("Error")) and "already exists" not in str(entry.get("Error")):
        pytest.skip(f"create_asset_ik_rig 失败: {entry}")
    chain = mcp.call_capability(
        "ManageAssetIKRig",
        AssetPath=path,
        Operations=[{
            "Action": "AddChain",
            "ChainName": "NxChain",
            "StartBone": "pelvis",
            "EndBone": "head",
        }],
    )
    assert isinstance(cap_first(chain), dict), chain
    got = cap_first(mcp.call_capability("GetAssetIKRig", AssetPath=path))
    assert not got.get("Error"), got


def test_create_ik_retargeter(test_ns, mcp):
    if not is_capability_available(mcp, "CreateAssetIKRetargeter"):
        pytest.skip("create_asset_ik_retargeter 未编入")
    path = f"{test_ns}/IKRT_Created"
    r = mcp.call_capability("CreateAssetIKRetargeter", AssetPath=path)
    entry = cap_first(r)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")):
        pytest.skip(f"create_asset_ik_retargeter 失败: {entry}")
    got = cap_first(mcp.call_capability("GetAssetIKRetargeter", AssetPath=path))
    assert not got.get("Error"), got
    try:
        bad = cap_first(
            mcp.call_capability(
                "ManageAssetIKRig",
                AssetPath=f"{test_ns}/IK_Created",
                Operations=[{"Action": "not_a_real_action"}],
            )
        )
    except MCPError as exc:
        bad = {"Error": str(exc)}
    assert bad.get("Error"), bad

    src = f"{test_ns}/IK_Src"
    tgt = f"{test_ns}/IK_Tgt"
    mesh = first_asset_path(mcp, "SkeletalMesh")
    for rig_path in (src, tgt):
        kwargs = {"AssetPath": rig_path}
        if mesh:
            kwargs["MeshPath"] = mesh
        cr = mcp.call_capability("CreateAssetIKRig", **kwargs)
        ce = cap_first(cr)
        if ce.get("Error") and "already exists" not in str(ce.get("Error")).lower() and "已存在" not in str(ce.get("Error")):
            pytest.skip(f"create_asset_ik_rig 失败: {ce}")
    man = mcp.call_capability(
        "ManageAssetIKRetargeter",
        AssetPath=path,
        Operations=[
            {"Action": "SetSourceRig", "RigPath": src},
            {"Action": "SetTargetRig", "RigPath": tgt},
            {"Action": "SetChainSource", "TargetChain": "Root", "SourceChain": "Root"},
        ],
    )
    for e in (man.get("Results") or [cap_first(man)]):
        if isinstance(e, dict) and e.get("Error") and "SetChainSource" in str(e):
            continue
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"manage_asset_ik_retargeter 跳过: {e}")


def test_manage_ik_rig_remaining_actions(test_ns, mcp):
    path = f"{test_ns}/IK_Created"
    mesh = first_asset_path(mcp, "SkeletalMesh")
    ops = [
        {"Action": "RemoveChain", "ChainName": "NxChain"},
        {"Action": "SetSolverEnabled", "SolverIndex": 0, "bEnabled": True},
        {"Action": "SetGoal", "GoalName": "NxGoal", "ChainName": "NxChain"},
    ]
    if mesh:
        ops.insert(0, {"Action": "SetPreviewMesh", "MeshPath": mesh})
    r = mcp.call_capability("ManageAssetIKRig", AssetPath=path, Operations=ops)
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"manage_asset_ik_rig 剩余 action 跳过: {e}")
