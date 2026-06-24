# Copyright byteyang. All Rights Reserved.
"""阶段十四：SoundWave / SoundCue / Niagara 只读（P5）。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import first_asset_path
from _framework.capability_probe import is_capability_available

pytestmark = pytest.mark.l3_asset


def test_get_asset_sound_wave_sample(mcp, require_tools):
    require_tools("get_asset_sound_wave")
    path = first_asset_path(mcp, "SoundWave")
    if not path:
        pytest.skip("无 SoundWave 样本且 NexusLink 无创建接口")
    r = mcp.call_capability("get_asset_sound_wave", assetPath=path)
    entry = (r.get("results") or [r])[0]
    assert not entry.get("error"), entry
    assert entry.get("duration") is not None, entry


def test_get_asset_sound_cue_sample(mcp, require_tools):
    require_tools("get_asset_sound_cue")
    path = first_asset_path(mcp, "SoundCue")
    if not path:
        pytest.skip("无 SoundCue 样本且 NexusLink 无创建接口")
    r = mcp.call_capability("get_asset_sound_cue", assetPath=path)
    entry = (r.get("results") or [r])[0]
    assert not entry.get("error"), entry
    assert "nodeCount" in entry or "duration" in entry, entry


def test_get_asset_niagara_system_sample(mcp, require_tools):
    require_tools("get_asset_niagara_system")
    if not is_capability_available(mcp, "get_asset_niagara_system"):
        pytest.skip("Niagara capability 未编入（WITH_NIAGARA=0）")
    path = first_asset_path(mcp, "NiagaraSystem")
    if not path:
        pytest.skip("无 NiagaraSystem 样本且 NexusLink 无创建接口")
    r = mcp.call_capability("get_asset_niagara_system", assetPath=path)
    entry = (r.get("results") or [r])[0]
    assert not entry.get("error"), entry
    assert entry.get("emitterCount") is not None, entry
