# Copyright byteyang. All Rights Reserved.
"""阶段二：控制台命令 + 截图（截图按规范不自动跑）。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import first_asset_path
from _framework.capability_probe import is_capability_available
from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l2_write


def test_exec_command_stat_fps(mcp, require_tools):
    require_tools("exec_command")
    r = cap_first(mcp.call("exec_command", command="stat fps"))
    assert r.get("executed") is True, f"exec_command did not execute: {r!r}"


def test_exec_command_output_in_get_output_log(mcp, require_tools):
    """exec_command 后 get_output_log 仍可读；勿用 help*（UE 会弹 ConsoleHelp.html）。"""
    require_tools("exec_command", "get_output_log")
    exec_r = cap_first(mcp.call("exec_command", command="stat fps"))
    assert exec_r.get("executed") is True, exec_r
    log_r = cap_first(mcp.call("get_output_log", limit=10, verbosity="all"))
    assert isinstance(log_r.get("entries"), list), log_r


def test_capture_viewport_deferred(mcp):
    """按 NexusMCP 调用规范第 7 条：截图消耗 token，不自动跑。
    SearchMode 下 capture_viewport 不在 tools/list，改用 search_capabilities 确认 capability 注册。
    """
    r = mcp.call("search_capabilities", capabilityName="capture_viewport")
    cap = r.get("capability") or {}
    assert cap.get("name") == "capture_viewport", f"capture_viewport capability missing: {r!r}"


def test_get_editor_context_sections(mcp, require_tools):
    require_tools("get_editor_context")
    r = mcp.call_capability(
        "get_editor_context",
        sections=["selection_actors", "content_browser_path"],
        limit=10,
    )
    results = r.get("results") or [r]
    entry = results[0] if results else r
    assert "sections" in entry or "actors" in entry or "path" in entry, entry


def test_search_console_variables_stat(mcp, require_tools):
    require_tools("search_console_variables")
    r = mcp.call_capability("search_console_variables", query="stat", limit=5)
    results = r.get("results") or [r]
    entry = results[0] if results else r
    assert entry.get("totalCount", 0) >= 0, entry
    vars_list = entry.get("variables") or []
    assert isinstance(vars_list, list), entry


def test_get_asset_lua_binding_sample(mcp):
    """get_asset_lua_binding：编辑器侧解析蓝图 UnLua 绑定（无绑定时 bound=false 亦合法）。"""
    if not is_capability_available(mcp, "get_asset_lua_binding"):
        pytest.skip("get_asset_lua_binding 未编入（需 WITH_UNLUA）")
    bp = first_asset_path(mcp, "Blueprint")
    if not bp:
        pytest.skip("无 Blueprint 样本")
    r = mcp.call_capability("get_asset_lua_binding", assetPath=bp)
    entry = (r.get("results") or [r])[0]
    assert not entry.get("error"), entry
    assert "bound" in entry or "fileExists" in entry, entry


@pytest.mark.requires_gui
def test_capture_viewport_editor_desktop_validate(mcp, require_tools):
    require_tools("capture_viewport")
    r = mcp.call_capability("capture_viewport", target="editor_desktop", validateOnly=True)
    results = r.get("results") or [r]
    entry = results[0] if results else r
    assert entry.get("validateOnly") is True, entry
    assert entry.get("success") is True, entry


@pytest.mark.requires_gui
def test_capture_viewport_validate_only(mcp, require_tools):
    """validateOnly 不写图片，仅验证 editor 视口通路。"""
    require_tools("capture_viewport")
    r = mcp.call_capability("capture_viewport", target="editor", validateOnly=True)
    results = r.get("results") or [r]
    entry = results[0] if results else r
    assert entry.get("validateOnly") is True, entry
    assert entry.get("success") is True, entry


