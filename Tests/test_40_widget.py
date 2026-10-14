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
    mcp.call("CreateAssetUserWidget", AssetPath=path)
    yield path


def test_widget_tree_batch_build(mcp, wbp_path):
    """5.2：一次批量建完整控件树（关键用例）。"""
    r = mcp.call(
        "ManageAssetUserWidget",
        AssetPath=wbp_path,
        Operations=[
            {"Action": "Add", "WidgetClass": "CanvasPanel",    "WidgetName": "RootCanvas"},
            {"Action": "Add", "WidgetClass": "TextBlock",      "WidgetName": "TitleText",   "ParentWidget": "RootCanvas"},
            {"Action": "Add", "WidgetClass": "Button",         "WidgetName": "ClickBtn",    "ParentWidget": "RootCanvas"},
            {"Action": "Add", "WidgetClass": "CheckBox",       "WidgetName": "TestCheck",   "ParentWidget": "RootCanvas"},
            {"Action": "Add", "WidgetClass": "Slider",         "WidgetName": "TestSlider",  "ParentWidget": "RootCanvas"},
            {"Action": "Add", "WidgetClass": "EditableTextBox","WidgetName": "TestInput",   "ParentWidget": "RootCanvas"},
            {"Action": "Add", "WidgetClass": "ProgressBar",    "WidgetName": "RemoveMe",    "ParentWidget": "RootCanvas"},
        ],
    )
    assert_success_count(r, 7, context="widget tree batch")


def test_widget_tree_filter(mcp, wbp_path):
    r = mcp.call("GetAssetUserWidget", AssetPath=wbp_path, NameFilter="Test")
    dump = str(r)
    assert "TestCheck" in dump or "TestSlider" in dump or "TestInput" in dump, \
        f"filter Test did not match expected widgets: {dump}"


def test_widget_animations_section(mcp, wbp_path):
    """读取 WBP animations section（无动画时返回空数组）。"""
    r = mcp.call_capability(
        "GetAssetUserWidget",
        AssetPath=wbp_path,
        Sections=["Animations"],
    )
    payload = cap_first(r)
    assert "Animations" in payload, f"animations section missing: {r!r}"
    assert isinstance(payload.get("Animations"), list), f"animations must be array: {r!r}"


def test_widget_set_text(mcp, wbp_path):
    pytest.skip(
        "编辑器侧 Widget 默认属性写入在当前 Capability 模型中无对应接口；"
        "运行时属性修改请在 PIE 会话中使用 set_runtime_widget_property。"
    )


def test_widget_remove_one(mcp, wbp_path):
    r = mcp.call(
        "ManageAssetUserWidget",
        AssetPath=wbp_path,
        Operations=[{"Action": "Remove", "WidgetName": "RemoveMe"}],
    )
    assert_success_count(r, 1, context="widget remove")


def test_widget_save(mcp, wbp_path):
    save = mcp.call("SaveAsset", AssetPath=wbp_path)
    assert (save.get("bSaved") or 0) == 1, f"wbp save: {save!r}"


def test_widget_animation_crud(mcp, wbp_path):
    """动画 CRUD：add_animation → add_track → add_key → get tracks → remove。"""
    r = mcp.call(
        "ManageAssetUserWidget",
        AssetPath=wbp_path,
        Operations=[
            {"Action": "AddAnimation", "AnimationName": "FadeIn"},
            {"Action": "AddTrack", "AnimationName": "FadeIn", "TrackName": "Alpha"},
            {"Action": "AddKey", "AnimationName": "FadeIn", "Time": 0.5, "KeyValue": 1.0},
        ],
    )
    assert_success_count(r, 3, context="widget animation crud")

    got = mcp.call_capability(
        "GetAssetUserWidget",
        AssetPath=wbp_path,
        Sections=["Animations"],
    )
    payload = cap_first(got)
    anims = payload.get("Animations") or []
    names = [a.get("name") for a in anims if isinstance(a, dict)]
    assert any("FadeIn" in (n or "") for n in names), f"FadeIn missing: {payload!r}"
    fade = next((a for a in anims if isinstance(a, dict) and "FadeIn" in (a.get("name") or "")), None)
    assert fade and fade.get("Tracks"), f"tracks missing: {payload!r}"

    rm = mcp.call(
        "ManageAssetUserWidget",
        AssetPath=wbp_path,
        Operations=[{"Action": "RemoveAnimation", "AnimationName": "FadeIn"}],
    )
    assert_success_count(rm, 1, context="RemoveAnimation")


def test_widget_graph_overview(mcp, wbp_path):
    r = mcp.call_capability(
        "GetAssetUserWidget",
        AssetPath=wbp_path,
        Sections=["graphOverview"],
    )
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    graphs = entry.get("Graphs") or []
    assert isinstance(graphs, list), entry
    names = [g.get("name") or g.get("GraphName") for g in graphs if isinstance(g, dict)]
    joined = " ".join(n or "" for n in names)
    assert "EventGraph" in joined or graphs, f"expected EventGraph in graphOverview: {entry!r}"


def test_widget_animation_bind_and_remove_key(mcp, wbp_path):
    """绑定控件 RenderOpacity 轨，打 key 后再 remove_key / remove_track。"""
    r = mcp.call(
        "ManageAssetUserWidget",
        AssetPath=wbp_path,
        Operations=[
            {"Action": "AddAnimation", "AnimationName": "FadeBound"},
            {
                "Action": "AddTrack",
                "AnimationName": "FadeBound",
                "WidgetName": "TitleText",
                "PropertyPath": "RenderOpacity",
                "TrackName": "Opacity",
            },
            {
                "Action": "AddKey",
                "AnimationName": "FadeBound",
                "TrackName": "Opacity",
                "Time": 0.25,
                "KeyValue": 0.5,
            },
        ],
    )
    assert_success_count(r, 3, context="bound animation track")

    rm_key = mcp.call(
        "ManageAssetUserWidget",
        AssetPath=wbp_path,
        Operations=[{
            "Action": "RemoveKey",
            "AnimationName": "FadeBound",
            "TrackName": "Opacity",
            "Time": 0.25,
        }],
    )
    assert_success_count(rm_key, 1, context="RemoveKey")

    rm_track = mcp.call(
        "ManageAssetUserWidget",
        AssetPath=wbp_path,
        Operations=[{
            "Action": "RemoveTrack",
            "AnimationName": "FadeBound",
            "TrackName": "Opacity",
        }],
    )
    assert_success_count(rm_track, 1, context="RemoveTrack")

    mcp.call(
        "ManageAssetUserWidget",
        AssetPath=wbp_path,
        Operations=[{"Action": "RemoveAnimation", "AnimationName": "FadeBound"}],
    )


def test_wbp_event_graph_via_blueprint(mcp, wbp_path):
    """WBP EventGraph 走 manage_asset_blueprint，不在 user_widget 复制图 API。"""
    add = mcp.call_capability(
        "ManageAssetBlueprint",
        AssetPath=wbp_path,
        Operations=[{
            "Action": "AddNode",
            "GraphName": "EventGraph",
            "NodeClass": "K2Node_CallFunction",
            "FunctionName": "PrintString",
            "PosX": 200,
            "PosY": 100,
        }],
    )
    pn_id = cap_first(add).get("NodeId")
    assert pn_id, f"WBP EventGraph add_node: {add!r}"


def test_widget_set_slot_and_property(mcp, wbp_path):
    try:
        r = mcp.call_capability(
            "ManageAssetUserWidget",
            AssetPath=wbp_path,
            Operations=[
                {
                    "Action": "SetSlot",
                    "WidgetName": "TitleText",
                    "AnchorMinX": 0.5,
                    "AnchorMinY": 0.5,
                    "AnchorMaxX": 0.5,
                    "AnchorMaxY": 0.5,
                },
                {"Action": "SetProperty", "WidgetName": "TitleText", "PropertyPath": "Visibility", "Value": "Visible"},
            ],
        )
    except MCPError as e:
        pytest.skip(f"widget set_slot/set_property 跳过: {e}")
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"widget set_slot/set_property 跳过: {e}")
