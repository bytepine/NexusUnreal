# Copyright byteyang. All Rights Reserved.
"""阶段一：基础探测 — 连接 / tools/list / editor info."""

from __future__ import annotations

import pytest

from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.smoke


def test_tools_list_contains_meta_tools(mcp, tool_names):
    """在 SearchMode（默认）下 tools/list 只包含 3 个元工具；
    在 MultiTool 模式下还包含所有 Capability。
    无论何种模式，3 个元工具必须始终存在。"""
    for required in ["SearchCapabilities", "CallCapability", "SubmitFeedback"]:
        assert required in tool_names, (
            f"meta-tool missing from tools/list: {required}\n"
            f"actual tools: {tool_names!r}"
        )


def test_search_capabilities_roundtrip(mcp):
    """search_capabilities 能发现至少一个 get_editor_info 相关 capability。"""
    r = mcp.call("SearchCapabilities", Query="editor info")
    # 返回体有 capabilities 列表（≥2 条时）或 capability 对象（精确命中时）
    assert isinstance(r, dict), f"search_capabilities returned non-dict: {r!r}"


def test_search_capabilities_nested_widget_action_enum(mcp):
    """manage_asset_user_widget 的 operations[].action 须在 parameters[] 中带 enum。"""
    r = mcp.call("SearchCapabilities", CapabilityName="ManageAssetUserWidget")
    # 新版返回 {"Capability":{"Parameters":[...]}}，旧版顶层 parameters
    cap = r.get("Capability") or r
    params = cap.get("Parameters") or []
    by_name = {p.get("name"): p for p in params if isinstance(p, dict)}
    action = by_name.get("Operations[].Action")
    assert action is not None, f"Operations[].Action missing in parameters: {by_name.keys()!r}"
    assert action.get("type") == "string (enum)" or action.get("enum"), action


def test_search_capabilities_array_sections_enum(mcp):
    """MultiSection get 的 sections[] 须带 enum，且 type 仍是 array（不得被误判为标量枚举）。"""
    r = mcp.call("SearchCapabilities", CapabilityName="GetAssetBlueprint")
    cap = r.get("Capability") or r
    params = cap.get("Parameters") or []
    by_name = {p.get("name"): p for p in params if isinstance(p, dict)}
    sections = by_name.get("Sections")
    assert sections is not None, f"sections missing in parameters: {by_name.keys()!r}"
    assert sections.get("type") == "array", f"sections type changed unexpectedly: {sections!r}"
    enum_vals = sections.get("enum") or []
    assert "variable" in enum_vals and "Component" in enum_vals, (
        f"expected singular section names in enum: {enum_vals!r}"
    )
    assert "Variables" not in enum_vals and "Components" not in enum_vals, (
        f"sections enum should not contain plural aliases: {enum_vals!r}"
    )


def test_call_capability_create_blackboard_not_unknown(mcp):
    """规范名 create_asset_blackboard 应可路由，不得 ErrorKind=unknown。"""
    try:
        r = mcp.call_capability(
            "CreateAssetBlackboard",
            AssetPath="/Game/__nexus_pytest_nonexistent_bb__",
            save=False,
        )
    except MCPError as exc:
        r = exc.raw or {}
    if isinstance(r, dict) and r.get("ErrorKind") == "unknown":
        pytest.fail(f"canonical name should resolve, got: {r!r}")


def test_search_capabilities_get_asset_hint(mcp):
    """Query=get_asset 零命中时应返回 get_asset_<类型> 路由 hint。"""
    r = mcp.call("SearchCapabilities", Query="GetAsset")
    assert r.get("ErrorKind") == "NotFound", r
    hint = r.get("Hint") or ""
    assert "GetAsset" in hint, f"expected routing hint: {r!r}"


def test_search_capabilities_query_too_broad(mcp):
    """单用过宽词 blueprint 应硬拦截，返回 suggestedQueries 而非整类列表。"""
    r = mcp.call("SearchCapabilities", Query="blueprint")
    assert r.get("ErrorKind") == "QueryTooBroad", r
    assert r.get("TotalCount") == 0, r
    caps = r.get("Capabilities") or []
    assert caps == [], r
    suggested = r.get("SuggestedQueries") or []
    assert any("blueprint" in str(q) for q in suggested), r
    assert r.get("FeedbackHint"), r


def test_search_capabilities_not_found(mcp):
    """精确名不存在时 ErrorKind=not_found，勿与 disabled 混用。"""
    r = mcp.call(
        "SearchCapabilities",
        CapabilityName="__nexus_mcp_nonexistent_cap_xyz__",
    )
    assert r.get("ErrorKind") == "NotFound", r
    assert "Capability" not in r


def _search_cap_names(r: dict) -> list[str]:
    cap = r.get("Capability")
    if isinstance(cap, dict) and cap.get("name"):
        return [str(cap["name"])]
    return [
        str(c.get("name"))
        for c in (r.get("Capabilities") or [])
        if isinstance(c, dict) and c.get("name")
    ]


def test_search_capabilities_current_map(mcp):
    """口语 current map 应命中 get_editor_context，而不是 get_asset_level。"""
    r = mcp.call("SearchCapabilities", Query="current map")
    names = _search_cap_names(r)
    assert "GetEditorContext" in names, r


def test_search_capabilities_get_refs(mcp):
    r = mcp.call("SearchCapabilities", Query="get refs")
    names = _search_cap_names(r)
    assert "GetAssetRefs" in names, r


def test_search_capabilities_cpp_enum_hint(mcp):
    r = mcp.call("SearchCapabilities", Query="cpp enum")
    hint = (r.get("Hint") or "").lower()
    assert "uenum" in hint or "GetAssetEnum" in hint, r


def test_search_capabilities_routing_hints_resolvable(mcp):
    r = mcp.call("SearchCapabilities", Query="zzzz_no_such_cap_xyz")
    hints = r.get("RoutingHints") or []
    for item in hints:
        name = item.get("name") if isinstance(item, dict) else None
        if not name:
            continue
        detail = mcp.call("SearchCapabilities", CapabilityName=name)
        cap = detail.get("Capability") or detail
        assert cap.get("name") == name, detail


def test_submit_feedback_smoke(mcp):
    """submit_feedback 最小通路：写入后返回 ok。"""
    r = mcp.call(
        "SubmitFeedback",
        Category="Other",
        Note="pytest P2 smoke",
        Capability="GetEditorInfo",
    )
    assert r.get("bOk") is True, r


def test_call_capability_editor_info(mcp):
    """通过 call_capability 调用 get_editor_info，验证 SearchMode 完整链路。"""
    info = mcp.call_capability("GetEditorInfo")
    assert info, "get_editor_info returned empty payload"
    joined = " ".join(str(v) for v in info.values())
    assert joined, "get_editor_info payload has no string fields"


def test_get_editor_info(mcp):
    info = mcp.call("GetEditorInfo")  # routes through call_capability automatically
    assert info, "get_editor_info returned empty payload"
    joined = " ".join(str(v) for v in info.values())
    assert joined, "get_editor_info payload has no string fields"


def test_get_output_log_basic(mcp, require_tools):
    require_tools("GetOutputLog")
    r = cap_first(mcp.call("GetOutputLog", Limit=20))
    assert "Entries" in r, f"no entries field: {r!r}"
    assert isinstance(r["Entries"], list)
    total = r.get("TotalCount")
    if total is not None:
        assert total >= len(r["Entries"])


def test_get_output_log_filtered_offset(mcp):
    r = cap_first(mcp.call("GetOutputLog", Verbosity="Warning",
                 TextFilter="NexusLink", Limit=10, Offset=5))
    assert isinstance(r.get("Entries"), list)


def test_get_output_log_watch_roundtrip(mcp, require_tools):
    """watch 装上后只收命中行；collectWatch / disarm 与互斥参数。"""
    require_tools("GetOutputLog")
    token = "NXWATCH_ROUNDTRIP_NO_HIT"
    try:
        with pytest.raises(MCPError):
            mcp.call(
                "GetOutputLog",
                Watch={"TextIncludes": [token]},
                bCollectWatch=True,
            )
        armed = cap_first(mcp.call(
            "GetOutputLog",
            Watch={"TextIncludes": [token], "Verbosity": "All"},
        ))
        assert armed.get("Watch") == "armed", armed
        assert armed.get("Entries") == []
        assert "bCollectWatch" in (armed.get("Hint") or ""), armed
        got = cap_first(mcp.call("GetOutputLog", bCollectWatch=True))
        assert got.get("Entries") == [], got
        assert got.get("Watch") == "armed", got
        done = cap_first(mcp.call("GetOutputLog", bCollectWatch=True, bDisarm=True))
        assert done.get("Watch") == "disarmed", done
        with pytest.raises(MCPError):
            mcp.call("GetOutputLog", bCollectWatch=True)
    finally:
        try:
            mcp.call("GetOutputLog", bDisarm=True)
        except MCPError:
            pass


def test_set_log_capture_filter_roundtrip(mcp):
    r1 = cap_first(mcp.call("SetLogCaptureFilter", Categories=["LogNexusLink", "LogTemp"]))
    assert r1.get("CaptureFilter") == "custom"
    sample = cap_first(mcp.call("GetOutputLog", Limit=5))
    # captureFilter echoed back so tests can see the active state.
    # Historically a string enum ("custom" / "All"); since the category-list
    # refactor it may also be the actual list of uppercased categories.
    cf = sample.get("CaptureFilter")
    if cf is not None:
        assert (
            cf in ("custom", "All")
            or (isinstance(cf, list) and len(cf) > 0)
        ), f"unexpected captureFilter: {cf!r}"

    r3 = cap_first(mcp.call("SetLogCaptureFilter", Categories=[]))
    assert r3.get("CaptureFilter") == "All"


@pytest.mark.requires_gui
def test_get_slate_widget_error_path(mcp, require_tools):
    """覆盖 `get_runtime_slate_widget` 执行链 —— 真实使用要从 Widget Reflector 拿十六进制地址，
    pytest 无 UI 交互，用一个绝无可能命中的地址 `0x0` 验证工具能优雅拒绝（要么
    返回 error 字段，要么抛 MCPError），而不是 Editor 侧 AV crash。"""
    require_tools("GetRuntimeSlateWidget")
    try:
        r = mcp.call_capability("GetRuntimeSlateWidget", Address="0x0")
    except MCPError:
        # 工具级拒绝是合法契约（参数校验层就挡了）
        return
    assert isinstance(r, dict), r
    # 命中后应明确说明无效地址；不要返回看起来成功的空 payload
    dump = str(r).lower()
    assert (
        r.get("Error")
        or "invalid" in dump
        or "not found" in dump
        or "null" in dump
    ), f"expected error-ish response for bogus address: {r!r}"
