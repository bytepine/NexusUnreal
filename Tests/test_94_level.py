# Copyright byteyang. All Rights Reserved.
"""阶段十四：关卡只读（P6 get_asset_level）。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import MCPError

pytestmark = pytest.mark.l3_asset


def _first_level_path(mcp) -> str | None:
    for asset_type in ("World", "level", "map"):
        try:
            listing = mcp.call_capability(
                "search_asset",
                assetType=asset_type,
                pathFilter="/Game/",
                limit=5,
            )
        except MCPError:
            continue
        assets = listing.get("assets") or []
        if assets:
            row = assets[0]
            return row.get("assetPath") or row.get("path")
    return None


def test_get_asset_level_actors_and_settings(mcp, require_tools):
    require_tools("get_asset_level")
    path = _first_level_path(mcp)
    if not path:
        pytest.skip("项目中无关卡 UWorld 样本")
    r = mcp.call_capability(
        "get_asset_level",
        assetPath=path,
        sections=["actors", "settings"],
        limit=20,
    )
    entry = (r.get("results") or [r])[0]
    assert not entry.get("error"), entry
    assert entry.get("packagePath"), entry
    assert "actorTotalCount" in entry, entry
    assert isinstance(entry.get("actors"), list), entry
    assert "settings" in entry, entry
