# Copyright byteyang. All Rights Reserved.
"""阶段十四：SoundWave / SoundCue / Niagara 只读（P5）。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import MCPError

pytestmark = pytest.mark.l3_asset


def _first_asset_path(mcp, asset_type: str) -> str | None:
    try:
        listing = mcp.call_capability(
            "search_asset",
            assetType=asset_type,
            pathFilter="/Game/",
            limit=5,
        )
    except MCPError:
        return None
    assets = listing.get("assets") or []
    if not assets:
        return None
    row = assets[0]
    return row.get("assetPath") or row.get("path")


def test_get_asset_sound_wave_sample(mcp, require_tools):
    require_tools("get_asset_sound_wave")
    path = _first_asset_path(mcp, "SoundWave")
    if not path:
        pytest.skip("项目中无 SoundWave 样本")
    r = mcp.call_capability("get_asset_sound_wave", assetPath=path)
    entry = (r.get("results") or [r])[0]
    assert not entry.get("error"), entry
    assert entry.get("duration") is not None, entry


def test_get_asset_sound_cue_sample(mcp, require_tools):
    require_tools("get_asset_sound_cue")
    path = _first_asset_path(mcp, "SoundCue")
    if not path:
        pytest.skip("项目中无 SoundCue 样本")
    r = mcp.call_capability("get_asset_sound_cue", assetPath=path)
    entry = (r.get("results") or [r])[0]
    assert not entry.get("error"), entry
    assert "nodeCount" in entry or "duration" in entry, entry


def test_get_asset_niagara_system_sample(mcp, require_tools):
    require_tools("get_asset_niagara_system")
    path = _first_asset_path(mcp, "NiagaraSystem")
    if not path:
        pytest.skip("项目中无 NiagaraSystem 样本或未启用 WITH_NIAGARA")
    r = mcp.call_capability("get_asset_niagara_system", assetPath=path)
    entry = (r.get("results") or [r])[0]
    assert not entry.get("error"), entry
    assert entry.get("emitterCount") is not None, entry
