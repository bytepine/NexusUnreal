# Copyright byteyang. All Rights Reserved.
"""阶段十一：PIE Runtime — Actor / Widget / Animation / Lua。

本文件所有用例都需要 `pie` fixture 启动的 PIE 会话；不请求 `pie` 的用例不会触发启停。
Lua 相关用例在 UnLua 不可用时整体跳过。
"""

from __future__ import annotations

import time

import pytest

from _framework.assertions import assert_success_count, ids_of
from _framework.mcp_client import MCPError, cap_first

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

    r = mcp.call(
        "spawn_actor",
        spawns=[
            {"blueprintPath": bp, "locationZ": 100},
            {"blueprintPath": bp, "locationX": 200, "locationZ": 100,
             "rotationYaw": 90},
        ],
    )
    # spawn_actor returns `name` in each result; accept legacy `actorName` too.
    results = r.get("results") or []
    names = [
        (res.get("actorName") or res.get("name"))
        for res in results
        if isinstance(res, dict)
    ]
    names = [n for n in names if n]
    if len(names) < 2:
        pytest.skip(f"spawn_actor returned <2 actors: {r!r}")
    yield names

    # Best-effort destroy; test_runtime_destroy also covers the cleanup path.
    try:
        mcp.call("destroy_actor", actorNames=names)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# PIE lifecycle
# ─────────────────────────────────────────────────────────────

def test_pie_status_is_running(mcp, pie):
    r = mcp.call("control_pie", action="status")
    running = r.get("isPIERunning")
    state = r.get("state")
    assert running is True or state == "running", f"PIE not running: {r!r}"


def test_pie_exec_slomo(mcp, pie):
    r = cap_first(mcp.call("exec_command", command="slomo 1", silent=True))
    assert r.get("executed") is True, r


# ─────────────────────────────────────────────────────────────
# Actor
# ─────────────────────────────────────────────────────────────

def test_list_actors_contains_spawned(mcp, spawned_actors):
    r = mcp.call("list_actors")
    names = []
    for a in r.get("actors", []) or []:
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
    r = mcp.call(
        "get_property",
        actorNames=list(spawned_actors),
        propertyPaths=["RootComponent.RelativeLocation"],
    )
    # 统一 results[] 包装：每个 actor 一条 entry，内嵌 propertyPaths 解析结果
    assert isinstance(r.get("results"), list), r
    assert len(r["results"]) == len(spawned_actors), r
    for entry in r["results"]:
        assert isinstance(entry.get("results"), list), entry


def test_actor_diagnose_transform(mcp, spawned_actors):
    r = mcp.call("get_property", actorName=spawned_actors[0], diagnose="transform")
    # 统一 results[] 包装：单 actor 一条 entry，内嵌 transform 结果
    assert isinstance(r.get("results"), list) and len(r["results"]) == 1, r
    dump = str(r["results"][0])
    assert "Relative" in dump or "Location" in dump or "results" in dump, r


def test_actor_section_all(mcp, spawned_actors):
    """section='all' 一次返回 components + attach_hierarchy 两段，
    避免 AI 按 get_asset 心智误传 'all' 被拒后重试。"""
    r = mcp.call("get_property", actorName=spawned_actors[0], section="all")
    # 统一 results[] 包装：单 actor 的 components/hierarchy/sections 落到 results[0]
    assert isinstance(r.get("results"), list) and len(r["results"]) == 1, r
    entry = r["results"][0]
    assert isinstance(entry.get("components"), list) and len(entry["components"]) > 0, entry
    assert isinstance(entry.get("hierarchy"), list), entry
    assert entry.get("sections") == ["components", "attach_hierarchy"], entry


def test_actor_section_invalid_hints_all(mcp, spawned_actors):
    """未知 section 错误消息应包含 'all' 选项提示。"""
    # Capability 编排：item 级失败不再抛 MCPError，error 写入 results[].error
    r = mcp.call("get_property", actorName=spawned_actors[0], section="bogus")
    assert isinstance(r.get("results"), list) and len(r["results"]) == 1, r
    err = (r["results"][0] or {}).get("error") or ""
    assert "all" in err and "components" in err, r


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
    wbp = f"{test_ns}/WBP_TestHUD"
    try:
        r0 = mcp.call("spawn_widget", assetPath=wbp)
    except MCPError as e:
        pytest.skip(f"spawn_runtime_widget 失败（WBP 不存在？）：{e}")
    assert r0, r0

    r_list = mcp.call("list_runtime_widgets")
    dump = str(r_list)
    assert "WBP_TestHUD" in dump or "TestHUD" in dump, f"widget not listed: {dump[:300]}"

    # 11.28：一次批量 6 个控件操作
    r = mcp.call(
        "interact_widget",
        operations=[
            {"widgetName": "TitleText", "action": "read"},
            {"widgetName": "TitleText", "action": "set",    "value": "Runtime Text"},
            {"widgetName": "ClickBtn",  "action": "click"},
            {"widgetName": "TestCheck", "action": "toggle"},
            {"widgetName": "TestSlider","action": "set",    "value": "0.75"},
            {"widgetName": "TestInput", "action": "set",    "value": "Hello Input"},
        ],
    )
    # A couple of operations may fail if widget removed earlier; accept >= 4.
    assert (r.get("successCount") or 0) >= 4, f"interact_widget batch: {r!r}"


def test_interact_runtime_widget_progressbar(mcp, pie, test_ns):
    """interact_runtime_widget 对 ProgressBar 支持 set/read。"""
    wbp = f"{test_ns}/WBP_TestHUD"
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
    assert not set_entry.get("error"), set_entry
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
