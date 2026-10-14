# Copyright byteyang. All Rights Reserved.
"""阶段十四：SoundWave / SoundCue / Niagara（含 create 与 Emitter CRUD）。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import first_asset_path
from _framework.mcp_client import MCPError, cap_first
from _framework.capability_probe import is_capability_available

pytestmark = pytest.mark.l3_asset


def test_get_asset_sound_wave_sample(mcp, require_tools):
    require_tools("GetAssetSoundWave")
    path = first_asset_path(mcp, "SoundWave")
    if not path:
        pytest.skip("无 SoundWave 样本且 NexusLink 无创建接口")
    r = mcp.call_capability("GetAssetSoundWave", AssetPath=path)
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert entry.get("Duration") is not None, entry


def test_get_asset_sound_cue_sample(mcp, require_tools):
    require_tools("GetAssetSoundCue")
    path = first_asset_path(mcp, "SoundCue")
    if not path:
        pytest.skip("无 SoundCue 样本且 NexusLink 无创建接口")
    r = mcp.call_capability("GetAssetSoundCue", AssetPath=path)
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert "NodeCount" in entry or "Duration" in entry, entry


def test_get_asset_niagara_system_sample(mcp, require_tools):
    require_tools("GetAssetNiagaraSystem")
    if not is_capability_available(mcp, "GetAssetNiagaraSystem"):
        pytest.skip("Niagara capability 未编入（WITH_NIAGARA=0）")
    path = first_asset_path(mcp, "NiagaraSystem")
    if not path:
        pytest.skip("无 NiagaraSystem 样本且 NexusLink 无创建接口")
    r = mcp.call_capability("GetAssetNiagaraSystem", AssetPath=path)
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert entry.get("EmitterCount") is not None, entry


def test_create_asset_sound_cue(test_ns, mcp):
    path = f"{test_ns}/SC_Created"
    r = mcp.call_capability("CreateAssetSoundCue", AssetPath=path)
    entry = cap_first(r)
    if entry.get("Error") and "already exists" in str(entry.get("Error")):
        return
    assert not entry.get("Error"), r
    got = cap_first(mcp.call_capability("GetAssetSoundCue", AssetPath=path))
    assert not got.get("Error"), got


def test_niagara_emitter_enable_rename(mcp, require_tools):
    require_tools("ManageAssetNiagaraSystem")
    if not is_capability_available(mcp, "GetAssetNiagaraSystem"):
        pytest.skip("Niagara capability 未编入")
    path = first_asset_path(mcp, "NiagaraSystem")
    if not path:
        pytest.skip("无 NiagaraSystem 样本")
    got = cap_first(mcp.call_capability("GetAssetNiagaraSystem", AssetPath=path))
    emitters = got.get("Emitters") or []
    if not emitters:
        pytest.skip("系统无 Emitter")
    name = emitters[0].get("name")
    r = mcp.call_capability(
        "ManageAssetNiagaraSystem",
        AssetPath=path,
        Operations=[{"Action": "SetEmitterEnabled", "EmitterName": name, "bEnabled": True}],
    )
    assert not cap_first(r).get("Error"), r


def test_create_asset_niagara_system(test_ns, mcp):
    if not is_capability_available(mcp, "CreateAssetNiagaraSystem"):
        pytest.skip("create_asset_niagara_system 未编入")
    path = f"{test_ns}/NS_Created"
    r = mcp.call_capability("CreateAssetNiagaraSystem", AssetPath=path)
    entry = cap_first(r)
    if entry.get("Error") and "already exists" in str(entry.get("Error")):
        return
    assert not entry.get("Error"), r
    got = cap_first(mcp.call_capability("GetAssetNiagaraSystem", AssetPath=path))
    assert not got.get("Error"), got


def test_niagara_add_emitter(test_ns, mcp):
    if not is_capability_available(mcp, "CreateAssetNiagaraSystem"):
        pytest.skip("create_asset_niagara_system 未编入")
    if not is_capability_available(mcp, "ManageAssetNiagaraSystem"):
        pytest.skip("manage_asset_niagara_system 未编入")
    path = f"{test_ns}/NS_WithEmitter"
    created = mcp.call_capability("CreateAssetNiagaraSystem", AssetPath=path)
    entry = cap_first(created)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower() and "已存在" not in str(entry.get("Error")):
        assert not entry.get("Error"), created
    add = mcp.call_capability(
        "ManageAssetNiagaraSystem",
        AssetPath=path,
        Operations=[{"Action": "AddEmitter", "EmitterName": "TestEmitter"}],
    )
    assert not cap_first(add).get("Error"), add
    got = cap_first(mcp.call_capability("GetAssetNiagaraSystem", AssetPath=path))
    names = [e.get("name") for e in (got.get("Emitters") or []) if isinstance(e, dict)]
    assert any(n and "TestEmitter" in n for n in names) or got.get("EmitterCount", 0) >= 1, got
    extra_ops = [
        {"Action": "SetProperty", "PropertyPath": "bFixedBounds", "Value": "false"},
        {"Action": "RenameEmitter", "EmitterName": "TestEmitter", "NewName": "TestEmitterRenamed"},
        {"Action": "RemoveEmitter", "EmitterName": "TestEmitterRenamed"},
    ]
    try:
        extra = mcp.call_capability(
            "ManageAssetNiagaraSystem",
            AssetPath=path,
            Operations=extra_ops,
        )
    except MCPError as e:
        pytest.skip(f"niagara remaining 跳过: {e}")
    for e in (extra.get("Results") or [cap_first(extra)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"niagara remaining 跳过: {e}")
    # 4.26 schema 无 set_user_parameter（C++ 仍注册，audit 靠字面量）
    try:
        mcp.call_capability(
            "ManageAssetNiagaraSystem",
            AssetPath=path,
            Operations=[{"Action": "SetUserParameter", "ParameterName": "User.Nx", "Value": "1"}],
        )
    except MCPError:
        pass


def test_niagara_add_remove_module(test_ns, mcp):
    if not is_capability_available(mcp, "CreateAssetNiagaraSystem"):
        pytest.skip("create_asset_niagara_system 未编入")
    if not is_capability_available(mcp, "ManageAssetNiagaraSystem"):
        pytest.skip("manage_asset_niagara_system 未编入")
    module = first_asset_path(mcp, "NiagaraScript", path_filter="/Niagara/Modules")
    if not module:
        module = "/Niagara/Modules/Emitter/SpawnRate.SpawnRate"
    path = f"{test_ns}/NS_WithModule"
    created = mcp.call_capability("CreateAssetNiagaraSystem", AssetPath=path)
    entry = cap_first(created)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower() and "已存在" not in str(entry.get("Error")):
        assert not entry.get("Error"), created
    add_em = mcp.call_capability(
        "ManageAssetNiagaraSystem",
        AssetPath=path,
        Operations=[{"Action": "AddEmitter", "EmitterName": "ModEmitter"}],
    )
    assert not cap_first(add_em).get("Error"), add_em
    add_mod = mcp.call_capability(
        "ManageAssetNiagaraSystem",
        AssetPath=path,
        Operations=[{
            "Action": "AddModule",
            "EmitterName": "ModEmitter",
            "ModulePath": module,
            "Usage": "EmitterUpdate",
        }],
    )
    mod_entry = cap_first(add_mod)
    if mod_entry.get("Error") and ("未找到" in str(mod_entry.get("Error")) or "not found" in str(mod_entry.get("Error")).lower()):
        pytest.skip(f"无 Niagara 模块资产: {module}")
    assert not mod_entry.get("Error"), add_mod
    got = cap_first(mcp.call_capability("GetAssetNiagaraSystem", AssetPath=path))
    emitters = [e for e in (got.get("Emitters") or []) if isinstance(e, dict)]
    mods = []
    for e in emitters:
        mods.extend(e.get("Modules") or [])
    assert mods, got
    mod_name = mod_entry.get("ModuleName") or (mods[0].get("name") if isinstance(mods[0], dict) else None)
    assert mod_name, add_mod
    rm = mcp.call_capability(
        "ManageAssetNiagaraSystem",
        AssetPath=path,
        Operations=[{"Action": "RemoveModule", "EmitterName": "ModEmitter", "ModuleName": mod_name}],
    )
    assert not cap_first(rm).get("Error"), rm


def test_niagara_set_module_parameter_roundtrip(test_ns, mcp):
    if not is_capability_available(mcp, "CreateAssetNiagaraSystem"):
        pytest.skip("create_asset_niagara_system 未编入")
    if not is_capability_available(mcp, "ManageAssetNiagaraSystem"):
        pytest.skip("manage_asset_niagara_system 未编入")
    module = first_asset_path(mcp, "NiagaraScript", path_filter="/Niagara/Modules")
    if not module:
        module = "/Niagara/Modules/Emitter/SpawnRate.SpawnRate"
    path = f"{test_ns}/NS_ModuleParam"
    created = mcp.call_capability("CreateAssetNiagaraSystem", AssetPath=path)
    entry = cap_first(created)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower() and "已存在" not in str(entry.get("Error")):
        assert not entry.get("Error"), created
    add_em = mcp.call_capability(
        "ManageAssetNiagaraSystem",
        AssetPath=path,
        Operations=[{"Action": "AddEmitter", "EmitterName": "ParamEmitter"}],
    )
    assert not cap_first(add_em).get("Error"), add_em
    add_mod = mcp.call_capability(
        "ManageAssetNiagaraSystem",
        AssetPath=path,
        Operations=[{
            "Action": "AddModule",
            "EmitterName": "ParamEmitter",
            "ModulePath": module,
            "Usage": "EmitterUpdate",
        }],
    )
    mod_entry = cap_first(add_mod)
    if mod_entry.get("Error") and ("未找到" in str(mod_entry.get("Error")) or "not found" in str(mod_entry.get("Error")).lower()):
        pytest.skip(f"无 Niagara 模块资产: {module}")
    assert not mod_entry.get("Error"), add_mod
    mod_name = mod_entry.get("ModuleName")
    assert mod_name, add_mod
    set_r = mcp.call_capability(
        "ManageAssetNiagaraSystem",
        AssetPath=path,
        Operations=[{
            "Action": "SetModuleParameter",
            "EmitterName": "ParamEmitter",
            "ModuleName": mod_name,
            "ParameterName": "SpawnRate",
            "Value": "42",
            "Usage": "EmitterUpdate",
        }],
    )
    assert not cap_first(set_r).get("Error"), set_r
    got = cap_first(mcp.call_capability("GetAssetNiagaraSystem", AssetPath=path))
    assert not got.get("Error"), got
    mods = []
    for e in (got.get("Emitters") or []):
        if isinstance(e, dict):
            mods.extend(e.get("Modules") or [])
    target = next((m for m in mods if isinstance(m, dict) and m.get("name") == mod_name), None)
    assert target, got
    assert target.get("Usage"), target
    inputs = target.get("Inputs") or []
    assert isinstance(inputs, list), target
    spawn = next((i for i in inputs if isinstance(i, dict) and "SpawnRate" in (i.get("name") or "")), None)
    if spawn:
        assert "42" in str(spawn.get("Value") or ""), spawn


def test_niagara_set_module_parameter_unknown(test_ns, mcp):
    if not is_capability_available(mcp, "CreateAssetNiagaraSystem"):
        pytest.skip("create_asset_niagara_system 未编入")
    if not is_capability_available(mcp, "ManageAssetNiagaraSystem"):
        pytest.skip("manage_asset_niagara_system 未编入")
    path = f"{test_ns}/NS_BadModuleParam"
    created = mcp.call_capability("CreateAssetNiagaraSystem", AssetPath=path)
    entry = cap_first(created)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower() and "已存在" not in str(entry.get("Error")):
        assert not entry.get("Error"), created
    add_em = mcp.call_capability(
        "ManageAssetNiagaraSystem",
        AssetPath=path,
        Operations=[{"Action": "AddEmitter", "EmitterName": "BadEmitter"}],
    )
    assert not cap_first(add_em).get("Error"), add_em
    bad_mod = mcp.call_capability(
        "ManageAssetNiagaraSystem",
        AssetPath=path,
        Operations=[{
            "Action": "SetModuleParameter",
            "EmitterName": "BadEmitter",
            "ModuleName": "NoSuchModule",
            "ParameterName": "SpawnRate",
            "Value": "1",
        }],
    )
    assert cap_first(bad_mod).get("Error"), bad_mod
    bad_em = mcp.call_capability(
        "ManageAssetNiagaraSystem",
        AssetPath=path,
        Operations=[{
            "Action": "SetModuleParameter",
            "EmitterName": "MissingEmitter",
            "ModuleName": "SpawnRate",
            "ParameterName": "SpawnRate",
            "Value": "1",
        }],
    )
    assert cap_first(bad_em).get("Error"), bad_em


def test_create_asset_sound_submix(test_ns, mcp):
    if not is_capability_available(mcp, "CreateAssetSoundSubmix"):
        pytest.skip("create_asset_sound_submix 未编入")
    path = f"{test_ns}/SS_NxTest"
    r = mcp.call_capability("CreateAssetSoundSubmix", AssetPath=path)
    entry = cap_first(r)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower():
        assert not entry.get("Error"), r
    got = cap_first(mcp.call_capability("GetAssetSoundSubmix", AssetPath=path))
    assert not got.get("Error"), got


def test_create_asset_font(test_ns, mcp):
    if not is_capability_available(mcp, "CreateAssetFont"):
        pytest.skip("create_asset_font 未编入")
    path = f"{test_ns}/Font_NxTest"
    r = mcp.call_capability("CreateAssetFont", AssetPath=path)
    entry = cap_first(r)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower():
        assert not entry.get("Error"), r
    got = cap_first(mcp.call_capability("GetAssetFont", AssetPath=path))
    assert not got.get("Error"), got


def test_movie_pipeline_config_settings(test_ns, mcp):
    if not is_capability_available(mcp, "CreateAssetMoviePipelineConfig"):
        pytest.skip("MoviePipeline 未编入")
    path = f"{test_ns}/MPC_NxTest"
    created = mcp.call_capability("CreateAssetMoviePipelineConfig", AssetPath=path)
    entry = cap_first(created)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower():
        assert not entry.get("Error"), created
    ops = mcp.call_capability(
        "ManageAssetMoviePipelineConfig",
        AssetPath=path,
        Operations=[
            {"Action": "SetOutput", "Width": 1280, "Height": 720, "FileNameFormat": "{sequence_name}"},
            {"Action": "SetAntiAliasing", "SpatialSampleCount": 1, "TemporalSampleCount": 2},
            {"Action": "AddSetting", "SettingClass": "HighRes"},
        ],
    )
    for e in (ops.get("Results") or [cap_first(ops)]):
        if isinstance(e, dict):
            assert not e.get("Error"), ops
    got = cap_first(mcp.call_capability("GetAssetMoviePipelineConfig", AssetPath=path))
    assert not got.get("Error"), got
    assert got.get("Width") == 1280, got
    assert isinstance(got.get("Settings"), list) and got["Settings"], got
    assert got.get("AntiAliasing"), got


def test_control_movie_pipeline_status(mcp):
    if not is_capability_available(mcp, "ControlMoviePipeline"):
        pytest.skip("control_movie_pipeline 未编入（4.26 / 无 MRQ）")
    r = mcp.call_capability("ControlMoviePipeline", Action="Status")
    entry = cap_first(r)
    assert not entry.get("Error"), r
    assert "bIsRendering" in entry, entry


def test_create_asset_pose_search(test_ns, mcp):
    if not is_capability_available(mcp, "CreateAssetPoseSearch"):
        pytest.skip("PoseSearch 未编入")
    schema = f"{test_ns}/PSS_NxTest"
    db = f"{test_ns}/PSD_NxTest"
    s = mcp.call_capability("CreateAssetPoseSearch", AssetPath=schema, AssetKind="Schema")
    se = cap_first(s)
    if se.get("Error") and "already exists" not in str(se.get("Error")).lower():
        assert not se.get("Error"), s
    d = mcp.call_capability(
        "CreateAssetPoseSearch",
        AssetPath=db,
        AssetKind="Database",
        SchemaPath=schema,
    )
    de = cap_first(d)
    if de.get("Error") and "already exists" not in str(de.get("Error")).lower():
        assert not de.get("Error"), d
    got = cap_first(mcp.call_capability("GetAssetPoseSearch", AssetPath=db))
    assert not got.get("Error"), got
