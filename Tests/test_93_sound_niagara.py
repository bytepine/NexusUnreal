# Copyright byteyang. All Rights Reserved.
"""阶段十四：SoundWave / SoundCue / Niagara 只读（P5）。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import first_asset_path
from _framework.mcp_client import cap_first
from _framework.capability_probe import is_capability_available

pytestmark = pytest.mark.l3_asset


def test_get_asset_sound_wave_sample(mcp, require_tools):
    require_tools("get_asset_sound_wave")
    path = first_asset_path(mcp, "SoundWave")
    if not path:
        pytest.skip("无 SoundWave 样本且 NexusLink 无创建接口")
    r = mcp.call_capability("get_asset_sound_wave", assetPath=path)
    entry = cap_first(r)
    assert not entry.get("error"), entry
    assert entry.get("duration") is not None, entry


def test_get_asset_sound_cue_sample(mcp, require_tools):
    require_tools("get_asset_sound_cue")
    path = first_asset_path(mcp, "SoundCue")
    if not path:
        pytest.skip("无 SoundCue 样本且 NexusLink 无创建接口")
    r = mcp.call_capability("get_asset_sound_cue", assetPath=path)
    entry = cap_first(r)
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
    entry = cap_first(r)
    assert not entry.get("error"), entry
    assert entry.get("emitterCount") is not None, entry


def test_create_asset_sound_cue(test_ns, mcp):
    path = f"{test_ns}/SC_Created"
    r = mcp.call_capability("create_asset_sound_cue", assetPath=path)
    entry = cap_first(r)
    if entry.get("error") and "already exists" in str(entry.get("error")):
        return
    assert not entry.get("error"), r
    got = cap_first(mcp.call_capability("get_asset_sound_cue", assetPath=path))
    assert not got.get("error"), got


def test_niagara_emitter_enable_rename(mcp, require_tools):
    require_tools("manage_asset_niagara_system")
    if not is_capability_available(mcp, "get_asset_niagara_system"):
        pytest.skip("Niagara capability 未编入")
    path = first_asset_path(mcp, "NiagaraSystem")
    if not path:
        pytest.skip("无 NiagaraSystem 样本")
    got = cap_first(mcp.call_capability("get_asset_niagara_system", assetPath=path))
    emitters = got.get("emitters") or []
    if not emitters:
        pytest.skip("系统无 Emitter")
    name = emitters[0].get("name")
    r = mcp.call_capability(
        "manage_asset_niagara_system",
        assetPath=path,
        operations=[{"action": "set_emitter_enabled", "emitterName": name, "enabled": True}],
    )
    assert not cap_first(r).get("error"), r


def test_create_asset_niagara_system(test_ns, mcp):
    if not is_capability_available(mcp, "create_asset_niagara_system"):
        pytest.skip("create_asset_niagara_system 未编入")
    path = f"{test_ns}/NS_Created"
    r = mcp.call_capability("create_asset_niagara_system", assetPath=path)
    entry = cap_first(r)
    if entry.get("error") and "already exists" in str(entry.get("error")):
        return
    assert not entry.get("error"), r
    got = cap_first(mcp.call_capability("get_asset_niagara_system", assetPath=path))
    assert not got.get("error"), got
