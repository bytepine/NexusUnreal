# Copyright byteyang. All Rights Reserved.
"""阶段二：控制台命令 + 截图（截图按规范不自动跑）。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import first_asset_path
from _framework.capability_probe import is_capability_available
from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l2_write


def test_exec_command_stat_fps(mcp, require_tools):
    require_tools("ExecCommand")
    r = cap_first(mcp.call("ExecCommand", Command="stat fps"))
    assert r.get("bExecuted") is True, f"exec_command did not execute: {r!r}"


def test_exec_command_output_in_get_output_log(mcp, require_tools):
    """exec_command 后 get_output_log 仍可读；勿用 help*（UE 会弹 ConsoleHelp.html）。"""
    require_tools("ExecCommand", "GetOutputLog")
    exec_r = cap_first(mcp.call("ExecCommand", Command="stat fps"))
    assert exec_r.get("bExecuted") is True, exec_r
    log_r = cap_first(mcp.call("GetOutputLog", Limit=10, Verbosity="All"))
    assert isinstance(log_r.get("Entries"), list), log_r


def test_exec_python_eval(mcp, require_tools):
    """exec_python 需 Python Editor Script Plugin；未启用时 require_tools 自动 skip。"""
    require_tools("ExecPython")
    r = cap_first(mcp.call("ExecPython", Code="1 + 1", Mode="Eval"))
    assert r.get("bExecuted") is True, f"exec_python did not execute: {r!r}"
    assert r.get("Result") == "2", r


def test_exec_python_traceback(mcp, require_tools):
    """语法错误须落到 error 字段（entry 计为失败），而不是静默成功。"""
    require_tools("ExecPython")
    r = cap_first(mcp.call("ExecPython", Code="raise RuntimeError('nexus mcp probe')"))
    assert r.get("bExecuted") is False, r
    assert "nexus mcp probe" in (r.get("Error") or ""), r


def test_exec_python_file_mode_rejects_escape(mcp, require_tools):
    """file 模式必须挡住 Content/Python/ 之外的路径。"""
    require_tools("ExecPython")
    with pytest.raises(MCPError):
        mcp.call("ExecPython", Mode="File", ScriptPath="../../Nexus.uproject")


def test_exec_python_file_mode_requires_py_extension(mcp, require_tools):
    """非 .py 会被 UE 当字面代码执行并报无关的 NameError，须提前拦。"""
    require_tools("ExecPython")
    with pytest.raises(MCPError):
        mcp.call("ExecPython", Mode="File", ScriptPath="probe.txt")


def test_exec_python_undo_not_recorded_for_pure_read(mcp, require_tools):
    """不碰 UObject 的脚本不该产生可回滚记录，否则 undoRecorded 就是假阳性。"""
    require_tools("ExecPython")
    r = cap_first(mcp.call("ExecPython", Code="1 + 1", Mode="Eval"))
    assert r.get("bUndoRecorded") is False, r


def test_exec_python_undo_recorded_matches_engine(mcp, require_tools):
    """undoRecorded 须与引擎自己的答案一致：modify() 的返回值就是「是否入了事务缓冲」。

    传 False 让它只入事务、不把包标脏，测完不留痕迹。
    """
    require_tools("ExecPython")
    code = (
        "import unreal\n"
        "o = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter')\n"
        "print('NEXUS_MODIFY:' + str(o.modify(False)))\n"
    )
    r = cap_first(mcp.call("ExecPython", Code=code))
    assert r.get("bExecuted") is True, r
    output = r.get("Output") or ""
    assert "NEXUS_MODIFY:True" in output, r
    assert r.get("bUndoRecorded") is True, r


def test_get_python_api_log(mcp, require_tools):
    """get_python_api 需 Python Editor Script Plugin；未启用时 require_tools 自动 skip。"""
    require_tools("GetPythonApi")
    r = cap_first(mcp.call("GetPythonApi", Target="unreal", Query="Log"))
    assert r.get("EngineVersion"), r
    entries = r.get("Entries") or []
    assert entries, r
    assert any("log" in (e.get("name") or "").lower() for e in entries), r


@pytest.mark.parametrize("bad_target", [
    "os",                    # 非 unreal 顶层模块
    "unrealx.Foo",           # 前缀相同但不是 unreal
    "unreal..log",           # 连续点
    "unreal'; import os; '", # 注入字符
])
def test_get_python_api_rejects_unsafe_target(mcp, require_tools, bad_target):
    """target 白名单是这个 cap 敢默认开启的唯一依据，须逐条挡住。"""
    require_tools("GetPythonApi")
    with pytest.raises(MCPError):
        mcp.call("GetPythonApi", Target=bad_target)


def test_get_python_api_rejects_unsafe_query(mcp, require_tools):
    """query 只允许标识符字符，带引号/括号一律拒绝。"""
    require_tools("GetPythonApi")
    with pytest.raises(MCPError):
        mcp.call("GetPythonApi", Query="log'); import os; ('")


def test_get_python_api_missing_attr_reports_version(mcp, require_tools):
    """探测不存在的 API 时同样要带版本 —— AI 正是靠它判断该换哪套 API。"""
    require_tools("GetPythonApi")
    r = cap_first(mcp.call("GetPythonApi", Target="unreal.NexusNoSuchApi"))
    assert r.get("Error"), r
    assert r.get("EngineVersion"), r
    assert r.get("pythonVersion"), r


def test_get_python_api_offset_pagination(mcp, require_tools):
    """offset 分页：两页不得重叠，且回显 offset。"""
    require_tools("GetPythonApi")
    page1 = cap_first(mcp.call("GetPythonApi", Target="unreal", Limit=5))
    page2 = cap_first(mcp.call("GetPythonApi", Target="unreal", Offset=5, Limit=5))
    assert len(page1.get("Entries") or []) == 5, page1
    assert page2.get("Offset") == 5, page2
    names1 = {e.get("name") for e in page1["Entries"]}
    names2 = {e.get("name") for e in page2["Entries"]}
    assert not (names1 & names2), (names1, names2)


def test_get_python_api_search_doc(mcp, require_tools):
    """bSearchDoc=True 时名字没命中但 docstring 命中的成员也应返回。"""
    require_tools("GetPythonApi")
    by_name = cap_first(mcp.call("GetPythonApi", Target="unreal", Query="Asset", Limit=100))
    by_doc = cap_first(mcp.call("GetPythonApi", Target="unreal", Query="Asset",
                                bSearchDoc=True, Limit=100))
    assert by_doc.get("totalMatched", 0) >= by_name.get("totalMatched", 0), (by_name, by_doc)


def test_capture_viewport_deferred(mcp):
    """按 NexusMCP 调用规范第 7 条：截图消耗 token，不自动跑。
    SearchMode 下 capture_viewport 不在 tools/list，改用 search_capabilities 确认 capability 注册。
    """
    r = mcp.call("SearchCapabilities", CapabilityName="CaptureViewport")
    cap = r.get("Capability") or {}
    assert cap.get("name") == "CaptureViewport", f"capture_viewport capability missing: {r!r}"


def test_get_editor_context_sections(mcp, require_tools):
    require_tools("GetEditorContext")
    r = mcp.call_capability(
        "GetEditorContext",
        Sections=["SelectionActors", "ContentBrowserPath", "SelectionAssets", "CurrentMap"],
        Limit=10,
    )
    entry = cap_first(r)
    assert "Sections" in entry or "Actors" in entry or "Path" in entry or "AssetPath" in entry, entry


def test_get_editor_context_current_map(mcp, require_tools):
    require_tools("GetEditorContext")
    r = mcp.call_capability("GetEditorContext", Sections=["CurrentMap"])
    entry = cap_first(r)
    path = entry.get("AssetPath") or ""
    assert path.startswith("/Game") or path.startswith("/Engine") or path.startswith("/Temp"), entry


def test_search_console_variables_stat(mcp, require_tools):
    require_tools("SearchConsoleVariables")
    r = mcp.call_capability("SearchConsoleVariables", Query="stat", Limit=5)
    entry = cap_first(r)
    assert entry.get("TotalCount", 0) >= 0, entry
    vars_list = entry.get("Variables") or []
    assert isinstance(vars_list, list), entry


def test_get_asset_lua_binding_sample(mcp):
    """get_asset_lua_binding：编辑器侧解析蓝图 UnLua 绑定（无绑定时 bBound=false 亦合法）。"""
    if not is_capability_available(mcp, "GetAssetLuaBinding"):
        pytest.skip("get_asset_lua_binding 未编入（需 WITH_UNLUA）")
    bp = first_asset_path(mcp, "Blueprint")
    if not bp:
        pytest.skip("无 Blueprint 样本")
    r = mcp.call_capability("GetAssetLuaBinding", AssetPath=bp)
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert "bBound" in entry or "bFileExists" in entry, entry


@pytest.mark.requires_gui
def test_capture_viewport_editor_desktop_validate(mcp, require_tools):
    require_tools("CaptureViewport")
    r = mcp.call_capability("CaptureViewport", Target="EditorDesktop", bValidateOnly=True)
    entry = cap_first(r)
    assert entry.get("bValidateOnly") is True, entry
    assert not entry.get("Error"), entry


@pytest.mark.requires_gui
def test_capture_viewport_validate_only(mcp, require_tools):
    """validateOnly 不写图片，仅验证 editor 视口通路。"""
    require_tools("CaptureViewport")
    r = mcp.call_capability("CaptureViewport", Target="Editor", bValidateOnly=True)
    entry = cap_first(r)
    assert entry.get("bValidateOnly") is True, entry
    assert not entry.get("Error"), entry


def test_capture_editor_panel_list(mcp, require_tools):
    """list 模式不出图：登记面板名 + Tab ID + 当前是否打开。"""
    require_tools("CaptureEditorPanel")
    entry = cap_first(mcp.call_capability("CaptureEditorPanel", Target="list"))
    panels = entry.get("Panels") or []
    names = {p.get("name") for p in panels}
    assert {"Viewport", "ContentBrowser", "details", "OutputLog"} <= names, entry
    assert all(p.get("TabId") for p in panels), entry


def test_capture_editor_panel_rejects_view_angle_without_actor(mcp, require_tools):
    """viewAngle 必须配 actorName，否则请求本身矛盾。"""
    require_tools("CaptureEditorPanel")
    entry = cap_first(mcp.call_capability("CaptureEditorPanel", ViewAngle="Top"))
    assert entry.get("bSuccess") is False, entry
    assert "ActorName" in (entry.get("Error") or ""), entry


@pytest.mark.requires_gui
def test_capture_editor_panel_viewport_validate(mcp, require_tools):
    """validateOnly 只确认面板 tab 存在，不写图片。"""
    require_tools("CaptureEditorPanel")
    entry = cap_first(mcp.call_capability("CaptureEditorPanel", Target="Viewport", bValidateOnly=True))
    assert entry.get("bValidateOnly") is True, entry
    assert not entry.get("Error"), entry


def test_manage_asset_lua_binding(test_ns, mcp):
    if not is_capability_available(mcp, "ManageAssetLuaBinding"):
        pytest.skip("manage_asset_lua_binding 未编入（需 WITH_UNLUA）")
    bp = f"{test_ns}/BP_LuaBind"
    mcp.call_capability("CreateAssetBlueprint", AssetPath=bp, ParentClass="Actor")
    r = mcp.call_capability(
        "ManageAssetLuaBinding",
        AssetPath=bp,
        Operations=[{"Action": "Bind", "ModuleName": "Script.BP_LuaBind"}],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), r
    got = cap_first(mcp.call_capability("GetAssetLuaBinding", AssetPath=bp))
    assert not got.get("Error"), got
    with pytest.raises(MCPError):
        mcp.call_capability(
            "ManageAssetLuaBinding",
            AssetPath=bp,
            Operations=[{"Action": "not_a_real_action"}],
        )
    unbind = mcp.call_capability(
        "ManageAssetLuaBinding",
        AssetPath=bp,
        Operations=[{"Action": "Unbind"}],
    )
    assert isinstance(cap_first(unbind), dict), unbind


