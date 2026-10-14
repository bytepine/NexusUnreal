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
    if not is_capability_available(mcp, "CreateAssetGameplayAbility"):
        pytest.skip(
            "GAS capability 未注册（请确认 GameplayAbilities 已启用并重新编译 Editor）"
        )


# ── GameplayAbility ──────────────────────────────────────────────────────────


def test_ga_create(test_ns, mcp):
    path = f"{test_ns}/GA_TestAbility"
    r = mcp.call("CreateAssetGameplayAbility", AssetPath=path)
    entry = cap_first(r)
    assert not entry.get("Error") and entry.get("bSuccess") is not False, f"create_asset_gameplay_ability 返回: {r!r}"
    assert entry.get("name") or entry.get("Path"), entry


def test_ga_get_metadata(test_ns, mcp):
    path = f"{test_ns}/GA_TestAbility"
    r = mcp.call("GetAssetGameplayAbility", AssetPath=path, Sections=["metadata"])
    assert isinstance(r, dict), r
    entry = cap_first(r)
    assert "InstancingPolicy" in entry, f"缺少 instancingPolicy: {entry!r}"


def test_ga_get_tags(test_ns, mcp):
    path = f"{test_ns}/GA_TestAbility"
    r = mcp.call("GetAssetGameplayAbility", AssetPath=path, Sections=["Tags"])
    assert isinstance(r, dict), r


def test_ga_manage_set_policy(test_ns, mcp):
    path = f"{test_ns}/GA_TestAbility"
    r = mcp.call(
        "ManageAssetGameplayAbility",
        AssetPath=path,
        Operations=[{
            "Action": "SetPolicy",
            "InstancingPolicy": "InstancedPerActor",
        }],
    )
    entry = cap_first(r)
    assert not entry.get("Error") and entry.get("bSuccess") is not False, (
        f"manage_asset_gameplay_ability set_policy 返回: {r!r}"
    )


def test_ga_policy_readback(test_ns, mcp):
    """确认 set_policy 写入后可读回。"""
    path = f"{test_ns}/GA_TestAbility"
    r = mcp.call("GetAssetGameplayAbility", AssetPath=path, Sections=["metadata"])
    entry = cap_first(r)
    assert entry.get("InstancingPolicy") == "InstancedPerActor", (
        f"期望 InstancedPerActor，实际: {entry.get('InstancingPolicy')!r}"
    )


def test_ga_manage_blueprint_set_defaults_non_actor(test_ns, mcp):
    """回归：此前 set_defaults 与 add_component 绑在同一 Actor 门后，GameplayAbility
    （非 Actor 子类）CDO 完全无法写自定义属性；修复后应可写任意 Blueprint 的 CDO。
    add_variable 单独一次调用且 bCompile=true——同批 operations 内部处于事务中会跳过全量
    Compile（见 NexusManageAssetBlueprintCapability.cpp:206），新变量不会立即出现在 CDO 上；
    bCompile=true 走事务外的 ApplyIfRequested，确保下一步 set_defaults 能解析到该属性。"""
    path = f"{test_ns}/GA_TestAbility"
    r_var = mcp.call_capability(
        "ManageAssetBlueprint",
        AssetPath=path,
        bCompile=True,
        Operations=[{"Action": "AddVariable", "VariableName": "TestCdoFlag",
                     "VariableType": "bool", "DefaultValue": "true"}],
    )
    assert not cap_first(r_var).get("Error"), f"add_variable on GA: {r_var!r}"

    r_set = mcp.call_capability(
        "ManageAssetBlueprint",
        AssetPath=path,
        Operations=[{"Action": "SetDefaults", "PropertyPath": "TestCdoFlag", "Value": "false"}],
    )
    entry = cap_first(r_set)
    assert not entry.get("Error"), f"set_defaults on non-Actor (GA) BP should now succeed: {entry!r}"

    r_get = mcp.call_capability("GetAssetBlueprint", AssetPath=path, Sections=["Defaults"])
    assert isinstance(cap_first(r_get).get("Defaults"), list), f"defaults read-back failed: {r_get!r}"


def test_ga_manage_blueprint_add_component_still_actor_only(test_ns, mcp):
    """回归：GameplayAbility 仍不是 Actor 子类，add_component 应继续被拒绝（Actor 门未被误删）。"""
    path = f"{test_ns}/GA_TestAbility"
    r = mcp.call_capability(
        "ManageAssetBlueprint",
        AssetPath=path,
        Operations=[{"Action": "AddComponent", "ComponentClass": "SceneComponent",
                     "ComponentName": "ShouldFail"}],
    )
    entry = cap_first(r)
    assert entry.get("Error"), f"add_component on GA (non-Actor) BP should still fail: {entry!r}"
    assert "Actor" in entry.get("Error", ""), entry


# ── GameplayEffect ───────────────────────────────────────────────────────────


def test_ge_create(test_ns, mcp):
    path = f"{test_ns}/GE_TestEffect"
    r = mcp.call("CreateAssetGameplayEffect", AssetPath=path)
    assert not cap_first(r).get("Error") and cap_first(r).get("bSuccess") is not False, f"create_asset_gameplay_effect 返回: {r!r}"


def test_ge_get_policy(test_ns, mcp):
    path = f"{test_ns}/GE_TestEffect"
    r = mcp.call("GetAssetGameplayEffect", AssetPath=path, Sections=["policy"])
    assert isinstance(r, dict), r
    entry = cap_first(r)
    assert "DurationPolicy" in entry, f"缺少 durationPolicy: {entry!r}"


def test_ge_manage_set_policy(test_ns, mcp):
    path = f"{test_ns}/GE_TestEffect"
    r = mcp.call(
        "ManageAssetGameplayEffect",
        AssetPath=path,
        Operations=[{"Action": "SetPolicy", "DurationPolicy": "Infinite"}],
    )
    assert not cap_first(r).get("Error"), f"manage set_policy 返回: {r!r}"


def test_ge_get_modifiers_empty(test_ns, mcp):
    path = f"{test_ns}/GE_TestEffect"
    r = mcp.call("GetAssetGameplayEffect", AssetPath=path, Sections=["Modifiers"])
    assert isinstance(r, dict), r


def test_ge_manage_tags(test_ns, mcp):
    """set_tags 操作应无报错完成（即使 Tag 在项目中未注册，error 信息可接受）。"""
    path = f"{test_ns}/GE_TestEffect"
    try:
        r = mcp.call(
            "ManageAssetGameplayEffect",
            AssetPath=path,
            Operations=[{
                "Action": "SetTags",
                "TagContainer": "GrantedTags",
                "Tags": [],
                "Mode": "Set",
            }],
        )
        assert not r.get("Error"), r
    except MCPError:
        pass  # Tag 未在项目注册时允许失败


def test_ga_remaining_sections_and_cost(test_ns, mcp):
    path = f"{test_ns}/GA_TestAbility"
    r = mcp.call(
        "GetAssetGameplayAbility",
        AssetPath=path,
        Sections=["costs", "graphOverview"],
    )
    assert isinstance(r, dict), r
    try:
        mcp.call(
            "ManageAssetGameplayAbility",
            AssetPath=path,
            Operations=[{"Action": "SetCostCooldown", "cost": "0", "cooldown": "0"}],
        )
    except MCPError:
        pass


def test_ge_modifiers_and_cues(test_ns, mcp):
    path = f"{test_ns}/GE_TestEffect"
    mcp.call(
        "GetAssetGameplayEffect",
        AssetPath=path,
        Sections=["Tags", "cues"],
    )
    try:
        r = mcp.call(
            "ManageAssetGameplayEffect",
            AssetPath=path,
            Operations=[
                {"Action": "AddModifier", "Attribute": "Health", "ModifierOp": "Add", "Magnitude": 10},
                {"Action": "SetModifier", "Index": 0, "Magnitude": 5},
                {"Action": "RemoveModifier", "Index": 0},
            ],
        )
    except MCPError as e:
        pytest.skip(f"GE modifier 跳过: {e}")
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"GE modifier 跳过: {e}")


def test_as_manage_set(test_ns, mcp):
    path = f"{test_ns}/AS_TestStats"
    mcp.call("CreateAssetAttributeSet", AssetPath=path)
    try:
        r = mcp.call(
            "ManageAssetAttributeSet",
            AssetPath=path,
            Operations=[{"Action": "Set", "AttributeName": "Health", "Value": "100"}],
        )
    except MCPError:
        pytest.skip("manage_asset_attribute_set set 不可用")
    assert isinstance(r, dict), r


# ── AttributeSet ─────────────────────────────────────────────────────────────


def test_as_create(test_ns, mcp):
    path = f"{test_ns}/AS_TestStats"
    r = mcp.call("CreateAssetAttributeSet", AssetPath=path)
    err = str(cap_first(r).get("Error") or "")
    if err and "already exists" not in err.lower() and "已存在" not in err:
        assert not cap_first(r).get("Error") and cap_first(r).get("bSuccess") is not False, f"create_asset_attribute_set 返回: {r!r}"


def test_as_get_empty(test_ns, mcp):
    """新建的 AS 不含 FGameplayAttributeData 属性时，attributes 为空数组而非 error。"""
    path = f"{test_ns}/AS_TestStats"
    r = mcp.call("GetAssetAttributeSet", AssetPath=path)
    assert isinstance(r, dict), r
    entry = cap_first(r)
    assert "Attributes" in entry, f"缺少 attributes 字段: {entry!r}"
    assert isinstance(entry["Attributes"], list), entry


def test_as_manage_reset_smoke(test_ns, mcp):
    """manage_asset_attribute_set reset：空 AS 无属性时 ops 可能失败，仅验通路。"""
    path = f"{test_ns}/AS_TestStats"
    try:
        r = mcp.call(
            "ManageAssetAttributeSet",
            AssetPath=path,
            Operations=[{"Action": "Reset", "AttributeName": "Health"}],
        )
    except MCPError:
        pytest.skip("manage_asset_attribute_set 不可用或未编译")
    assert isinstance(r, dict), r


# ── GameplayCueNotify ────────────────────────────────────────────────────────


def test_gc_notify_create_get(test_ns, mcp):
    if not is_capability_available(mcp, "CreateAssetGameplayCueNotify"):
        pytest.skip("create_asset_gameplay_cue_notify 未编入")
    path = f"{test_ns}/GCN_Created"
    r = mcp.call("CreateAssetGameplayCueNotify", AssetPath=path)
    entry = cap_first(r)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower():
        pytest.fail(f"create_asset_gameplay_cue_notify 失败: {entry}")
    got = cap_first(mcp.call("GetAssetGameplayCueNotify", AssetPath=path))
    assert not got.get("Error"), got
    man = cap_first(
        mcp.call(
            "ManageAssetGameplayCueNotify",
            AssetPath=path,
            Operations=[{"Action": "SetCueName", "CueName": "GameplayCue.Nx.Test"}],
        )
    )
    assert isinstance(man, dict), man
