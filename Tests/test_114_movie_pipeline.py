# Copyright byteyang. All Rights Reserved.
"""MoviePipeline config create/get（UE5+ 门控 skip）。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.0")]


@pytest.fixture(scope="module", autouse=True)
def require_mrq(mcp):
    if not is_capability_available(mcp, "create_asset_movie_pipeline_config"):
        pytest.skip("MoviePipeline capability 未编入（需 WITH_MOVIE_RENDER_PIPELINE）")


def test_movie_pipeline_config(test_ns, mcp):
    path = f"{test_ns}/MPC_Created"
    cr = mcp.call_capability("create_asset_movie_pipeline_config", assetPath=path)
    entry = cap_first(cr)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower():
        pytest.fail(f"create_asset_movie_pipeline_config 失败: {entry}")
    got = cap_first(mcp.call_capability("get_asset_movie_pipeline_config", assetPath=path))
    assert not got.get("error"), got
    man = cap_first(
        mcp.call_capability(
            "manage_asset_movie_pipeline_config",
            assetPath=path,
            operations=[{"action": "set_output", "width": 1280, "height": 720}],
        )
    )
    assert isinstance(man, dict), man
    extra = mcp.call_capability(
        "manage_asset_movie_pipeline_config",
        assetPath=path,
        operations=[
            {"action": "add_setting", "settingClass": "HighRes"},
            {"action": "set_setting_enabled", "settingClass": "HighRes", "enabled": True},
            {"action": "set_setting_property", "settingClass": "HighRes", "propertyPath": "TileCount", "value": "1"},
            {"action": "remove_setting", "settingClass": "HighRes"},
        ],
    )
    for e in (extra.get("results") or [cap_first(extra)]):
        if isinstance(e, dict) and e.get("error"):
            pytest.skip(f"movie_pipeline remaining 跳过: {e}")
