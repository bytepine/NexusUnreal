# Copyright byteyang. All Rights Reserved.
"""阶段五：Widget Blueprint — 批量建树 + 运行时模拟属性读写。"""

from __future__ import annotations

import pytest

from _framework.assertions import assert_success_count
from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l3_asset


@pytest.fixture(scope="module")
def wbp_path(test_ns, mcp):
    path = f"{test_ns}/WBP_TestHUD"
    mcp.call("create_widget", assetPath=path)
    yield path


def test_widget_tree_batch_build(mcp, wbp_path):
    """5.2：一次批量建完整控件树（关键用例）。"""
    r = mcp.call(
        "manage_widget",
        assetPath=wbp_path,
        widgets=[
            {"action": "add", "widgetClass": "CanvasPanel",    "widgetName": "RootCanvas"},
            {"action": "add", "widgetClass": "TextBlock",      "widgetName": "TitleText",   "parentWidget": "RootCanvas"},
            {"action": "add", "widgetClass": "Button",         "widgetName": "ClickBtn",    "parentWidget": "RootCanvas"},
            {"action": "add", "widgetClass": "CheckBox",       "widgetName": "TestCheck",   "parentWidget": "RootCanvas"},
            {"action": "add", "widgetClass": "Slider",         "widgetName": "TestSlider",  "parentWidget": "RootCanvas"},
            {"action": "add", "widgetClass": "EditableTextBox","widgetName": "TestInput",   "parentWidget": "RootCanvas"},
            {"action": "add", "widgetClass": "ProgressBar",    "widgetName": "RemoveMe",    "parentWidget": "RootCanvas"},
        ],
    )
    assert_success_count(r, 7, context="widget tree batch")


def test_widget_tree_filter(mcp, wbp_path):
    r = mcp.call("get_asset_user_widget", assetPath=wbp_path, nameFilter="Test")
    dump = str(r)
    assert "TestCheck" in dump or "TestSlider" in dump or "TestInput" in dump, \
        f"filter Test did not match expected widgets: {dump}"


def test_widget_animations_section(mcp, wbp_path):
    """读取 WBP animations section（无动画时返回空数组）。"""
    r = mcp.call_capability(
        "get_asset_user_widget",
        assetPath=wbp_path,
        sections=["animations"],
    )
    payload = cap_first(r)
    assert "animations" in payload, f"animations section missing: {r!r}"
    assert isinstance(payload.get("animations"), list), f"animations must be array: {r!r}"


def test_widget_set_text(mcp, wbp_path):
    pytest.skip(
        "编辑器侧 Widget 默认属性写入在当前 Capability 模型中无对应接口；"
        "运行时属性修改请在 PIE 会话中使用 set_runtime_widget_property。"
    )


def test_widget_remove_one(mcp, wbp_path):
    r = mcp.call(
        "manage_widget",
        assetPath=wbp_path,
        widgets=[{"action": "remove", "widgetName": "RemoveMe"}],
    )
    assert_success_count(r, 1, context="widget remove")


def test_widget_save(mcp, wbp_path):
    save = mcp.call("save_asset", assetPaths=[wbp_path])
    assert (save.get("saved") or 0) == 1, f"wbp save: {save!r}"
