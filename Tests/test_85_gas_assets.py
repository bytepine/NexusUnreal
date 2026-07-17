# Copyright byteyang. All Rights Reserved.
"""阶段十：GAS 资产 — GameplayAbility / GameplayEffect / AttributeSet。

所有用例在 WITH_GAS=0（tools/list 中无 GAS cap）时整体 skip。
"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l3_asset

# ── 公共 fixture ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="module", autouse=True)
def require_gas(mcp):
    """GameplayAbilities 已在 .uproject 启用；探测 GAS capability 是否已编入 NexusLink。"""
    if not is_capability_available(mcp, "create_asset_gameplay_ability"):
        pytest.skip(
            "GAS capability 未注册（请确认 GameplayAbilities 已启用并重新编译 Editor）"
        )


# ── GameplayAbility ──────────────────────────────────────────────────────────


def test_ga_create(test_ns, mcp):
    path = f"{test_ns}/GA_TestAbility"
    r = mcp.call("create_asset_gameplay_ability", assetPath=path)
    entry = cap_first(r)
    assert not entry.get("error") and entry.get("success") is not False, f"create_asset_gameplay_ability 返回: {r!r}"
    assert entry.get("name") or entry.get("path"), entry


def test_ga_get_metadata(test_ns, mcp):
    path = f"{test_ns}/GA_TestAbility"
    r = mcp.call("get_asset_gameplay_ability", assetPath=path, sections=["metadata"])
    assert isinstance(r, dict), r
    entries = r.get("results") or r.get("entries") or [r]
    assert entries, f"无 entries: {r!r}"
    entry = entries[0]
    assert "instancingPolicy" in entry, f"缺少 instancingPolicy: {entry!r}"


def test_ga_get_tags(test_ns, mcp):
    path = f"{test_ns}/GA_TestAbility"
    r = mcp.call("get_asset_gameplay_ability", assetPath=path, sections=["tags"])
    assert isinstance(r, dict), r


def test_ga_manage_set_policy(test_ns, mcp):
    path = f"{test_ns}/GA_TestAbility"
    r = mcp.call(
        "manage_asset_gameplay_ability",
        assetPath=path,
        action="set_policy",
        instancingPolicy="InstancedPerActor",
    )
    assert not r.get("error") and r.get("success") is not False, f"manage_asset_gameplay_ability set_policy 返回: {r!r}"


def test_ga_policy_readback(test_ns, mcp):
    """确认 set_policy 写入后可读回。"""
    path = f"{test_ns}/GA_TestAbility"
    r = mcp.call("get_asset_gameplay_ability", assetPath=path, sections=["metadata"])
    entries = r.get("results") or r.get("entries") or [r]
    entry = entries[0]
    assert entry.get("instancingPolicy") == "InstancedPerActor", (
        f"期望 InstancedPerActor，实际: {entry.get('instancingPolicy')!r}"
    )


# ── GameplayEffect ───────────────────────────────────────────────────────────


def test_ge_create(test_ns, mcp):
    path = f"{test_ns}/GE_TestEffect"
    r = mcp.call("create_asset_gameplay_effect", assetPath=path)
    assert not cap_first(r).get("error") and cap_first(r).get("success") is not False, f"create_asset_gameplay_effect 返回: {r!r}"


def test_ge_get_policy(test_ns, mcp):
    path = f"{test_ns}/GE_TestEffect"
    r = mcp.call("get_asset_gameplay_effect", assetPath=path, sections=["policy"])
    assert isinstance(r, dict), r
    entries = r.get("results") or r.get("entries") or [r]
    entry = entries[0]
    assert "durationPolicy" in entry, f"缺少 durationPolicy: {entry!r}"


def test_ge_manage_set_policy(test_ns, mcp):
    path = f"{test_ns}/GE_TestEffect"
    r = mcp.call(
        "manage_asset_gameplay_effect",
        assetPath=path,
        operations=[{"action": "set_policy", "durationPolicy": "Infinite"}],
    )
    assert not r.get("error"), f"manage set_policy 返回: {r!r}"


def test_ge_get_modifiers_empty(test_ns, mcp):
    path = f"{test_ns}/GE_TestEffect"
    r = mcp.call("get_asset_gameplay_effect", assetPath=path, sections=["modifiers"])
    assert isinstance(r, dict), r


def test_ge_manage_tags(test_ns, mcp):
    """set_tags 操作应无报错完成（即使 Tag 在项目中未注册，error 信息可接受）。"""
    path = f"{test_ns}/GE_TestEffect"
    try:
        r = mcp.call(
            "manage_asset_gameplay_effect",
            assetPath=path,
            operations=[{
                "action": "set_tags",
                "tagContainer": "grantedTags",
                "tags": [],
                "mode": "set",
            }],
        )
        assert not r.get("error"), r
    except MCPError:
        pass  # Tag 未在项目注册时允许失败


# ── AttributeSet ─────────────────────────────────────────────────────────────


def test_as_create(test_ns, mcp):
    path = f"{test_ns}/AS_TestStats"
    r = mcp.call("create_asset_attribute_set", assetPath=path)
    assert not cap_first(r).get("error") and cap_first(r).get("success") is not False, f"create_asset_attribute_set 返回: {r!r}"


def test_as_get_empty(test_ns, mcp):
    """新建的 AS 不含 FGameplayAttributeData 属性时，attributes 为空数组而非 error。"""
    path = f"{test_ns}/AS_TestStats"
    r = mcp.call("get_asset_attribute_set", assetPath=path)
    assert isinstance(r, dict), r
    entries = r.get("results") or r.get("entries") or [r]
    entry = entries[0]
    assert "attributes" in entry, f"缺少 attributes 字段: {entry!r}"
    assert isinstance(entry["attributes"], list), entry


def test_as_manage_reset_smoke(test_ns, mcp):
    """manage_asset_attribute_set reset：空 AS 无属性时 ops 可能失败，仅验通路。"""
    path = f"{test_ns}/AS_TestStats"
    try:
        r = mcp.call(
            "manage_asset_attribute_set",
            assetPath=path,
            operations=[{"action": "reset", "attributeName": "Health"}],
        )
    except MCPError:
        pytest.skip("manage_asset_attribute_set 不可用或未编译")
    assert isinstance(r, dict), r
