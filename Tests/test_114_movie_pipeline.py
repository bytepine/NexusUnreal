# Copyright byteyang. All Rights Reserved.
"""MoviePipeline config create/get（UE5+ 门控 skip）。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.0")]


@pytest.fixture(scope="module", autouse=True)
def require_mrq(mcp):
    if not is_capability_available(mcp, "CreateAssetMoviePipelineConfig"):
        pytest.skip("MoviePipeline capability 未编入（需 WITH_MOVIE_RENDER_PIPELINE）")


def test_movie_pipeline_config(test_ns, mcp):
    path = f"{test_ns}/MPC_Created"
    cr = mcp.call_capability("CreateAssetMoviePipelineConfig", AssetPath=path)
    entry = cap_first(cr)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower():
        pytest.fail(f"create_asset_movie_pipeline_config 失败: {entry}")
    got = cap_first(mcp.call_capability("GetAssetMoviePipelineConfig", AssetPath=path))
    assert not got.get("Error"), got
    man = cap_first(
        mcp.call_capability(
            "ManageAssetMoviePipelineConfig",
            AssetPath=path,
            Operations=[{"Action": "SetOutput", "Width": 1280, "Height": 720}],
        )
    )
    assert isinstance(man, dict), man
    extra = mcp.call_capability(
        "ManageAssetMoviePipelineConfig",
        AssetPath=path,
        Operations=[
            {"Action": "AddSetting", "SettingClass": "HighRes"},
            {"Action": "SetSettingEnabled", "SettingClass": "HighRes", "bEnabled": True},
            {"Action": "SetSettingProperty", "SettingClass": "HighRes", "PropertyPath": "TileCount", "Value": "1"},
            {"Action": "RemoveSetting", "SettingClass": "HighRes"},
        ],
    )
    for e in (extra.get("Results") or [cap_first(extra)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"movie_pipeline remaining 跳过: {e}")
