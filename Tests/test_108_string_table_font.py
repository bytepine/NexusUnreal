# Copyright byteyang. All Rights Reserved.
"""StringTable 往返 + Font get/manage。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l3_asset


def test_string_table_roundtrip(test_ns, mcp):
    path = f"{test_ns}/ST_Created"
    cr = mcp.call_capability("create_asset_string_table", assetPath=path, namespace="NxTest")
    entry = cap_first(cr)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower():
        pytest.fail(f"create_asset_string_table 失败: {entry}")

    man = mcp.call_capability(
        "manage_asset_string_table",
        assetPath=path,
        operations=[{"action": "add_key", "key": "Hello", "source": "World"}],
    )
    m = cap_first(man)
    assert not m.get("error"), man

    got = cap_first(mcp.call_capability("get_asset_string_table", assetPath=path))
    assert not got.get("error"), got
    keys = got.get("keys") or []
    assert any(isinstance(k, dict) and k.get("key") == "Hello" for k in keys), got

    extra = mcp.call_capability(
        "manage_asset_string_table",
        assetPath=path,
        operations=[
            {"action": "set_source", "key": "Hello", "source": "World2"},
            {"action": "remove_key", "key": "Hello"},
        ],
    )
    for e in (extra.get("results") or [cap_first(extra)]):
        if isinstance(e, dict):
            assert not e.get("error"), extra

    try:
        bad = cap_first(
            mcp.call_capability(
                "manage_asset_string_table",
                assetPath=path,
                operations=[{"action": "not_a_real_action", "key": "x"}],
            )
        )
    except MCPError as exc:
        bad = {"error": str(exc)}
    assert bad.get("error"), bad


def test_font_get_manage(mcp):
    r = mcp.call_capability("search_asset", assetType="Font", pathFilter="/Engine/", limit=1)
    payload = r if isinstance(r, dict) else {}
    assets = payload.get("assets") or payload.get("results") or []
    if not assets:
        r = mcp.call_capability("search_asset", assetType="Font", pathFilter="/Game/", limit=1)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("assets") or payload.get("results") or []
    if not assets:
        pytest.skip("未找到 Font 资产")
    first = assets[0] if isinstance(assets[0], dict) else {}
    path = first.get("assetPath") or first.get("path") or ""
    if not path:
        pytest.skip("Font 路径为空")
    got = cap_first(mcp.call_capability("get_asset_font", assetPath=path))
    assert "scalingFactor" in got or "characterCount" in got, got
    man = cap_first(
        mcp.call_capability(
            "manage_asset_font",
            assetPath=path,
            operations=[{"action": "set_property", "propertyPath": "ScalingFactor", "value": "1.0"}],
        )
    )
    assert isinstance(man, dict), man
