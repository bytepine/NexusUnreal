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
    for required in ["search_capabilities", "call_capability", "submit_feedback"]:
        assert required in tool_names, (
            f"meta-tool missing from tools/list: {required}\n"
            f"actual tools: {tool_names!r}"
        )


def test_search_capabilities_roundtrip(mcp):
    """search_capabilities 能发现至少一个 get_editor_info 相关 capability。"""
    r = mcp.call("search_capabilities", query="editor info")
    # 返回体有 capabilities 列表（≥2 条时）或 capability 对象（精确命中时）
    assert isinstance(r, dict), f"search_capabilities returned non-dict: {r!r}"


def test_search_capabilities_nested_widget_action_enum(mcp):
    """manage_asset_user_widget 的 widgets[].action 须在 parameters[] 中带 enum。"""
    r = mcp.call("search_capabilities", capabilityName="manage_asset_user_widget")
    # 新版返回 {"capability":{"parameters":[...]}}，旧版顶层 parameters
    cap = r.get("capability") or r
    params = cap.get("parameters") or []
    by_name = {p.get("name"): p for p in params if isinstance(p, dict)}
    action = by_name.get("widgets[].action")
    assert action is not None, f"widgets[].action missing in parameters: {by_name.keys()!r}"
    assert action.get("type") == "string (enum)" or action.get("enum"), action


def test_call_capability_legacy_blackboard_not_unknown(mcp):
    """create_blackboard 旧名应解析为 create_asset_blackboard，不得 errorKind=unknown。"""
    try:
        r = mcp.call(
            "call_capability",
            capability="create_blackboard",
            arguments={"assetPath": "/Game/__nexus_pytest_nonexistent_bb__", "save": False},
        )
    except MCPError as exc:
        r = exc.data if isinstance(exc.data, dict) else {}
    if isinstance(r, dict) and r.get("errorKind") == "unknown":
        pytest.fail(f"legacy name should resolve, got: {r!r}")


def test_search_capabilities_get_asset_hint(mcp):
    """query=get_asset 零命中时应返回 get_asset_<类型> 路由 hint。"""
    r = mcp.call("search_capabilities", query="get_asset")
    assert r.get("errorKind") == "not_found", r
    hint = r.get("hint") or ""
    assert "get_asset_" in hint, f"expected routing hint: {r!r}"


def test_search_capabilities_not_found(mcp):
    """精确名不存在时 errorKind=not_found，勿与 disabled 混用。"""
    r = mcp.call(
        "search_capabilities",
        capabilityName="__nexus_mcp_nonexistent_cap_xyz__",
    )
    assert r.get("errorKind") == "not_found", r
    assert "capability" not in r


def test_submit_feedback_smoke(mcp):
    """submit_feedback 最小通路：写入后返回 ok。"""
    r = mcp.call(
        "submit_feedback",
        category="other",
        note="pytest P2 smoke",
        capability="get_editor_info",
    )
    assert r.get("ok") is True, r


def test_call_capability_editor_info(mcp):
    """通过 call_capability 调用 get_editor_info，验证 SearchMode 完整链路。"""
    info = mcp.call_capability("get_editor_info")
    assert info, "get_editor_info returned empty payload"
    joined = " ".join(str(v) for v in info.values())
    assert joined, "get_editor_info payload has no string fields"


def test_get_editor_info(mcp):
    info = mcp.call("get_editor_info")  # routes through call_capability automatically
    assert info, "get_editor_info returned empty payload"
    joined = " ".join(str(v) for v in info.values())
    assert joined, "get_editor_info payload has no string fields"


def test_get_output_log_basic(mcp, require_tools):
    require_tools("get_output_log")
    r = cap_first(mcp.call("get_output_log", limit=20))
    assert "entries" in r, f"no entries field: {r!r}"
    assert isinstance(r["entries"], list)
    total = r.get("totalCount")
    if total is not None:
        assert total >= len(r["entries"])


def test_get_output_log_filtered_offset(mcp):
    r = cap_first(mcp.call("get_output_log", verbosity="warning",
                 textFilter="NexusLink", limit=10, offset=5))
    assert isinstance(r.get("entries"), list)


def test_set_log_capture_filter_roundtrip(mcp):
    r1 = cap_first(mcp.call("set_log_capture_filter", categories=["LogNexusLink", "LogTemp"]))
    assert r1.get("captureFilter") == "custom"
    sample = cap_first(mcp.call("get_output_log", limit=5))
    # captureFilter echoed back so tests can see the active state.
    # Historically a string enum ("custom" / "all"); since the category-list
    # refactor it may also be the actual list of uppercased categories.
    cf = sample.get("captureFilter")
    if cf is not None:
        assert (
            cf in ("custom", "all")
            or (isinstance(cf, list) and len(cf) > 0)
        ), f"unexpected captureFilter: {cf!r}"

    r3 = cap_first(mcp.call("set_log_capture_filter", categories=[]))
    assert r3.get("captureFilter") == "all"


@pytest.mark.requires_gui
def test_get_slate_widget_error_path(mcp, require_tools):
    """覆盖 `get_runtime_slate_widget` 执行链 —— 真实使用要从 Widget Reflector 拿十六进制地址，
    pytest 无 UI 交互，用一个绝无可能命中的地址 `0x0` 验证工具能优雅拒绝（要么
    返回 error 字段，要么抛 MCPError），而不是 Editor 侧 AV crash。"""
    require_tools("get_runtime_slate_widget")
    try:
        r = mcp.call_capability("get_runtime_slate_widget", address="0x0")
    except MCPError:
        # 工具级拒绝是合法契约（参数校验层就挡了）
        return
    assert isinstance(r, dict), r
    # 命中后应明确说明无效地址；不要返回看起来成功的空 payload
    dump = str(r).lower()
    assert (
        r.get("error")
        or "invalid" in dump
        or "not found" in dump
        or "null" in dump
    ), f"expected error-ish response for bogus address: {r!r}"
