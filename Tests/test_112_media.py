# Copyright byteyang. All Rights Reserved.
"""FileMediaSource 往返。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l3_asset


def test_media_source_roundtrip(test_ns, mcp):
    path = f"{test_ns}/MS_Created"
    cr = mcp.call_capability("create_asset_media_source", assetPath=path)
    entry = cap_first(cr)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower():
        pytest.fail(f"create_asset_media_source 失败: {entry}")

    man = cap_first(
        mcp.call_capability(
            "manage_asset_media_source",
            assetPath=path,
            operations=[{"action": "set_file_path", "mediaPath": "C:/tmp/nx_dummy.mp4"}],
        )
    )
    assert not man.get("error"), man

    got = cap_first(mcp.call_capability("get_asset_media_source", assetPath=path))
    assert not got.get("error"), got
    assert "mediaPath" in got, got

    bad = cap_first(
        mcp.call_capability(
            "manage_asset_media_source",
            assetPath=path,
            operations=[{"action": "not_real"}],
        )
    )
    assert bad.get("error"), bad
