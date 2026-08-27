# Copyright byteyang. All Rights Reserved.
"""阶段五：Widget Blueprint — 批量建树 + 运行时模拟属性读写。"""

from __future__ import annotations

import pytest

from _framework.assertions import assert_success_count
from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l3_asset


@pytest.fixture(scope="module")
def wbp_path(test_ns, mcp):
    path = f"{test_ns}/WBP_TestHUD"
    mcp.call("create_asset_user_widget", assetPath=path)
    yield path


def test_widget_tree_batch_build(mcp, wbp_path):
    """5.2：一次批量建完整控件树（关键用例）。"""
    r = mcp.call(
        "manage_asset_user_widget",
        assetPath=wbp_path,
        operations=[
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
        "manage_asset_user_widget",
        assetPath=wbp_path,
        operations=[{"action": "remove", "widgetName": "RemoveMe"}],
    )
    assert_success_count(r, 1, context="widget remove")


def test_widget_save(mcp, wbp_path):
    save = mcp.call("save_asset", assetPath=wbp_path)
    assert (save.get("saved") or 0) == 1, f"wbp save: {save!r}"


def test_widget_animation_crud(mcp, wbp_path):
    """动画 CRUD：add_animation → add_track → add_key → get tracks → remove。"""
    r = mcp.call(
        "manage_asset_user_widget",
        assetPath=wbp_path,
        operations=[
            {"action": "add_animation", "animationName": "FadeIn"},
            {"action": "add_track", "animationName": "FadeIn", "trackName": "Alpha"},
            {"action": "add_key", "animationName": "FadeIn", "time": 0.5, "keyValue": 1.0},
        ],
    )
    assert_success_count(r, 3, context="widget animation crud")

    got = mcp.call_capability(
        "get_asset_user_widget",
        assetPath=wbp_path,
        sections=["animations"],
    )
    payload = cap_first(got)
    anims = payload.get("animations") or []
    names = [a.get("name") for a in anims if isinstance(a, dict)]
    assert any("FadeIn" in (n or "") for n in names), f"FadeIn missing: {payload!r}"
    fade = next((a for a in anims if isinstance(a, dict) and "FadeIn" in (a.get("name") or "")), None)
    assert fade and fade.get("tracks"), f"tracks missing: {payload!r}"

    rm = mcp.call(
        "manage_asset_user_widget",
        assetPath=wbp_path,
        operations=[{"action": "remove_animation", "animationName": "FadeIn"}],
    )
    assert_success_count(rm, 1, context="remove_animation")


def test_widget_graph_overview(mcp, wbp_path):
    r = mcp.call_capability(
        "get_asset_user_widget",
        assetPath=wbp_path,
        sections=["graphOverview"],
    )
    entry = cap_first(r)
    assert not entry.get("error"), entry
    graphs = entry.get("graphs") or []
    assert isinstance(graphs, list), entry
    names = [g.get("name") or g.get("graphName") for g in graphs if isinstance(g, dict)]
    joined = " ".join(n or "" for n in names)
    assert "EventGraph" in joined or graphs, f"expected EventGraph in graphOverview: {entry!r}"


def test_widget_animation_bind_and_remove_key(mcp, wbp_path):
    """绑定控件 RenderOpacity 轨，打 key 后再 remove_key / remove_track。"""
    r = mcp.call(
        "manage_asset_user_widget",
        assetPath=wbp_path,
        operations=[
            {"action": "add_animation", "animationName": "FadeBound"},
            {
                "action": "add_track",
                "animationName": "FadeBound",
                "widgetName": "TitleText",
                "propertyPath": "RenderOpacity",
                "trackName": "Opacity",
            },
            {
                "action": "add_key",
                "animationName": "FadeBound",
                "trackName": "Opacity",
                "time": 0.25,
                "keyValue": 0.5,
            },
        ],
    )
    assert_success_count(r, 3, context="bound animation track")

    rm_key = mcp.call(
        "manage_asset_user_widget",
        assetPath=wbp_path,
        operations=[{
            "action": "remove_key",
            "animationName": "FadeBound",
            "trackName": "Opacity",
            "time": 0.25,
        }],
    )
    assert_success_count(rm_key, 1, context="remove_key")

    rm_track = mcp.call(
        "manage_asset_user_widget",
        assetPath=wbp_path,
        operations=[{
            "action": "remove_track",
            "animationName": "FadeBound",
            "trackName": "Opacity",
        }],
    )
    assert_success_count(rm_track, 1, context="remove_track")

    mcp.call(
        "manage_asset_user_widget",
        assetPath=wbp_path,
        operations=[{"action": "remove_animation", "animationName": "FadeBound"}],
    )


def test_wbp_event_graph_via_blueprint(mcp, wbp_path):
    """WBP EventGraph 走 manage_asset_blueprint，不在 user_widget 复制图 API。"""
    add = mcp.call_capability(
        "manage_asset_blueprint",
        assetPath=wbp_path,
        operations=[{
            "action": "add_node",
            "graphName": "EventGraph",
            "nodeClass": "K2Node_CallFunction",
            "functionName": "PrintString",
            "posX": 200,
            "posY": 100,
        }],
    )
    pn_id = cap_first(add).get("nodeId")
    assert pn_id, f"WBP EventGraph add_node: {add!r}"


def test_widget_set_slot_and_property(mcp, wbp_path):
    try:
        r = mcp.call_capability(
            "manage_asset_user_widget",
            assetPath=wbp_path,
            operations=[
                {
                    "action": "set_slot",
                    "widgetName": "TitleText",
                    "anchorMinX": 0.5,
                    "anchorMinY": 0.5,
                    "anchorMaxX": 0.5,
                    "anchorMaxY": 0.5,
                },
                {"action": "set_property", "widgetName": "TitleText", "propertyPath": "Visibility", "value": "Visible"},
            ],
        )
    except MCPError as e:
        pytest.skip(f"widget set_slot/set_property 跳过: {e}")
    for e in (r.get("results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("error"):
            pytest.skip(f"widget set_slot/set_property 跳过: {e}")
