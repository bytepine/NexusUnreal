# Copyright byteyang. All Rights Reserved.
"""阶段十四：SoundWave / SoundCue / Niagara（含 create 与 Emitter CRUD）。"""

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


def test_niagara_add_emitter(test_ns, mcp):
    if not is_capability_available(mcp, "create_asset_niagara_system"):
        pytest.skip("create_asset_niagara_system 未编入")
    if not is_capability_available(mcp, "manage_asset_niagara_system"):
        pytest.skip("manage_asset_niagara_system 未编入")
    path = f"{test_ns}/NS_WithEmitter"
    created = mcp.call_capability("create_asset_niagara_system", assetPath=path)
    entry = cap_first(created)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower() and "已存在" not in str(entry.get("error")):
        assert not entry.get("error"), created
    add = mcp.call_capability(
        "manage_asset_niagara_system",
        assetPath=path,
        operations=[{"action": "add_emitter", "emitterName": "TestEmitter"}],
    )
    assert not cap_first(add).get("error"), add
    got = cap_first(mcp.call_capability("get_asset_niagara_system", assetPath=path))
    names = [e.get("name") for e in (got.get("emitters") or []) if isinstance(e, dict)]
    assert any(n and "TestEmitter" in n for n in names) or got.get("emitterCount", 0) >= 1, got


def test_niagara_add_remove_module(test_ns, mcp):
    if not is_capability_available(mcp, "create_asset_niagara_system"):
        pytest.skip("create_asset_niagara_system 未编入")
    if not is_capability_available(mcp, "manage_asset_niagara_system"):
        pytest.skip("manage_asset_niagara_system 未编入")
    module = first_asset_path(mcp, "NiagaraScript", path_filter="/Niagara/Modules")
    if not module:
        module = "/Niagara/Modules/Emitter/SpawnRate.SpawnRate"
    path = f"{test_ns}/NS_WithModule"
    created = mcp.call_capability("create_asset_niagara_system", assetPath=path)
    entry = cap_first(created)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower() and "已存在" not in str(entry.get("error")):
        assert not entry.get("error"), created
    add_em = mcp.call_capability(
        "manage_asset_niagara_system",
        assetPath=path,
        operations=[{"action": "add_emitter", "emitterName": "ModEmitter"}],
    )
    assert not cap_first(add_em).get("error"), add_em
    add_mod = mcp.call_capability(
        "manage_asset_niagara_system",
        assetPath=path,
        operations=[{
            "action": "add_module",
            "emitterName": "ModEmitter",
            "modulePath": module,
            "usage": "EmitterUpdate",
        }],
    )
    mod_entry = cap_first(add_mod)
    if mod_entry.get("error") and ("未找到" in str(mod_entry.get("error")) or "not found" in str(mod_entry.get("error")).lower()):
        pytest.skip(f"无 Niagara 模块资产: {module}")
    assert not mod_entry.get("error"), add_mod
    got = cap_first(mcp.call_capability("get_asset_niagara_system", assetPath=path))
    emitters = [e for e in (got.get("emitters") or []) if isinstance(e, dict)]
    mods = []
    for e in emitters:
        mods.extend(e.get("modules") or [])
    assert mods, got
    mod_name = mod_entry.get("moduleName") or (mods[0].get("name") if isinstance(mods[0], dict) else None)
    assert mod_name, add_mod
    rm = mcp.call_capability(
        "manage_asset_niagara_system",
        assetPath=path,
        operations=[{"action": "remove_module", "emitterName": "ModEmitter", "moduleName": mod_name}],
    )
    assert not cap_first(rm).get("error"), rm


def test_niagara_set_module_parameter_roundtrip(test_ns, mcp):
    if not is_capability_available(mcp, "create_asset_niagara_system"):
        pytest.skip("create_asset_niagara_system 未编入")
    if not is_capability_available(mcp, "manage_asset_niagara_system"):
        pytest.skip("manage_asset_niagara_system 未编入")
    module = first_asset_path(mcp, "NiagaraScript", path_filter="/Niagara/Modules")
    if not module:
        module = "/Niagara/Modules/Emitter/SpawnRate.SpawnRate"
    path = f"{test_ns}/NS_ModuleParam"
    created = mcp.call_capability("create_asset_niagara_system", assetPath=path)
    entry = cap_first(created)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower() and "已存在" not in str(entry.get("error")):
        assert not entry.get("error"), created
    add_em = mcp.call_capability(
        "manage_asset_niagara_system",
        assetPath=path,
        operations=[{"action": "add_emitter", "emitterName": "ParamEmitter"}],
    )
    assert not cap_first(add_em).get("error"), add_em
    add_mod = mcp.call_capability(
        "manage_asset_niagara_system",
        assetPath=path,
        operations=[{
            "action": "add_module",
            "emitterName": "ParamEmitter",
            "modulePath": module,
            "usage": "EmitterUpdate",
        }],
    )
    mod_entry = cap_first(add_mod)
    if mod_entry.get("error") and ("未找到" in str(mod_entry.get("error")) or "not found" in str(mod_entry.get("error")).lower()):
        pytest.skip(f"无 Niagara 模块资产: {module}")
    assert not mod_entry.get("error"), add_mod
    mod_name = mod_entry.get("moduleName")
    assert mod_name, add_mod
    set_r = mcp.call_capability(
        "manage_asset_niagara_system",
        assetPath=path,
        operations=[{
            "action": "set_module_parameter",
            "emitterName": "ParamEmitter",
            "moduleName": mod_name,
            "parameterName": "SpawnRate",
            "value": "42",
            "usage": "EmitterUpdate",
        }],
    )
    assert not cap_first(set_r).get("error"), set_r
    got = cap_first(mcp.call_capability("get_asset_niagara_system", assetPath=path))
    assert not got.get("error"), got
    mods = []
    for e in (got.get("emitters") or []):
        if isinstance(e, dict):
            mods.extend(e.get("modules") or [])
    target = next((m for m in mods if isinstance(m, dict) and m.get("name") == mod_name), None)
    assert target, got
    assert target.get("usage"), target
    inputs = target.get("inputs") or []
    assert isinstance(inputs, list), target
    spawn = next((i for i in inputs if isinstance(i, dict) and "SpawnRate" in (i.get("name") or "")), None)
    if spawn:
        assert "42" in str(spawn.get("value") or ""), spawn


def test_niagara_set_module_parameter_unknown(test_ns, mcp):
    if not is_capability_available(mcp, "create_asset_niagara_system"):
        pytest.skip("create_asset_niagara_system 未编入")
    if not is_capability_available(mcp, "manage_asset_niagara_system"):
        pytest.skip("manage_asset_niagara_system 未编入")
    path = f"{test_ns}/NS_BadModuleParam"
    created = mcp.call_capability("create_asset_niagara_system", assetPath=path)
    entry = cap_first(created)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower() and "已存在" not in str(entry.get("error")):
        assert not entry.get("error"), created
    add_em = mcp.call_capability(
        "manage_asset_niagara_system",
        assetPath=path,
        operations=[{"action": "add_emitter", "emitterName": "BadEmitter"}],
    )
    assert not cap_first(add_em).get("error"), add_em
    bad_mod = mcp.call_capability(
        "manage_asset_niagara_system",
        assetPath=path,
        operations=[{
            "action": "set_module_parameter",
            "emitterName": "BadEmitter",
            "moduleName": "NoSuchModule",
            "parameterName": "SpawnRate",
            "value": "1",
        }],
    )
    assert cap_first(bad_mod).get("error"), bad_mod
    bad_em = mcp.call_capability(
        "manage_asset_niagara_system",
        assetPath=path,
        operations=[{
            "action": "set_module_parameter",
            "emitterName": "MissingEmitter",
            "moduleName": "SpawnRate",
            "parameterName": "SpawnRate",
            "value": "1",
        }],
    )
    assert cap_first(bad_em).get("error"), bad_em


def test_create_asset_sound_submix(test_ns, mcp):
    if not is_capability_available(mcp, "create_asset_sound_submix"):
        pytest.skip("create_asset_sound_submix 未编入")
    path = f"{test_ns}/SS_NxTest"
    r = mcp.call_capability("create_asset_sound_submix", assetPath=path)
    entry = cap_first(r)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower():
        assert not entry.get("error"), r
    got = cap_first(mcp.call_capability("get_asset_sound_submix", assetPath=path))
    assert not got.get("error"), got


def test_create_asset_font(test_ns, mcp):
    if not is_capability_available(mcp, "create_asset_font"):
        pytest.skip("create_asset_font 未编入")
    path = f"{test_ns}/Font_NxTest"
    r = mcp.call_capability("create_asset_font", assetPath=path)
    entry = cap_first(r)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower():
        assert not entry.get("error"), r
    got = cap_first(mcp.call_capability("get_asset_font", assetPath=path))
    assert not got.get("error"), got


def test_movie_pipeline_config_settings(test_ns, mcp):
    if not is_capability_available(mcp, "create_asset_movie_pipeline_config"):
        pytest.skip("MoviePipeline 未编入")
    path = f"{test_ns}/MPC_NxTest"
    created = mcp.call_capability("create_asset_movie_pipeline_config", assetPath=path)
    entry = cap_first(created)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower():
        assert not entry.get("error"), created
    ops = mcp.call_capability(
        "manage_asset_movie_pipeline_config",
        assetPath=path,
        operations=[
            {"action": "set_output", "width": 1280, "height": 720, "fileNameFormat": "{sequence_name}"},
            {"action": "set_anti_aliasing", "spatialSampleCount": 1, "temporalSampleCount": 2},
            {"action": "add_setting", "settingClass": "HighRes"},
        ],
    )
    for e in (ops.get("results") or [cap_first(ops)]):
        if isinstance(e, dict):
            assert not e.get("error"), ops
    got = cap_first(mcp.call_capability("get_asset_movie_pipeline_config", assetPath=path))
    assert not got.get("error"), got
    assert got.get("width") == 1280, got
    assert isinstance(got.get("settings"), list) and got["settings"], got
    assert got.get("antiAliasing"), got


def test_control_movie_pipeline_status(mcp):
    if not is_capability_available(mcp, "control_movie_pipeline"):
        pytest.skip("control_movie_pipeline 未编入（4.26 / 无 MRQ）")
    r = mcp.call_capability("control_movie_pipeline", action="status")
    entry = cap_first(r)
    assert not entry.get("error"), r
    assert "isRendering" in entry, entry


def test_create_asset_pose_search(test_ns, mcp):
    if not is_capability_available(mcp, "create_asset_pose_search"):
        pytest.skip("PoseSearch 未编入")
    schema = f"{test_ns}/PSS_NxTest"
    db = f"{test_ns}/PSD_NxTest"
    s = mcp.call_capability("create_asset_pose_search", assetPath=schema, assetKind="Schema")
    se = cap_first(s)
    if se.get("error") and "already exists" not in str(se.get("error")).lower():
        assert not se.get("error"), s
    d = mcp.call_capability(
        "create_asset_pose_search",
        assetPath=db,
        assetKind="Database",
        schemaPath=schema,
    )
    de = cap_first(d)
    if de.get("error") and "already exists" not in str(de.get("error")).lower():
        assert not de.get("error"), d
    got = cap_first(mcp.call_capability("get_asset_pose_search", assetPath=db))
    assert not got.get("error"), got
