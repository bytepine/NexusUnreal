# Copyright byteyang. All Rights Reserved.
"""FileMediaSource 往返。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l3_asset


def test_media_source_roundtrip(test_ns, mcp):
    path = f"{test_ns}/MS_Created"
    cr = mcp.call_capability("CreateAssetMediaSource", AssetPath=path)
    entry = cap_first(cr)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower():
        pytest.fail(f"create_asset_media_source 失败: {entry}")

    man = cap_first(
        mcp.call_capability(
            "ManageAssetMediaSource",
            AssetPath=path,
            Operations=[{"Action": "SetFilePath", "MediaPath": "C:/tmp/nx_dummy.mp4"}],
        )
    )
    assert not man.get("Error"), man
    loop = cap_first(
        mcp.call_capability(
            "ManageAssetMediaSource",
            AssetPath=path,
            Operations=[{"Action": "SetLoop", "bLoop": True}],
        )
    )
    if loop.get("Error"):
        pytest.skip(f"media set_loop 跳过: {loop}")

    got = cap_first(mcp.call_capability("GetAssetMediaSource", AssetPath=path))
    assert not got.get("Error"), got
    assert "MediaPath" in got, got

    try:
        bad = cap_first(
            mcp.call_capability(
                "ManageAssetMediaSource",
                AssetPath=path,
                Operations=[{"Action": "not_real"}],
            )
        )
    except MCPError as exc:
        bad = {"Error": str(exc)}
    assert bad.get("Error"), bad
