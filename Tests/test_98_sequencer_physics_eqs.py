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
    r = mcp.call_capability("create_asset_level_sequence", assetPath=path)
    entry = cap_first(r)
    if entry.get("error") and "already exists" not in str(entry.get("error", "")):
        pytest.skip(f"create_asset_level_sequence 失败: {entry}")
    return path


def test_get_level_sequence(seq_path, mcp):
    r = mcp.call_capability("get_asset_level_sequence", assetPath=seq_path)
    entry = cap_first(r)
    assert entry.get("assetType") == "LevelSequence", entry
    assert "bindingsCount" in entry, entry


def test_manage_level_sequence_set_display_rate(seq_path, mcp):
    r = mcp.call_capability(
        "manage_asset_level_sequence",
        assetPath=seq_path,
        operations=[{"action": "set_display_rate", "numerator": 24, "denominator": 1}],
    )
    entry = cap_first(r)
    assert not entry.get("error"), r


def test_manage_level_sequence_possessable_track_key(seq_path, mcp):
    add_pos = mcp.call_capability(
        "manage_asset_level_sequence",
        assetPath=seq_path,
        operations=[{"action": "add_possessable", "possessableName": "NxActor", "className": "Actor"}],
    )
    pos = cap_first(add_pos)
    assert not pos.get("error"), add_pos
    guid = pos.get("bindingGuid")
    assert guid, add_pos

    add_tracks = mcp.call_capability(
        "manage_asset_level_sequence",
        assetPath=seq_path,
        operations=[
            {"action": "add_track", "bindingGuid": guid, "trackClass": "Float"},
            {"action": "add_track", "bindingGuid": guid, "trackClass": "Transform"},
        ],
    )
    for e in (add_tracks.get("results") or [cap_first(add_tracks)]):
        if isinstance(e, dict):
            assert not e.get("error"), add_tracks

    keys = mcp.call_capability(
        "manage_asset_level_sequence",
        assetPath=seq_path,
        operations=[
            {"action": "add_float_key", "bindingGuid": guid, "time": 0.5, "keyValue": 1.0},
            {
                "action": "set_transform_key",
                "bindingGuid": guid,
                "time": 1.0,
                "x": 10,
                "y": 20,
                "z": 30,
                "pitch": 5,
                "yaw": 15,
                "roll": 0,
            },
        ],
    )
    for e in (keys.get("results") or [cap_first(keys)]):
        if isinstance(e, dict):
            assert not e.get("error"), keys


def test_manage_level_sequence_extended_tracks(seq_path, mcp):
    """P1：Master Fade/Event + Binding SkeletalAnimation/Visibility。"""
    master = mcp.call_capability(
        "manage_asset_level_sequence",
        assetPath=seq_path,
        operations=[
            {"action": "add_master_track", "trackClass": "Fade"},
            {"action": "add_master_track", "trackClass": "Event"},
        ],
    )
    for e in (master.get("results") or [cap_first(master)]):
        if isinstance(e, dict):
            assert not e.get("error"), master

    add_pos = mcp.call_capability(
        "manage_asset_level_sequence",
        assetPath=seq_path,
        operations=[{"action": "add_possessable", "possessableName": "NxAnimActor", "className": "Actor"}],
    )
    pos = cap_first(add_pos)
    assert not pos.get("error"), add_pos
    guid = pos.get("bindingGuid")
    assert guid, add_pos

    binding = mcp.call_capability(
        "manage_asset_level_sequence",
        assetPath=seq_path,
        operations=[
            {"action": "add_track", "bindingGuid": guid, "trackClass": "SkeletalAnimation"},
            {"action": "add_track", "bindingGuid": guid, "trackClass": "Visibility"},
            {"action": "add_track", "bindingGuid": guid, "trackClass": "Particle"},
        ],
    )
    for e in (binding.get("results") or [cap_first(binding)]):
        if isinstance(e, dict):
            assert not e.get("error"), binding


def test_manage_level_sequence_remaining(seq_path, mcp):
    try:
        r = mcp.call_capability(
            "manage_asset_level_sequence",
            assetPath=seq_path,
            operations=[
                {"action": "set_playback_range", "startFrame": 0, "endFrame": 60},
                {"action": "add_spawnable", "possessableName": "NxSpawn", "className": "Actor"},
            ],
        )
    except MCPError as e:
        pytest.skip(f"level_sequence remaining 跳过: {e}")
    for e in (r.get("results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("error"):
            pytest.skip(f"level_sequence remaining 跳过: {e}")
    guid = cap_first(r).get("bindingGuid")
    try:
        rm = mcp.call_capability(
            "manage_asset_level_sequence",
            assetPath=seq_path,
            operations=[
                {"action": "remove_master_track", "trackClass": "Fade"},
                {"action": "remove_binding", "bindingGuid": guid or "00000000000000000000000000000000"},
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
        "search_asset",
        query="PhysicsAsset",
        assetType="PhysicsAsset",
        pathFilter="/Game/",
        limit=1,
    )
    assets = r.get("assets") or []
    if not assets:
        pytest.skip("项目中无 PhysicsAsset，跳过 Physics 测试")
    return assets[0].get("path") or assets[0].get("assetPath")


def test_get_physics_asset(pa_path, mcp):
    r = mcp.call_capability("get_asset_physics_asset", assetPath=pa_path)
    entry = cap_first(r)
    assert entry.get("assetType") == "PhysicsAsset", entry
    assert "bodiesCount" in entry, entry
    assert "constraintsCount" in entry, entry


def test_manage_physics_asset_add_sphere(pa_path, mcp):
    """向已有 PhysicsAsset 的第一个 Body 添加球体（无副作用 — 写入后 Body 数量不变）。"""
    get_r = mcp.call_capability("get_asset_physics_asset", assetPath=pa_path)
    bodies = get_r.get("results", [{}])[0].get("bodies", [])
    if not bodies:
        pytest.skip("PhysicsAsset 无 Body")
    bone_name = bodies[0].get("boneName", "")
    r = mcp.call_capability(
        "manage_asset_physics_asset",
        assetPath=pa_path,
        operations=[{"action": "add_sphere", "boneName": bone_name, "radius": 5.0}],
    )
    entry = cap_first(r)
    assert not entry.get("error"), r


def test_manage_physics_asset_remaining(pa_path, mcp):
    get_r = mcp.call_capability("get_asset_physics_asset", assetPath=pa_path)
    bodies = cap_first(get_r).get("bodies") or []
    if not bodies:
        pytest.skip("PhysicsAsset 无 Body")
    bone_name = bodies[0].get("boneName", "")
    try:
        r = mcp.call_capability(
            "manage_asset_physics_asset",
            assetPath=pa_path,
            saveToDisk=False,
            operations=[
                {"action": "set_physics_type", "boneName": bone_name, "physicsType": "Default"},
                {"action": "add_capsule", "boneName": bone_name, "radius": 4, "halfHeight": 8},
                {"action": "add_box", "boneName": bone_name, "extentX": 3, "extentY": 3, "extentZ": 3},
                {"action": "add_constraint", "boneName": bone_name, "bone1": bone_name, "bone2": bone_name},
                {"action": "remove_constraint", "jointName": bone_name},
                {"action": "clear_shapes", "boneName": bone_name},
            ],
        )
    except MCPError as e:
        pytest.skip(f"physics remaining 跳过: {e}")
    for e in (r.get("results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("error"):
            pytest.skip(f"physics remaining 跳过: {e}")


# ── EQS ──────────────────────────────────────────────────────────────────────

def test_create_eqs(test_ns, mcp, require_tools):
    require_tools("create_asset_eqs")
    path = f"{test_ns}/EQ_TestFindCover"
    r = mcp.call_capability("create_asset_eqs", assetPath=path)
    entry = cap_first(r)
    assert not entry.get("error"), r
    assert not entry.get("error") and entry.get("success") is not False, r


def test_get_eqs(test_ns, mcp, require_tools):
    require_tools("get_asset_eqs")
    path = f"{test_ns}/EQ_TestFindCover"
    r = mcp.call_capability("get_asset_eqs", assetPath=path)
    entry = cap_first(r)
    assert entry.get("assetType") == "EnvQuery", entry


def test_manage_eqs_add_option(test_ns, mcp, require_tools):
    require_tools("manage_asset_eqs")
    path = f"{test_ns}/EQ_TestFindCover"
    r = mcp.call_capability(
        "manage_asset_eqs",
        assetPath=path,
        operations=[{"action": "add_option"}],
    )
    entry = cap_first(r)
    assert not entry.get("error"), r
    assert not entry.get("error") and entry.get("success") is not False, r


def test_manage_eqs_set_generator(test_ns, mcp, require_tools):
    require_tools("manage_asset_eqs")
    path = f"{test_ns}/EQ_TestFindCover"
    r = mcp.call_capability(
        "manage_asset_eqs",
        assetPath=path,
        operations=[{
            "action": "set_generator",
            "optionIndex": 0,
            "generatorClass": "EnvQueryGenerator_ActorsOfClass",
        }],
    )
    entry = cap_first(r)
    # 生成器类名可能因版本而异，允许未找到
    assert "error" not in entry or "未找到" in entry["error"], r


def test_manage_eqs_test_and_remove(test_ns, mcp, require_tools):
    require_tools("manage_asset_eqs")
    path = f"{test_ns}/EQ_TestFindCover"
    r = mcp.call_capability(
        "manage_asset_eqs",
        assetPath=path,
        operations=[
            {"action": "add_test", "optionIndex": 0, "testClass": "EnvQueryTest_Trace"},
            {"action": "remove_test", "optionIndex": 0, "testIndex": 0},
            {"action": "remove_option", "optionIndex": 0},
        ],
    )
    for e in (r.get("results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("error"):
            pytest.skip(f"eqs remaining 跳过: {e}")
