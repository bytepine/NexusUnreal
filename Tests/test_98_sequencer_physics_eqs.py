# Copyright byteyang. All Rights Reserved.
"""阶段九八：Tier2 — LevelSequencer / PhysicsAsset / EQS。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.l3_asset


# ── Level Sequence ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def seq_path(test_ns, mcp):
    """动态发现或跳过。"""
    r = mcp.call_capability(
        "search_asset",
        query="LevelSequence",
        assetType="LevelSequence",
        pathFilter="/Game/",
        limit=1,
    )
    assets = r.get("results") or []
    if not assets:
        pytest.skip("项目中无 LevelSequence 资产，跳过 Sequencer 测试")
    return assets[0].get("path") or assets[0].get("assetPath")


def test_get_level_sequence(seq_path, mcp):
    r = mcp.call_capability("get_asset_level_sequence", assetPath=seq_path)
    results = r.get("results") or []
    assert len(results) == 1, r
    entry = results[0]
    assert entry.get("assetType") == "LevelSequence", entry
    assert "bindingsCount" in entry, entry


def test_manage_level_sequence_set_display_rate(seq_path, mcp):
    r = mcp.call_capability(
        "manage_asset_level_sequence",
        assetPath=seq_path,
        operations=[{"action": "set_display_rate", "numerator": 24, "denominator": 1}],
    )
    results = r.get("results") or []
    assert len(results) == 1, r
    assert not results[0].get("error"), r


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
    assets = r.get("results") or []
    if not assets:
        pytest.skip("项目中无 PhysicsAsset，跳过 Physics 测试")
    return assets[0].get("path") or assets[0].get("assetPath")


def test_get_physics_asset(pa_path, mcp):
    r = mcp.call_capability("get_asset_physics_asset", assetPath=pa_path)
    results = r.get("results") or []
    assert len(results) == 1, r
    entry = results[0]
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
    results = r.get("results") or []
    assert len(results) == 1, r
    assert not results[0].get("error"), r


# ── EQS ──────────────────────────────────────────────────────────────────────

def test_create_eqs(test_ns, mcp):
    path = f"{test_ns}/EQ_TestFindCover"
    r = mcp.call_capability("create_asset_eqs", assetPath=path)
    results = r.get("results") or []
    assert len(results) == 1, r
    assert not results[0].get("error"), r
    assert results[0].get("success"), r


def test_get_eqs(test_ns, mcp):
    path = f"{test_ns}/EQ_TestFindCover"
    r = mcp.call_capability("get_asset_eqs", assetPath=path)
    results = r.get("results") or []
    assert len(results) == 1, r
    entry = results[0]
    assert entry.get("assetType") == "EnvQuery", entry


def test_manage_eqs_add_option(test_ns, mcp):
    path = f"{test_ns}/EQ_TestFindCover"
    r = mcp.call_capability(
        "manage_asset_eqs",
        assetPath=path,
        operations=[{"action": "add_option"}],
    )
    results = r.get("results") or []
    assert len(results) == 1, r
    assert not results[0].get("error"), r
    assert results[0].get("success"), r


def test_manage_eqs_set_generator(test_ns, mcp):
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
    results = r.get("results") or []
    assert len(results) == 1, r
    # 生成器类名可能因版本而异，允许未找到
    assert "error" not in results[0] or "未找到" in results[0]["error"], r
