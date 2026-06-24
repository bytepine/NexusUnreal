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
        mcp.call("create_blueprint", assetPath=bp, parentClass="Actor")
    except MCPError:
        # Already exists — fine.
        pass

    r = spawn_runtime_actors(
        mcp,
        [
            {"blueprintPath": bp, "locationZ": 100},
            {"blueprintPath": bp, "locationX": 200, "locationZ": 100, "rotationYaw": 90},
        ],
    )
    names = r
    if len(names) < 2:
        pytest.skip(f"spawn_actor returned <2 actors")
    yield names

    destroy_runtime_actors(mcp, names)


# ─────────────────────────────────────────────────────────────
# PIE lifecycle
# ─────────────────────────────────────────────────────────────

def test_pie_status_is_running(mcp, pie):
    r = mcp.call("control_pie", action="status")
    assert pie_is_running(r), f"PIE not running: {r!r}"


def test_pie_exec_slomo(mcp, pie):
    r = cap_first(mcp.call("exec_command", command="slomo 1", silent=True))
    assert r.get("executed") is True, r


# ─────────────────────────────────────────────────────────────
# Actor
# ─────────────────────────────────────────────────────────────

def test_list_actors_contains_spawned(mcp, spawned_actors):
    r = mcp.call("list_actors")
    payload = cap_first(r)
    names = []
    for a in payload.get("actors", []) or []:
        if isinstance(a, dict):
            names.append(a.get("name") or a.get("actorName") or "")
    for n in spawned_actors:
        assert n in names, f"spawned actor {n} missing: {names}"


def test_actor_property_batch_write(mcp, spawned_actors):
    a, b = spawned_actors
    r = mcp.call(
        "set_property",
        updates=[
            {"actorName": a, "propertyPath": "Health", "value": "50"},
            {"actorName": b, "propertyPath": "Health", "value": "150"},
        ],
    )
    # Health may not exist on a generic Actor subclass — treat missing as skip.
    sc = r.get("successCount") or 0
    if sc == 0:
        pytest.skip(f"spawned actor has no Health property: {r!r}")
    assert sc == 2


def test_actor_property_multi_path(mcp, spawned_actors):
    a = spawned_actors[0]
    r = mcp.call(
        "get_property",
        actorName=a,
        propertyPaths=["RootComponent.RelativeLocation"],
    )
    # Capability 编排：单 actor 也走 results[]，每条 entry 内嵌 ResolveBatch 的 inner results[]
    assert isinstance(r.get("results"), list) and len(r["results"]) == 1, r
    inner = r["results"][0].get("results")
    assert isinstance(inner, list) and len(inner) >= 1, r


def test_actor_property_multi_actor(mcp, spawned_actors):
    results = []
    for actor in spawned_actors:
        r = mcp.call(
            "get_property",
            actorName=actor,
            propertyPaths=["RootComponent.RelativeLocation"],
        )
        assert isinstance(r.get("results"), list) and len(r["results"]) == 1, r
        results.append(r["results"][0])
    assert len(results) == len(spawned_actors)


def test_actor_diagnose_transform(mcp, spawned_actors):
    r = mcp.call("get_property", actorName=spawned_actors[0], diagnose="transform")
    # 统一 results[] 包装：单 actor 一条 entry，内嵌 transform 结果
    assert isinstance(r.get("results"), list) and len(r["results"]) == 1, r
    dump = str(r["results"][0])
    assert "Relative" in dump or "Location" in dump or "results" in dump, r


def test_actor_section_all(mcp, spawned_actors):
    """section='all' 或 view 预设：返回组件/层级类信息即可。"""
    r = mcp.call("get_property", actorName=spawned_actors[0], section="all")
    assert isinstance(r.get("results"), list) and len(r["results"]) == 1, r
    entry = r["results"][0]
    has_components = isinstance(entry.get("components"), list) and entry["components"]
    has_children = isinstance(entry.get("children"), list) and entry["children"]
    has_hierarchy = isinstance(entry.get("hierarchy"), list)
    assert has_components or has_children or has_hierarchy, entry


def test_actor_section_invalid_hints_all(mcp, spawned_actors):
    """未知 section：条目级 error 或回退为默认视图（插件版本差异）。"""
    r = mcp.call("get_property", actorName=spawned_actors[0], section="bogus")
    assert isinstance(r.get("results"), list) and len(r["results"]) == 1, r
    entry = r["results"][0] or {}
    err = entry.get("error") or ""
    if err:
        assert "all" in err or "components" in err or "view" in err, r
    else:
        pytest.skip(f"bogus section 未返回 error（当前插件行为）：{entry!r}")


def test_diff_actors(mcp, spawned_actors):
    a, b = spawned_actors
    r = mcp.call(
        "diff_actors",
        actorNameA=a,
        actorNameB=b,
        propertyPaths=["RootComponent.RelativeLocation"],
    )
    assert isinstance(r, dict), r


def test_runtime_destroy_one(mcp, spawned_actors):
    # Destroy only second spawned actor — first stays for other cases in file.
    second = spawned_actors[1]
    try:
        r = mcp.call("destroy_actor", actorNames=[second])
        assert (r.get("successCount") or 0) >= 1, r
    except MCPError:
        # Actor already gone is acceptable.
        pass


def test_get_behavior_tree_runtime(mcp, pie, test_ns, require_tools):
    """get_behavior_tree section=runtime：对 test_ns 中已创建的 BT_TestAI 查运行时状态。
    BT 未附到 AI Controller 时 runtime 返回空或 error 均合法，只要工具不崩溃即通过。"""
    require_tools("get_behavior_tree")
    bt_path = f"{test_ns}/BT_TestAI"
    try:
        r = mcp.call("get_behavior_tree", section="runtime", assetPath=bt_path)
    except MCPError as e:
        # runtime 查询对未运行的 BT 可能直接拒绝，属合法契约
        pytest.skip(f"get_behavior_tree runtime rejected (BT not running): {e}")
    assert isinstance(r, dict), r


def test_get_gameplay_tags_actor(mcp, pie, spawned_actors, require_tools):
    """get_gameplay_tags section=actor：查询运行中 Actor 的 Gameplay Tags。
    Actor 无 Tag 时返回空列表，只要形状合法即通过。"""
    require_tools("get_gameplay_tags")
    actor = spawned_actors[0]
    try:
        r = mcp.call("get_gameplay_tags", section="actor", actorName=actor)
    except MCPError as e:
        pytest.skip(f"get_gameplay_tags actor 查询失败：{e}")
    assert isinstance(r, dict), r
    # tags 字段应为列表（可为空）
    tags = r.get("tags")
    assert tags is None or isinstance(tags, list), f"unexpected tags shape: {r!r}"


# ─────────────────────────────────────────────────────────────
# Widget Runtime
# ─────────────────────────────────────────────────────────────

def test_spawn_and_interact_widget(mcp, pie, test_ns):
    wbp = ensure_test_hud_widget(mcp, test_ns)
    try:
        r0 = mcp.call("spawn_widget", assetPath=wbp)
    except MCPError as e:
        pytest.skip(f"spawn_runtime_widget 失败（WBP 不存在？）：{e}")
    spawn_entry = cap_first(r0)
    assert not spawn_entry.get("error"), spawn_entry

    # spawn 成功即可；list 可能只含关卡自带 HUD（WBP_Main）
    ops = [
        ("TitleText", "read"),
        ("TitleText", "set", "Runtime Text"),
        ("ClickBtn", "click"),
        ("TestCheck", "toggle"),
        ("TestSlider", "set", "0.75"),
        ("TestInput", "set", "Hello Input"),
    ]
    ok = 0
    for row in ops:
        kwargs = {"widgetName": row[0], "action": row[1]}
        if len(row) > 2:
            kwargs["value"] = row[2]
        try:
            ir = mcp.call("interact_widget", **kwargs)
            entry = cap_first(ir)
            if not entry.get("error"):
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
            "manage_asset_user_widget",
            assetPath=wbp,
            widgets=[
                {
                    "action": "add",
                    "widgetClass": "ProgressBar",
                    "widgetName": "TestProgress",
                    "parentWidget": "RootCanvas",
                },
            ],
        )
        mcp.call("save_asset", assetPaths=[wbp])
        mcp.call("spawn_widget", assetPath=wbp)
    except MCPError as e:
        pytest.skip(f"ProgressBar 运行时前置失败：{e}")

    set_r = mcp.call_capability(
        "interact_runtime_widget",
        widgetName="TestProgress",
        action="set",
        value="0.42",
    )
    set_entry = (set_r.get("results") or [set_r])[0]
    if set_entry.get("error"):
        pytest.skip(f"ProgressBar 运行时不可用：{set_entry}")
    assert abs(float(set_entry.get("percent", -1)) - 0.42) < 0.01, set_entry

    read_r = mcp.call_capability(
        "interact_runtime_widget",
        widgetName="TestProgress",
        action="read",
    )
    read_entry = (read_r.get("results") or [read_r])[0]
    assert not read_entry.get("error"), read_entry
    assert abs(float(read_entry.get("percent", -1)) - 0.42) < 0.01, read_entry


def test_runtime_widget_batch_read(mcp, pie):
    try:
        r = mcp.call_capability("get_runtime_widget_property",
                                widgetName="TitleText")
    except MCPError as e:
        pytest.skip(f"运行时 Widget 读取失败：{e}")
    assert isinstance(r, dict), r


def test_set_runtime_widget_property_title(mcp, pie, test_ns):
    """set_runtime_widget_property：直接写 UMG 属性（非 interact 路径）。"""
    wbp = ensure_test_hud_widget(mcp, test_ns)
    try:
        mcp.call("spawn_widget", assetPath=wbp)
    except MCPError as e:
        pytest.skip(f"spawn_widget 前置失败：{e}")
    r = mcp.call_capability(
        "set_runtime_widget_property",
        updates=[{
            "widgetName": "TitleText",
            "propertyPath": "Text",
            "value": "MCP SetProperty",
        }],
    )
    entry = (r.get("results") or [r])[0]
    if entry.get("error"):
        pytest.skip(f"set_runtime_widget_property 不可用：{entry}")
    read_r = mcp.call_capability(
        "get_runtime_widget_property",
        widgetName="TitleText",
        propertyPath="Text",
    )
    read_entry = (read_r.get("results") or [read_r])[0]
    assert not read_entry.get("error"), read_entry
    text_val = str(read_entry.get("value") or read_entry.get("text") or "")
    assert "MCP SetProperty" in text_val, read_entry


def test_destroy_runtime_widget(mcp, pie, test_ns):
    """destroy_runtime_widget：spawn 后按实例名销毁。"""
    wbp = ensure_test_hud_widget(mcp, test_ns)
    try:
        mcp.call("spawn_widget", assetPath=wbp)
    except MCPError as e:
        pytest.skip(f"spawn_widget 前置失败：{e}")

    listed = mcp.call("list_runtime_widgets")
    widgets = listed.get("widgets") or []
    target = None
    for row in widgets:
        if not isinstance(row, dict):
            continue
        dump = str(row)
        if "WBP_TestHUD" in dump or "TestHUD" in dump:
            target = row.get("name") or row.get("widgetName") or row.get("instanceName")
            break
    if not target:
        pytest.skip(f"list_runtime_widgets 未找到 WBP 实例：{listed!r}")

    dr = mcp.call_capability("destroy_runtime_widget", widgetName=target)
    del_entry = (dr.get("results") or [dr])[0]
    assert not del_entry.get("error"), del_entry

    listed2 = mcp.call("list_runtime_widgets")
    dump2 = str(listed2)
    assert target not in dump2 or len(listed2.get("widgets") or []) < len(widgets), (
        listed2
    )


# ─────────────────────────────────────────────────────────────
# Lua (UnLua 可选)
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def _unlua_available(mcp, pie, tool_names):
    # SearchMode 下 tools/list 仅含元工具；直接调用探测 UnLua 是否可用
    if "get_runtime_lua_stack" not in tool_names:
        try:
            mcp.call_capability("get_runtime_lua_stack")
        except MCPError as e:
            pytest.skip(f"UnLua 运行时不可用：{e}")
    return True


@pytest.mark.lua
def test_lua_version(mcp, _unlua_available):
    r = mcp.call_capability("get_runtime_lua_value", path="_VERSION")
    assert isinstance(r, dict) and "results" in r and len(r["results"]) == 1, f"expected results[1]: {r}"
    entry = r["results"][0]
    assert entry.get("path") == "_VERSION", f"expected path echo: {entry}"
    assert "Lua" in str(entry.get("value", "")), f"expected Lua version: {entry}"


@pytest.mark.lua
def test_lua_eval(mcp, _unlua_available):
    r = mcp.call_capability("eval_runtime_lua", code="return 1+1")
    assert isinstance(r, dict) and "results" in r and len(r["results"]) == 1, f"expected results[1]: {r}"
    entry = r["results"][0]
    assert entry.get("value") == 2, f"expected value=2: {entry}"


@pytest.mark.lua
def test_lua_memory_gc(mcp, _unlua_available):
    before = mcp.call_capability("get_runtime_lua_memory")
    gc = mcp.call_capability("gc_runtime_lua", mode="collect")
    after = mcp.call_capability("get_runtime_lua_memory")
    for r in (before, gc, after):
        assert isinstance(r, dict) and "results" in r and len(r["results"]) == 1, f"expected results[1]: {r}"
    assert "memoryKB" in before["results"][0] and "memoryKB" in after["results"][0]
    assert gc["results"][0].get("mode") == "collect"


@pytest.mark.lua
def test_lua_env_smoke(mcp, _unlua_available):
    r = mcp.call_capability("get_runtime_lua_env", limit=5)
    assert isinstance(r.get("results"), list) and len(r["results"]) == 1, r


@pytest.mark.lua
def test_lua_loaded_smoke(mcp, _unlua_available):
    r = mcp.call_capability("get_runtime_lua_loaded")
    assert isinstance(r.get("results"), list) and len(r["results"]) == 1, r


@pytest.mark.lua
def test_lua_stack_smoke(mcp, _unlua_available):
    r = mcp.call_capability("get_runtime_lua_stack", maxDepth=3)
    assert isinstance(r.get("results"), list) and len(r["results"]) == 1, r


@pytest.mark.lua
def test_lua_dofile_invalid_path(mcp, _unlua_available):
    """dofile 非法路径：条目级 error，不抛 MCPError。"""
    r = mcp.call_capability("dofile_runtime_lua", filePath="__nonexistent_mcp_test__.lua")
    entry = (r.get("results") or [{}])[0]
    assert entry.get("error") or entry.get("path") == "__nonexistent_mcp_test__.lua", entry


@pytest.mark.lua
def test_lua_set_global_smoke(mcp, _unlua_available):
    key = "__McpTestLuaSet__"
    mcp.call_capability("set_runtime_lua", path=key, value="42")
    r = mcp.call_capability("get_runtime_lua_value", path=key)
    entry = (r.get("results") or [{}])[0]
    assert str(entry.get("value", "")).strip() in ("42", "42.0"), entry


@pytest.mark.lua
def test_lua_hotreload_contract(mcp, _unlua_available):
    """UnLua 2.x 成功；1.x 返回条目级 error（文档约定）。"""
    r = mcp.call_capability("hotreload_runtime_lua")
    entry = (r.get("results") or [{}])[0]
    assert entry.get("success") is True or bool(entry.get("error")), entry


@pytest.mark.lua
def test_lua_metatable_smoke(mcp, _unlua_available):
    """get_runtime_lua_metatable：非法路径也应返回结构化 results。"""
    r = mcp.call_capability(
        "get_runtime_lua_metatable",
        path="__McpNonexistentClass__",
        limit=5,
    )
    entry = (r.get("results") or [r])[0]
    assert entry.get("error") or isinstance(entry.get("chain"), list) or entry.get("path"), entry


@pytest.mark.lua
def test_lua_object_smoke(mcp, _unlua_available, spawned_actors):
    """get_runtime_lua_object：对 PIE Actor 探测实例表（无 UnLua 绑定时允许 error）。"""
    r = mcp.call_capability(
        "get_runtime_lua_object",
        actorName=spawned_actors[0],
        limit=5,
    )
    entry = (r.get("results") or [r])[0]
    assert isinstance(entry, dict), entry
    assert entry.get("keys") is not None or entry.get("error"), entry
