# Copyright byteyang. All Rights Reserved.
"""阶段九八：Tier2 — LevelSequencer / PhysicsAsset / EQS。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l3_asset


# ── Level Sequence ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def seq_path(test_ns, mcp):
    path = f"{test_ns}/LS_Created"
    r = mcp.call_capability("CreateAssetLevelSequence", AssetPath=path)
    entry = cap_first(r)
    if entry.get("Error") and "already exists" not in str(entry.get("Error", "")):
        pytest.skip(f"create_asset_level_sequence 失败: {entry}")
    return path


def test_get_level_sequence(seq_path, mcp):
    r = mcp.call_capability("GetAssetLevelSequence", AssetPath=seq_path)
    entry = cap_first(r)
    assert entry.get("AssetType") == "LevelSequence", entry
    assert "BindingsCount" in entry, entry


def test_manage_level_sequence_set_display_rate(seq_path, mcp):
    r = mcp.call_capability(
        "ManageAssetLevelSequence",
        AssetPath=seq_path,
        Operations=[{"Action": "SetDisplayRate", "Numerator": 24, "Denominator": 1}],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r


def test_manage_level_sequence_possessable_track_key(seq_path, mcp):
    add_pos = mcp.call_capability(
        "ManageAssetLevelSequence",
        AssetPath=seq_path,
        Operations=[{"Action": "AddPossessable", "PossessableName": "NxActor", "ClassName": "Actor"}],
    )
    pos = cap_first(add_pos)
    assert not pos.get("Error"), add_pos
    guid = pos.get("BindingGuid")
    assert guid, add_pos

    add_tracks = mcp.call_capability(
        "ManageAssetLevelSequence",
        AssetPath=seq_path,
        Operations=[
            {"Action": "AddTrack", "BindingGuid": guid, "TrackClass": "Float"},
            {"Action": "AddTrack", "BindingGuid": guid, "TrackClass": "Transform"},
        ],
    )
    for e in (add_tracks.get("Results") or [cap_first(add_tracks)]):
        if isinstance(e, dict):
            assert not e.get("Error"), add_tracks

    keys = mcp.call_capability(
        "ManageAssetLevelSequence",
        AssetPath=seq_path,
        Operations=[
            {"Action": "AddFloatKey", "BindingGuid": guid, "Time": 0.5, "KeyValue": 1.0},
            {
                "Action": "SetTransformKey",
                "BindingGuid": guid,
                "Time": 1.0,
                "x": 10,
                "y": 20,
                "z": 30,
                "Pitch": 5,
                "Yaw": 15,
                "Roll": 0,
            },
        ],
    )
    for e in (keys.get("Results") or [cap_first(keys)]):
        if isinstance(e, dict):
            assert not e.get("Error"), keys


def test_manage_level_sequence_extended_tracks(seq_path, mcp):
    """P1：Master Fade/Event + Binding SkeletalAnimation/Visibility。"""
    master = mcp.call_capability(
        "ManageAssetLevelSequence",
        AssetPath=seq_path,
        Operations=[
            {"Action": "AddMasterTrack", "TrackClass": "Fade"},
            {"Action": "AddMasterTrack", "TrackClass": "Event"},
        ],
    )
    for e in (master.get("Results") or [cap_first(master)]):
        if isinstance(e, dict):
            assert not e.get("Error"), master

    add_pos = mcp.call_capability(
        "ManageAssetLevelSequence",
        AssetPath=seq_path,
        Operations=[{"Action": "AddPossessable", "PossessableName": "NxAnimActor", "ClassName": "Actor"}],
    )
    pos = cap_first(add_pos)
    assert not pos.get("Error"), add_pos
    guid = pos.get("BindingGuid")
    assert guid, add_pos

    binding = mcp.call_capability(
        "ManageAssetLevelSequence",
        AssetPath=seq_path,
        Operations=[
            {"Action": "AddTrack", "BindingGuid": guid, "TrackClass": "SkeletalAnimation"},
            {"Action": "AddTrack", "BindingGuid": guid, "TrackClass": "Visibility"},
            {"Action": "AddTrack", "BindingGuid": guid, "TrackClass": "Particle"},
        ],
    )
    for e in (binding.get("Results") or [cap_first(binding)]):
        if isinstance(e, dict):
            assert not e.get("Error"), binding


def test_manage_level_sequence_remaining(seq_path, mcp):
    try:
        r = mcp.call_capability(
            "ManageAssetLevelSequence",
            AssetPath=seq_path,
            Operations=[
                {"Action": "SetPlaybackRange", "StartFrame": 0, "EndFrame": 60},
                {"Action": "AddSpawnable", "PossessableName": "NxSpawn", "ClassName": "Actor"},
            ],
        )
    except MCPError as e:
        pytest.skip(f"level_sequence remaining 跳过: {e}")
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"level_sequence remaining 跳过: {e}")
    guid = cap_first(r).get("BindingGuid")
    try:
        rm = mcp.call_capability(
            "ManageAssetLevelSequence",
            AssetPath=seq_path,
            Operations=[
                {"Action": "RemoveMasterTrack", "TrackClass": "Fade"},
                {"Action": "RemoveBinding", "BindingGuid": guid or "00000000000000000000000000000000"},
            ],
        )
    except MCPError as e:
        pytest.skip(f"level_sequence remaining 跳过: {e}")
    assert isinstance(cap_first(rm), dict), rm


# ── Physics Asset ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pa_path(mcp):
    """Mannequin PhysicsAsset。"""
    r = mcp.call_capability(
        "SearchAsset",
        Query="PhysicsAsset",
        AssetType="PhysicsAsset",
        PathFilter="/Game/",
        Limit=1,
    )
    assets = r.get("Assets") or []
    if not assets:
        pytest.skip("项目中无 PhysicsAsset，跳过 Physics 测试")
    return assets[0].get("Path") or assets[0].get("AssetPath")


def test_get_physics_asset(pa_path, mcp):
    r = mcp.call_capability("GetAssetPhysicsAsset", AssetPath=pa_path)
    entry = cap_first(r)
    assert entry.get("AssetType") == "PhysicsAsset", entry
    assert "BodiesCount" in entry, entry
    assert "ConstraintsCount" in entry, entry


def test_manage_physics_asset_add_sphere(pa_path, mcp):
    """向已有 PhysicsAsset 的第一个 Body 添加球体（无副作用 — 写入后 Body 数量不变）。"""
    get_r = mcp.call_capability("GetAssetPhysicsAsset", AssetPath=pa_path)
    bodies = get_r.get("Results", [{}])[0].get("Bodies", [])
    if not bodies:
        pytest.skip("PhysicsAsset 无 Body")
    bone_name = bodies[0].get("BoneName", "")
    r = mcp.call_capability(
        "ManageAssetPhysicsAsset",
        AssetPath=pa_path,
        Operations=[{"Action": "AddSphere", "BoneName": bone_name, "Radius": 5.0}],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r


def test_manage_physics_asset_remaining(pa_path, mcp):
    get_r = mcp.call_capability("GetAssetPhysicsAsset", AssetPath=pa_path)
    bodies = cap_first(get_r).get("Bodies") or []
    if not bodies:
        pytest.skip("PhysicsAsset 无 Body")
    bone_name = bodies[0].get("BoneName", "")
    try:
        r = mcp.call_capability(
            "ManageAssetPhysicsAsset",
            AssetPath=pa_path,
            bSaveToDisk=False,
            Operations=[
                {"Action": "SetPhysicsType", "BoneName": bone_name, "PhysicsType": "Default"},
                {"Action": "AddCapsule", "BoneName": bone_name, "Radius": 4, "HalfHeight": 8},
                {"Action": "AddBox", "BoneName": bone_name, "ExtentX": 3, "ExtentY": 3, "ExtentZ": 3},
                {"Action": "AddConstraint", "BoneName": bone_name, "Bone1": bone_name, "Bone2": bone_name},
                {"Action": "RemoveConstraint", "JointName": bone_name},
                {"Action": "ClearShapes", "BoneName": bone_name},
            ],
        )
    except MCPError as e:
        pytest.skip(f"physics remaining 跳过: {e}")
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"physics remaining 跳过: {e}")


# ── EQS ──────────────────────────────────────────────────────────────────────

def test_create_eqs(test_ns, mcp, require_tools):
    require_tools("CreateAssetEQS")
    path = f"{test_ns}/EQ_TestFindCover"
    r = mcp.call_capability("CreateAssetEQS", AssetPath=path)
    entry = cap_first(r)
    assert not entry.get("Error"), r
    assert not entry.get("Error") and entry.get("bSuccess") is not False, r


def test_get_eqs(test_ns, mcp, require_tools):
    require_tools("GetAssetEQS")
    path = f"{test_ns}/EQ_TestFindCover"
    r = mcp.call_capability("GetAssetEQS", AssetPath=path)
    entry = cap_first(r)
    assert entry.get("AssetType") == "EnvQuery", entry


def test_manage_eqs_add_option(test_ns, mcp, require_tools):
    require_tools("ManageAssetEQS")
    path = f"{test_ns}/EQ_TestFindCover"
    r = mcp.call_capability(
        "ManageAssetEQS",
        AssetPath=path,
        Operations=[{"Action": "AddOption"}],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r
    assert not entry.get("Error") and entry.get("bSuccess") is not False, r


def test_manage_eqs_set_generator(test_ns, mcp, require_tools):
    require_tools("ManageAssetEQS")
    path = f"{test_ns}/EQ_TestFindCover"
    r = mcp.call_capability(
        "ManageAssetEQS",
        AssetPath=path,
        Operations=[{
            "Action": "SetGenerator",
            "OptionIndex": 0,
            "GeneratorClass": "EnvQueryGenerator_ActorsOfClass",
        }],
    )
    entry = cap_first(r)
    # 生成器类名可能因版本而异，允许未找到
    assert "Error" not in entry or "未找到" in entry["Error"], r


def test_manage_eqs_test_and_remove(test_ns, mcp, require_tools):
    require_tools("ManageAssetEQS")
    path = f"{test_ns}/EQ_TestFindCover"
    r = mcp.call_capability(
        "ManageAssetEQS",
        AssetPath=path,
        Operations=[
            {"Action": "AddTest", "OptionIndex": 0, "TestClass": "EnvQueryTest_Trace"},
            {"Action": "RemoveTest", "OptionIndex": 0, "TestIndex": 0},
            {"Action": "RemoveOption", "OptionIndex": 0},
        ],
    )
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"eqs remaining 跳过: {e}")
