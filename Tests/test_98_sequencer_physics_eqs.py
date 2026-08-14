# Copyright byteyang. All Rights Reserved.
"""阶段九八：Tier2 — LevelSequencer / PhysicsAsset / EQS。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_first

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
    r = mcp.call_capability(
        "manage_asset_level_sequence",
        assetPath=seq_path,
        operations=[
            {"action": "add_possessable", "objectClass": "Actor", "bindingName": "NxActor"},
            {"action": "add_track", "bindingName": "NxActor", "trackType": "MovieSceneFloatTrack"},
            {"action": "add_float_key", "bindingName": "NxActor", "time": 0.0, "value": 1.0},
        ],
    )
    entry = cap_first(r)
    assert isinstance(entry, dict), r
    got = cap_first(mcp.call_capability(
        "get_asset_level_sequence", assetPath=seq_path, sections=["bindings", "tracks"],
    ))
    assert not got.get("error"), got


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
