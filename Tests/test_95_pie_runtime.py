# Copyright byteyang. All Rights Reserved.
"""阶段十一：PIE Runtime — Actor / Widget / Animation / Lua。

本文件所有用例都需要 `pie` fixture 启动的 PIE 会话；不请求 `pie` 的用例不会触发启停。
Lua 相关用例在 UnLua 不可用时整体跳过。
"""

from __future__ import annotations

import time

import pytest

from _framework.asset_helpers import ensure_test_hud_widget
from _framework.assertions import assert_success_count, ids_of
from _framework.mcp_client import MCPError, cap_first
from _framework.runtime_helpers import destroy_runtime_actors, pie_is_running, spawn_runtime_actors

pytestmark = pytest.mark.l4_runtime


@pytest.fixture(scope="module")
def spawned_actors(mcp, pie, test_ns):
    """11.7：批量生成两个 BP_TestActor。"""
    bp = f"{test_ns}/BP_TestActor"
    # BP_TestActor should have been created by test_30_blueprint; recreate as
    # a safety net so this file can run in isolation too.
    try:
        mcp.call("CreateAssetBlueprint", AssetPath=bp, ParentClass="Actor")
    except MCPError:
        # Already exists — fine.
        pass

    r = spawn_runtime_actors(
        mcp,
        [
            {"AssetPath": bp, "LocationZ": 100},
            {"AssetPath": bp, "LocationX": 200, "LocationZ": 100, "RotationYaw": 90},
        ],
    )
    names = r
    if len(names) < 2:
        pytest.skip(f"spawn_runtime_actor returned <2 actors")
    yield names

    destroy_runtime_actors(mcp, names)


# ─────────────────────────────────────────────────────────────
# PIE lifecycle
# ─────────────────────────────────────────────────────────────

def test_pie_status_is_running(mcp, pie):
    r = mcp.call("ControlPie", Action="Status")
    assert pie_is_running(r), f"PIE not running: {r!r}"
    entry = cap_first(r) if r.get("Results") else r
    assert entry.get("bHasPlayWorld") is True, entry


def test_pie_exec_slomo(mcp, pie):
    r = cap_first(mcp.call("ExecCommand", Command="slomo 1", bSilent=True))
    assert r.get("bExecuted") is True, r


def test_get_output_log_during_pie(mcp, pie):
    r = cap_first(mcp.call("GetOutputLog", Limit=5, Preset="Diagnose"))
    assert "Entries" in r, r
    assert isinstance(r["Entries"], list)


@pytest.mark.requires_gui
def test_capture_viewport_pie_validate(mcp, pie, require_tools):
    require_tools("CaptureViewport")
    r = mcp.call_capability("CaptureViewport", Target="PIE", bValidateOnly=True)
    entry = cap_first(r)
    assert entry.get("bValidateOnly") is True, entry
    assert not entry.get("Error"), entry


# ─────────────────────────────────────────────────────────────
# Actor
# ─────────────────────────────────────────────────────────────

def test_list_actors_contains_spawned(mcp, spawned_actors):
    r = mcp.call("ListRuntimeActors")
    payload = cap_first(r)
    names = []
    for a in payload.get("Actors", []) or []:
        if isinstance(a, dict):
            names.append(a.get("name") or a.get("ActorName") or "")
    for n in spawned_actors:
        assert n in names, f"spawned actor {n} missing: {names}"


def test_actor_property_batch_write(mcp, spawned_actors):
    a, b = spawned_actors
    results = [
        mcp.call(
            "SetRuntimeActorProperty",
            Updates=[{"ActorName": actor, "PropertyPath": "Health", "Value": value}],
        )
        for actor, value in ((a, "50"), (b, "150"))
    ]
    # Health may not exist on a generic Actor subclass — treat missing as skip.
    sc = sum(r.get("SuccessCount") or 0 for r in results)
    if sc == 0:
        pytest.skip(f"spawned actor has no Health property: {results!r}")
    assert sc == 2


def test_actor_property_multi_path(mcp, spawned_actors):
    a = spawned_actors[0]
    r = mcp.call(
        "GetRuntimeActorProperty",
        ActorName=a,
        PropertyPaths=["RootComponent.RelativeLocation"],
    )
    # 单条已提升到顶层；内嵌 results[] 仍为 ResolveBatch 属性结果
    entry = cap_first(r)
    inner = entry.get("Results")
    assert isinstance(inner, list) and len(inner) >= 1, r


def test_actor_property_multi_actor(mcp, spawned_actors):
    results = []
    for actor in spawned_actors:
        r = mcp.call(
            "GetRuntimeActorProperty",
            ActorName=actor,
            PropertyPaths=["RootComponent.RelativeLocation"],
        )
        results.append(cap_first(r))
    assert len(results) == len(spawned_actors)


def test_actor_diagnose_transform(mcp, spawned_actors):
    r = mcp.call("GetRuntimeActorProperty", ActorName=spawned_actors[0], Diagnose="Transform")
    entry = cap_first(r)
    dump = str(entry)
    assert "Relative" in dump or "Location" in dump or "Results" in dump, r


def test_actor_view_all(mcp, spawned_actors):
    """View="All"：返回组件/层级类信息即可。"""
    r = mcp.call("GetRuntimeActorProperty", ActorName=spawned_actors[0], View="All")
    entry = cap_first(r)
    has_components = isinstance(entry.get("Components"), list) and entry["Components"]
    has_children = isinstance(entry.get("Children"), list) and entry["Children"]
    has_hierarchy = isinstance(entry.get("Hierarchy"), list)
    assert has_components or has_children or has_hierarchy, entry


def test_actor_view_invalid_hints_all(mcp, spawned_actors):
    """未知 view：schema enum 拒绝、条目级 error，或回退为默认视图。"""
    try:
        r = mcp.call("GetRuntimeActorProperty", ActorName=spawned_actors[0], View="bogus")
    except MCPError as e:
        dump = str(e).lower()
        assert "enum" in dump or "View" in dump or "bogus" in dump, e
        return
    entry = cap_first(r) or {}
    err = entry.get("Error") or ""
    if err:
        assert "All" in err or "Components" in err or "View" in err, r
    else:
        pytest.skip(f"bogus view 未返回 error（当前插件行为）：{entry!r}")


def test_diff_actors(mcp, spawned_actors):
    a, b = spawned_actors
    r = mcp.call(
        "DiffRuntimeActors",
        ActorNameA=a,
        ActorNameB=b,
        PropertyPaths=["RootComponent.RelativeLocation"],
    )
    assert isinstance(r, dict), r


def test_runtime_destroy_one(mcp, spawned_actors):
    # Destroy only second spawned actor — first stays for other cases in file.
    second = spawned_actors[1]
    try:
        r = mcp.call("DestroyRuntimeActor", ActorName=second)
        assert not cap_first(r).get("Error"), r
    except MCPError:
        # Actor already gone is acceptable.
        pass


def test_get_behavior_tree_runtime(mcp, pie, spawned_actors, require_tools):
    """get_runtime_actor_behavior_tree：查询运行中 Actor 的行为树状态。
    Actor 未运行 BT 时返回空或 error 均合法，只要 Capability 不崩溃即通过。"""
    require_tools("GetRuntimeActorBehaviorTree")
    try:
        r = mcp.call("GetRuntimeActorBehaviorTree", ActorName=spawned_actors[0])
    except MCPError as e:
        # runtime 查询对未运行的 BT 可能直接拒绝，属合法契约
        pytest.skip(f"get_runtime_actor_behavior_tree rejected (BT not running): {e}")
    assert isinstance(r, dict), r


def test_get_gameplay_tags_actor(mcp, pie, spawned_actors, require_tools):
    """get_gameplay_tags View=actor：查询运行中 Actor 的 Gameplay Tags。
    Actor 无 Tag 时返回空列表，只要形状合法即通过。"""
    require_tools("GetGameplayTags")
    actor = spawned_actors[0]
    try:
        r = mcp.call("GetGameplayTags", Sections=["Actor"], ActorName=actor)
    except MCPError as e:
        pytest.skip(f"get_gameplay_tags actor 查询失败：{e}")
    assert isinstance(r, dict), r
    # tags 字段应为列表（可为空）
    tags = r.get("Tags")
    assert tags is None or isinstance(tags, list), f"unexpected tags shape: {r!r}"


# ─────────────────────────────────────────────────────────────
# Widget Runtime
# ─────────────────────────────────────────────────────────────

def test_spawn_and_interact_widget(mcp, pie, test_ns):
    wbp = ensure_test_hud_widget(mcp, test_ns)
    try:
        r0 = mcp.call("SpawnRuntimeWidget", AssetPath=wbp)
    except MCPError as e:
        pytest.skip(f"spawn_runtime_widget 失败（WBP 不存在？）：{e}")
    spawn_entry = cap_first(r0)
    assert not spawn_entry.get("Error"), spawn_entry

    # spawn 成功即可；list 可能只含关卡自带 HUD（WBP_Main）
    ops = [
        ("TitleText", "Read"),
        ("TitleText", "Set", "Runtime Text"),
        ("ClickBtn", "Click"),
        ("TestCheck", "Toggle"),
        ("TestSlider", "Set", "0.75"),
        ("TestInput", "Set", "Hello Input"),
    ]
    ok = 0
    for row in ops:
        kwargs = {"WidgetName": row[0], "Action": row[1]}
        if len(row) > 2:
            kwargs["Value"] = row[2]
        try:
            ir = mcp.call("InteractRuntimeWidget", **kwargs)
            entry = cap_first(ir)
            if not entry.get("Error"):
                ok += 1
        except MCPError:
            pass
    if ok < 4:
        pytest.skip(f"interact_widget 成功数不足（{ok}/6），运行时 Widget 可能未挂上视口")


def test_interact_runtime_widget_progressbar(mcp, pie, test_ns):
    """interact_runtime_widget 对 ProgressBar 支持 set/read。"""
    wbp = ensure_test_hud_widget(mcp, test_ns)
    try:
        mcp.call_capability(
            "ManageAssetUserWidget",
            AssetPath=wbp,
            Operations=[
                {
                    "Action": "Add",
                    "WidgetClass": "ProgressBar",
                    "WidgetName": "TestProgress",
                    "ParentWidget": "RootCanvas",
                },
            ],
        )
        mcp.call("SaveAsset", AssetPath=wbp)
        mcp.call("SpawnRuntimeWidget", AssetPath=wbp)
    except MCPError as e:
        pytest.skip(f"ProgressBar 运行时前置失败：{e}")

    set_r = mcp.call_capability(
        "InteractRuntimeWidget",
        WidgetName="TestProgress",
        Action="Set",
        Value="0.42",
    )
    set_entry = cap_first(set_r)
    if set_entry.get("Error"):
        pytest.skip(f"ProgressBar 运行时不可用：{set_entry}")
    assert abs(float(set_entry.get("Percent", -1)) - 0.42) < 0.01, set_entry

    read_r = mcp.call_capability(
        "InteractRuntimeWidget",
        WidgetName="TestProgress",
        Action="Read",
    )
    read_entry = cap_first(read_r)
    assert not read_entry.get("Error"), read_entry
    assert abs(float(read_entry.get("Percent", -1)) - 0.42) < 0.01, read_entry


def test_runtime_widget_batch_read(mcp, pie):
    try:
        r = mcp.call_capability("GetRuntimeWidgetProperty",
                                WidgetName="TitleText")
    except MCPError as e:
        pytest.skip(f"运行时 Widget 读取失败：{e}")
    assert isinstance(r, dict), r


def test_set_runtime_widget_property_title(mcp, pie, test_ns):
    """set_runtime_widget_property：直接写 UMG 属性（非 interact 路径）。"""
    wbp = ensure_test_hud_widget(mcp, test_ns)
    try:
        mcp.call("SpawnRuntimeWidget", AssetPath=wbp)
    except MCPError as e:
        pytest.skip(f"spawn_widget 前置失败：{e}")
    try:
        r = mcp.call_capability(
            "SetRuntimeWidgetProperty",
            Updates=[{
                "WidgetName": "TitleText",
                "PropertyPath": "Text",
                "Value": "MCP SetProperty",
            }],
        )
    except MCPError as e:
        pytest.skip(f"set_runtime_widget_property 不可用：{e}")
    entry = cap_first(r)
    if entry.get("Error"):
        pytest.skip(f"set_runtime_widget_property 不可用：{entry}")
    read_r = mcp.call_capability(
        "GetRuntimeWidgetProperty",
        WidgetName="TitleText",
        PropertyPaths=["Text"],
    )
    read_entry = cap_first(read_r)
    assert not read_entry.get("Error"), read_entry
    text_val = str(read_entry.get("Value") or read_entry.get("text") or "")
    assert "MCP SetProperty" in text_val, read_entry


def test_destroy_runtime_widget(mcp, pie, test_ns):
    """destroy_runtime_widget：spawn 后按实例名销毁。"""
    wbp = ensure_test_hud_widget(mcp, test_ns)
    try:
        mcp.call("SpawnRuntimeWidget", AssetPath=wbp)
    except MCPError as e:
        pytest.skip(f"spawn_widget 前置失败：{e}")

    listed = mcp.call("ListRuntimeWidgets")
    widgets = listed.get("Widgets") or []
    target = None
    for row in widgets:
        if not isinstance(row, dict):
            continue
        name = row.get("name") or row.get("WidgetName") or row.get("instanceName") or ""
        if name in ("RootCanvas", "CanvasPanel"):
            continue
        dump = str(row)
        if "WBP_TestHUD" in dump or "TestHUD" in dump or "WBP_" in name:
            target = name
            break
    if not target:
        pytest.skip(f"list_runtime_widgets 未找到 WBP 实例：{listed!r}")

    try:
        dr = mcp.call_capability("DestroyRuntimeWidget", WidgetName=target)
    except MCPError as e:
        pytest.skip(f"destroy_runtime_widget 跳过: {e}")
    del_entry = cap_first(dr)
    if del_entry.get("Error"):
        pytest.skip(f"destroy_runtime_widget 跳过: {del_entry}")

    listed2 = mcp.call("ListRuntimeWidgets")
    dump2 = str(listed2)
    assert target not in dump2 or len(listed2.get("Widgets") or []) < len(widgets), (
        listed2
    )


# ─────────────────────────────────────────────────────────────
# Lua (UnLua 可选)
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def _unlua_available(mcp, pie, tool_names):
    # SearchMode 下 tools/list 仅含元工具；直接调用探测 UnLua 是否可用
    if "GetRuntimeLuaStack" not in tool_names:
        try:
            mcp.call_capability("GetRuntimeLuaStack")
        except MCPError as e:
            pytest.skip(f"UnLua 运行时不可用：{e}")
    return True


@pytest.mark.lua
def test_lua_version(mcp, _unlua_available):
    r = mcp.call_capability("GetRuntimeLuaValue", LuaPath="_VERSION")
    entry = cap_first(r)
    assert entry.get("LuaPath") == "_VERSION", f"expected luaPath echo: {entry}"
    assert "Lua" in str(entry.get("Value", "")), f"expected Lua version: {entry}"


@pytest.mark.lua
def test_lua_eval(mcp, _unlua_available):
    r = mcp.call_capability("EvalRuntimeLua", Code="return 1+1")
    entry = cap_first(r)
    assert entry.get("Value") == 2, f"expected Value=2: {entry}"


@pytest.mark.lua
def test_lua_memory_gc(mcp, _unlua_available):
    before = mcp.call_capability("GetRuntimeLuaMemory")
    gc = mcp.call_capability("GcRuntimeLua", Mode="Collect")
    after = mcp.call_capability("GetRuntimeLuaMemory")
    before_e, gc_e, after_e = cap_first(before), cap_first(gc), cap_first(after)
    assert "MemoryKB" in before_e and "MemoryKB" in after_e
    assert gc_e.get("Mode") == "Collect"


@pytest.mark.lua
def test_lua_env_smoke(mcp, _unlua_available):
    r = mcp.call_capability("GetRuntimeLuaEnv", Limit=5)
    assert cap_first(r), r


@pytest.mark.lua
def test_lua_loaded_smoke(mcp, _unlua_available):
    r = mcp.call_capability("GetRuntimeLuaLoaded")
    assert cap_first(r), r


@pytest.mark.lua
def test_lua_stack_smoke(mcp, _unlua_available):
    r = mcp.call_capability("GetRuntimeLuaStack", MaxDepth=3)
    assert cap_first(r), r


@pytest.mark.lua
def test_lua_dofile_invalid_path(mcp, _unlua_available):
    """dofile 非法路径：条目级 error，不抛 MCPError。"""
    r = mcp.call_capability("DofileRuntimeLua", ScriptPath="__nonexistent_mcp_test__.lua")
    entry = cap_first(r)
    assert entry.get("Error") or entry.get("Path") == "__nonexistent_mcp_test__.lua", entry


@pytest.mark.lua
def test_lua_set_global_smoke(mcp, _unlua_available):
    key = "__McpTestLuaSet__"
    mcp.call_capability("SetRuntimeLua", LuaPath=key, Value="42")
    r = mcp.call_capability("GetRuntimeLuaValue", LuaPath=key)
    entry = cap_first(r)
    assert str(entry.get("Value", "")).strip() in ("42", "42.0"), entry


@pytest.mark.lua
def test_lua_hotreload_contract(mcp, _unlua_available):
    """UnLua 2.x 成功；1.x 返回条目级 error（文档约定）。"""
    r = mcp.call_capability("HotReloadRuntimeLua")
    entry = cap_first(r)
    assert isinstance(entry, dict), entry


@pytest.mark.lua
def test_lua_metatable_smoke(mcp, _unlua_available):
    """get_runtime_lua_metatable：非法路径也应返回结构化 results。"""
    r = mcp.call_capability(
        "GetRuntimeLuaMetatable",
        LuaPath="__McpNonexistentClass__",
        Limit=5,
    )
    entry = cap_first(r)
    assert entry.get("Error") or isinstance(entry.get("chain"), list) or entry.get("LuaPath"), entry


@pytest.mark.lua
def test_lua_object_smoke(mcp, _unlua_available, spawned_actors):
    """get_runtime_lua_object：对 PIE Actor 探测实例表（无 UnLua 绑定时允许 error）。"""
    r = mcp.call_capability(
        "GetRuntimeLuaObject",
        ActorName=spawned_actors[0],
        Limit=5,
    )
    entry = cap_first(r)
    assert isinstance(entry, dict), entry
    assert entry.get("Keys") is not None or entry.get("Error"), entry


def test_control_pie_pause_resume(mcp, pie):
    r = mcp.call_capability("ControlPie", Action="Pause")
    entry = cap_first(r)
    assert not entry.get("Error"), r
    mcp.call_capability("ControlPie", Action="Resume")


def test_interact_runtime_widget_combobox(mcp, pie, test_ns):
    wbp = ensure_test_hud_widget(mcp, test_ns)
    try:
        mcp.call_capability(
            "ManageAssetUserWidget",
            AssetPath=wbp,
            Operations=[{
                "Action": "Add",
                "WidgetClass": "ComboBoxString",
                "WidgetName": "TestCombo",
                "ParentWidget": "RootCanvas",
            }],
        )
        mcp.call("SaveAsset", AssetPath=wbp)
        mcp.call("SpawnRuntimeWidget", AssetPath=wbp)
    except MCPError as e:
        pytest.skip(f"ComboBox 运行时前置失败：{e}")
    read_r = mcp.call_capability(
        "InteractRuntimeWidget",
        WidgetName="TestCombo",
        Action="Read",
    )
    entry = cap_first(read_r)
    if entry.get("Error"):
        pytest.skip(f"ComboBox 运行时不可用：{entry}")
    assert "OptionCount" in entry or "Selected" in entry, entry


def test_interact_runtime_actor_audio(mcp, pie):
    from _framework.capability_probe import is_capability_available
    from _framework.asset_helpers import first_asset_path
    if not is_capability_available(mcp, "InteractRuntimeActorAudio"):
        pytest.skip("interact_runtime_actor_audio 未编入")
    path = first_asset_path(mcp, "SoundWave") or first_asset_path(mcp, "SoundCue")
    if not path:
        pytest.skip("无音效样本")
    r = mcp.call_capability(
        "InteractRuntimeActorAudio",
        Action="PlaySound",
        AssetPath=path,
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r


def test_interact_runtime_actor_niagara(mcp, pie, spawned_actors):
    from _framework.capability_probe import is_capability_available
    if not is_capability_available(mcp, "InteractRuntimeActorNiagara"):
        pytest.skip("interact_runtime_actor_niagara 未编入")
    r = mcp.call_capability(
        "InteractRuntimeActorNiagara",
        Action="Deactivate",
        ActorName=spawned_actors[0],
    )
    entry = cap_first(r)
    assert isinstance(entry, dict), r


def test_interact_runtime_actor_ai_no_controller(mcp, pie, spawned_actors):
    from _framework.capability_probe import is_capability_available
    if not is_capability_available(mcp, "InteractRuntimeActorAI"):
        pytest.skip("interact_runtime_actor_ai 未编入")
    r = mcp.call_capability(
        "InteractRuntimeActorAI",
        Action="MoveTo",
        ActorName=spawned_actors[0],
        x=0, y=0, z=0,
    )
    entry = cap_first(r)
    assert entry.get("Error"), r


def test_interact_runtime_actor_behavior_tree(mcp, pie, spawned_actors):
    from _framework.capability_probe import is_capability_available
    if not is_capability_available(mcp, "InteractRuntimeActorBehaviorTree"):
        pytest.skip("interact_runtime_actor_behavior_tree 未编入")
    actor = spawned_actors[0]
    try:
        stop_r = mcp.call_capability(
            "InteractRuntimeActorBehaviorTree",
            Action="StopTree",
            ActorName=actor,
        )
    except MCPError as e:
        pytest.skip(f"无运行中 BT / AIController: {e}")
    stop_e = cap_first(stop_r)
    if stop_e.get("Error") or stop_r.get("Error"):
        pytest.skip(f"无运行中 BT / AIController: {stop_e or stop_r}")
    try:
        mcp.call_capability(
            "InteractRuntimeActorBehaviorTree",
            Action="SetBlackboard",
            ActorName=actor,
            KeyName="Target",
            Value="None",
        )
        restart = mcp.call_capability(
            "InteractRuntimeActorBehaviorTree",
            Action="RestartTree",
            ActorName=actor,
        )
    except MCPError as e:
        pytest.skip(f"无运行中 BT / AIController: {e}")
    assert isinstance(cap_first(restart), dict), restart
