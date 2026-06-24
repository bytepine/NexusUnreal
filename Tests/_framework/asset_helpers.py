# Copyright byteyang. All Rights Reserved.
"""测试用资产发现与按需创建（优先 test_ns，回退模板工程已知路径）。"""

from __future__ import annotations

import contextlib
from typing import Callable, Optional

from _framework.mcp_client import MCPClient, MCPError, cap_first

# ThirdPerson 模板工程内稳定存在的只读样本（search 失败时回退）
_KNOWN_PATHS: dict[str, str] = {
    "Skeleton": "/Game/Mannequin/Character/Mesh/UE4_Mannequin_Skeleton",
    "SkeletalMesh": "/Game/Mannequin/Character/Mesh/SK_Mannequin",
    "AnimSequence": "/Game/Mannequin/Animations/ThirdPersonIdle",
    "StaticMesh": "/Game/Geometry/Meshes/1M_Cube",
    "Texture2D": "/Game/Mannequin/Character/Textures/T_Male_N",
    "Blueprint": "/Game/ThirdPersonBP/Blueprints/ThirdPersonCharacter",
    "WidgetBlueprint": "/Game/ThirdPersonBP/Blueprints/WBP_Main",
    "Material": "/Game/ThirdPerson/Meshes/RampMaterial",
    "World": "/Game/ThirdPersonBP/Maps/ThirdPersonExampleMap",
    "level": "/Game/ThirdPersonBP/Maps/ThirdPersonExampleMap",
    "map": "/Game/ThirdPersonBP/Maps/ThirdPersonExampleMap",
}


def first_asset_path(
    mcp: MCPClient,
    asset_type: str,
    *,
    path_filter: str = "/Game/",
    limit: int = 10,
) -> Optional[str]:
    """search_asset 取第一条路径；兼容 results[0] 批量包装。"""
    try:
        listing = mcp.call_capability(
            "search_asset",
            assetType=asset_type,
            pathFilter=path_filter,
            limit=limit,
        )
    except MCPError:
        listing = None
    if listing:
        payload = cap_first(listing)
        assets = payload.get("assets") or []
        if assets:
            row = assets[0]
            path = row.get("assetPath") or row.get("path")
            if path:
                return path
    return _KNOWN_PATHS.get(asset_type)


def first_level_path(mcp: MCPClient) -> Optional[str]:
    for asset_type in ("World", "level", "map"):
        path = first_asset_path(mcp, asset_type)
        if path:
            return path
    return None


def _create_ignore_exists(mcp: MCPClient, fn: Callable[[], None]) -> None:
    with contextlib.suppress(MCPError):
        fn()


def ensure_blueprint(mcp: MCPClient, test_ns: str, name: str = "BP_TestSample") -> str:
    path = f"{test_ns}/{name}"
    _create_ignore_exists(
        mcp,
        lambda: mcp.call("create_blueprint", assetPath=path, parentClass="Actor"),
    )
    return path


def ensure_struct(mcp: MCPClient, test_ns: str, name: str = "S_TestProbe") -> str:
    path = f"{test_ns}/{name}"
    _create_ignore_exists(
        mcp,
        lambda: mcp.call("create_struct", assetPath=path),
    )
    return path


def ensure_material(mcp: MCPClient, test_ns: str, name: str = "M_TestProbe") -> str:
    path = f"{test_ns}/{name}"
    _create_ignore_exists(
        mcp,
        lambda: mcp.call("create_material", assetPath=path),
    )
    return path


def ensure_widget(mcp: MCPClient, test_ns: str, name: str = "WBP_TestProbe") -> str:
    path = f"{test_ns}/{name}"
    _create_ignore_exists(
        mcp,
        lambda: mcp.call("create_widget", assetPath=path),
    )
    return path


def ensure_test_hud_widget(mcp: MCPClient, test_ns: str) -> str:
    """WBP_TestHUD + 标准控件树（与 test_40 一致，供 PIE Widget 用例自给）。"""
    path = ensure_widget(mcp, test_ns, "WBP_TestHUD")
    try:
        probe = mcp.call_capability(
            "get_asset_user_widget",
            assetPath=path,
            nameFilter="TitleText",
        )
        if "TitleText" in str(probe):
            return path
    except MCPError:
        pass
    mcp.call(
        "manage_widget",
        assetPath=path,
        widgets=[
            {"action": "add", "widgetClass": "CanvasPanel", "widgetName": "RootCanvas"},
            {"action": "add", "widgetClass": "TextBlock", "widgetName": "TitleText", "parentWidget": "RootCanvas"},
            {"action": "add", "widgetClass": "Button", "widgetName": "ClickBtn", "parentWidget": "RootCanvas"},
            {"action": "add", "widgetClass": "CheckBox", "widgetName": "TestCheck", "parentWidget": "RootCanvas"},
            {"action": "add", "widgetClass": "Slider", "widgetName": "TestSlider", "parentWidget": "RootCanvas"},
            {"action": "add", "widgetClass": "EditableTextBox", "widgetName": "TestInput", "parentWidget": "RootCanvas"},
            {"action": "add", "widgetClass": "ProgressBar", "widgetName": "RemoveMe", "parentWidget": "RootCanvas"},
        ],
    )
    with contextlib.suppress(MCPError):
        mcp.call("save_asset", assetPaths=[path])
    return path


def ensure_behavior_tree(mcp: MCPClient, test_ns: str) -> str:
    bt = f"{test_ns}/BT_TestProbe"
    bb = f"{test_ns}/BB_TestProbe"
    _create_ignore_exists(
        mcp,
        lambda: mcp.call(
            "create_behavior_tree",
            assetPath=bt,
            blackboardPath=bb,
        ),
    )
    return bt


def resolve_skeleton(mcp: MCPClient) -> str:
    """动画类测试依赖的 Skeleton：先搜 Mannequin，再回退已知路径。"""
    path = first_asset_path(
        mcp,
        "Skeleton",
        path_filter="/Game/Mannequin",
        limit=5,
    )
    if not path:
        path = _KNOWN_PATHS["Skeleton"]
    return path


def probe_asset_readable(
    mcp: MCPClient,
    capability: str,
    asset_path: str,
    **kwargs: object,
) -> bool:
    """调用只读 get_asset_* 验证路径有效。"""
    try:
        r = mcp.call_capability(capability, assetPath=asset_path, **kwargs)
    except MCPError:
        return False
    entry = (r.get("results") or [r])[0]
    return isinstance(entry, dict) and not entry.get("error")
