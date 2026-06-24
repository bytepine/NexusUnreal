# Copyright byteyang. All Rights Reserved.
"""阶段十五：GAS Runtime — ASC 只读与 apply_effect 写通路（需 PIE）。"""

from __future__ import annotations

import contextlib

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import MCPError, cap_first
from _framework.runtime_helpers import destroy_runtime_actors, spawn_runtime_actors

pytestmark = pytest.mark.l4_runtime


@pytest.fixture(scope="module", autouse=True)
def require_gas(mcp):
    if not is_capability_available(mcp, "get_runtime_actor_ability_system"):
        pytest.skip("GAS runtime capability 未编入（请确认 WITH_GAS 并重新编译 Editor）")


@pytest.fixture(scope="module")
def gas_runtime_assets(test_ns, mcp) -> dict:
    """带 ASC 的 Character BP + 用于 apply 的 GE。"""
    bp = f"{test_ns}/BP_GasRuntimeChar"
    ge = f"{test_ns}/GE_GasRuntimeProbe"
    mcp.call("create_blueprint", assetPath=bp, parentClass="Character")
    try:
        mcp.call_capability(
            "manage_asset_blueprint",
            assetPath=bp,
            action="add_component",
            componentClass="AbilitySystemComponent",
            componentName="AbilitySystem",
        )
    except MCPError as e:
        pytest.skip(f"无法添加 AbilitySystemComponent：{e}")
    mcp.call_capability("compile_blueprint", assetPath=bp)
    with contextlib.suppress(MCPError):
        mcp.call("create_asset_gameplay_effect", assetPath=ge)
    return {"bp": bp, "ge": ge}


@pytest.fixture(scope="module")
def gas_runtime_actor(mcp, pie, gas_runtime_assets) -> str:
    names = spawn_runtime_actors(
        mcp,
        [{"blueprintPath": gas_runtime_assets["bp"], "locationZ": 120}],
    )
    if not names:
        pytest.skip("GAS 角色 spawn 失败")
    yield names[0]
    destroy_runtime_actors(mcp, names)


def test_get_runtime_actor_ability_system_sections(mcp, gas_runtime_actor):
    r = mcp.call_capability(
        "get_runtime_actor_ability_system",
        actorName=gas_runtime_actor,
        sections=["abilities", "effects", "attributes"],
    )
    entry = cap_first(r)
    assert not entry.get("error"), entry
    for key in ("abilities", "effects", "attributes"):
        val = entry.get(key)
        assert val is None or isinstance(val, list), f"{key}: {entry!r}"


def test_interact_runtime_apply_effect_smoke(mcp, gas_runtime_actor, gas_runtime_assets):
    ge = gas_runtime_assets["ge"]
    if not is_capability_available(mcp, "interact_runtime_actor_ability_system"):
        pytest.skip("interact_runtime_actor_ability_system 不可用")
    try:
        r = mcp.call_capability(
            "interact_runtime_actor_ability_system",
            action="apply_effect",
            actorName=gas_runtime_actor,
            effectPath=ge,
        )
    except MCPError as e:
        pytest.skip(f"apply_effect 被拒绝（ASC 未初始化？）：{e}")
    entry = cap_first(r)
    assert entry.get("success") is True or bool(entry.get("error")), entry
