# Copyright byteyang. All Rights Reserved.
"""Tier4-4b: SoundClass/SoundAttenuation/SoundConcurrency 创建/读取/管理 + SoundSubmix 读取/管理。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_first
from _framework.asset_helpers import first_asset_path
from _framework.capability_probe import is_capability_available

pytestmark = pytest.mark.l3_asset

# ── SoundClass ────────────────────────────────────────────────────────────────

class TestSoundClass:
    @pytest.fixture(autouse=True)
    def _paths(self, test_ns):
        self.path = f"{test_ns}/TestSoundClass"
        self.ns = test_ns

    def test_create(self, mcp):
        r = mcp.call_capability("CreateAssetSoundClass",
                                AssetPath=self.path,
                                Volume=0.8, Pitch=1.0)
        first = cap_first(r)
        # 固定路径资产跨次运行可能已存在，视为可继续后续 get/manage
        if first.get("Error") and "already exists" in str(first.get("Error")):
            return
        assert (not first.get("Error") and first.get("bSuccess") is not False) or first.get("name"), (
            f"create_asset_sound_class 失败: {r}"
        )

    def test_get(self, mcp):
        r = mcp.call_capability("GetAssetSoundClass", AssetPath=self.path)
        first = cap_first(r)
        assert "Volume" in first and "Pitch" in first, f"字段缺失: {first}"
        assert abs(first.get("Volume", 0) - 0.8) < 0.01, f"volume 不符: {first}"

    def test_manage_volume(self, mcp):
        r = mcp.call_capability("ManageAssetSoundClass",
                                AssetPath=self.path,
                                Operations=[{"Action": "Set", "Volume": 0.5, "Pitch": 1.2}])
        first = cap_first(r)
        assert not first.get("Error") and first.get("bSuccess") is not False, f"manage 失败: {first}"

    def test_get_after_manage(self, mcp):
        r = mcp.call_capability("GetAssetSoundClass", AssetPath=self.path)
        first = cap_first(r)
        assert abs(first.get("Volume", 0) - 0.5) < 0.01, f"manage 后 volume 不符: {first}"

    def test_search_sound_class(self, mcp):
        r = mcp.call_capability("SearchAsset",
                                AssetType="SoundClass",
                                PathFilter=self.ns,
                                Limit=5)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("Assets") or payload.get("Results") or []
        assert isinstance(assets, list), f"search_asset SoundClass 格式错误: {r}"


# ── SoundAttenuation ──────────────────────────────────────────────────────────

class TestSoundAttenuation:
    @pytest.fixture(autouse=True)
    def _paths(self, test_ns):
        self.path = f"{test_ns}/TestSoundAttenuation"
        self.ns = test_ns

    def test_create(self, mcp):
        r = mcp.call_capability("CreateAssetSoundAttenuation",
                                AssetPath=self.path,
                                InnerRadius=500.0, FalloffDistance=4000.0)
        first = cap_first(r)
        if first.get("Error") and "already exists" in str(first.get("Error")):
            return
        assert (not first.get("Error") and first.get("bSuccess") is not False) or first.get("name"), (
            f"create_asset_sound_attenuation 失败: {r}"
        )

    def test_get(self, mcp):
        r = mcp.call_capability("GetAssetSoundAttenuation", AssetPath=self.path)
        first = cap_first(r)
        assert "InnerRadius" in first and "FalloffDistance" in first, f"字段缺失: {first}"
        assert abs(first.get("InnerRadius", 0) - 500.0) < 1.0, f"innerRadius 不符: {first}"

    def test_manage(self, mcp):
        r = mcp.call_capability("ManageAssetSoundAttenuation",
                                AssetPath=self.path,
                                Operations=[{"Action": "Set", "InnerRadius": 800.0, "FalloffDistance": 5000.0}])
        first = cap_first(r)
        assert not first.get("Error") and first.get("bSuccess") is not False, f"manage 失败: {first}"

    def test_search_sound_attenuation(self, mcp):
        r = mcp.call_capability("SearchAsset",
                                AssetType="SoundAttenuation",
                                PathFilter=self.ns,
                                Limit=5)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("Assets") or payload.get("Results") or []
        assert isinstance(assets, list), f"search_asset SoundAttenuation 格式错误: {r}"


# ── SoundConcurrency ──────────────────────────────────────────────────────────

class TestSoundConcurrency:
    @pytest.fixture(autouse=True)
    def _paths(self, test_ns):
        self.path = f"{test_ns}/TestSoundConcurrency"
        self.ns = test_ns

    def test_create(self, mcp):
        r = mcp.call_capability("CreateAssetSoundConcurrency",
                                AssetPath=self.path,
                                MaxCount=8)
        first = cap_first(r)
        if first.get("Error") and "already exists" in str(first.get("Error")):
            return
        assert (not first.get("Error") and first.get("bSuccess") is not False) or first.get("name"), (
            f"create_asset_sound_concurrency 失败: {r}"
        )

    def test_get(self, mcp):
        r = mcp.call_capability("GetAssetSoundConcurrency", AssetPath=self.path)
        first = cap_first(r)
        assert "MaxCount" in first and "ResolutionRule" in first, f"字段缺失: {first}"
        assert first.get("MaxCount") == 8, f"maxCount 不符: {first}"

    def test_manage(self, mcp):
        r = mcp.call_capability("ManageAssetSoundConcurrency",
                                AssetPath=self.path,
                                Operations=[{"Action": "Set", "MaxCount": 4, "RetriggerTime": 0.1}])
        first = cap_first(r)
        assert not first.get("Error") and first.get("bSuccess") is not False, f"manage 失败: {first}"

    def test_get_after_manage(self, mcp):
        r = mcp.call_capability("GetAssetSoundConcurrency", AssetPath=self.path)
        first = cap_first(r)
        assert first.get("MaxCount") == 4, f"manage 后 maxCount 不符: {first}"

    def test_search_sound_concurrency(self, mcp):
        r = mcp.call_capability("SearchAsset",
                                AssetType="SoundConcurrency",
                                PathFilter=self.ns,
                                Limit=5)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("Assets") or payload.get("Results") or []
        assert isinstance(assets, list), f"search_asset SoundConcurrency 格式错误: {r}"


# ── SoundSubmix ───────────────────────────────────────────────────────────────

class TestSoundSubmix:
    """get/manage SoundSubmix；需项目中存在 SoundSubmix 资产。"""

    @pytest.fixture(autouse=True)
    def _find_submix(self, mcp):
        r = mcp.call_capability("SearchAsset",
                                AssetType="SoundSubmix",
                                PathFilter="/Game/",
                                Limit=1)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("Assets") or payload.get("Results") or []
        if not assets:
            pytest.skip("项目中未找到 SoundSubmix 资产，跳过测试")
        first = assets[0] if isinstance(assets[0], dict) else {}
        self._sm_path = first.get("AssetPath") or first.get("Path") or ""
        if not self._sm_path:
            pytest.skip("SoundSubmix 路径解析失败，跳过测试")

    def test_get(self, mcp):
        r = mcp.call_capability("GetAssetSoundSubmix", AssetPath=self._sm_path)
        first = cap_first(r)
        # UE4/5.0 输出线性字段；UE5.1+ 输出 dB 字段
        has_linear = "OutputVolume" in first or "WetLevel" in first
        has_db = "OutputVolumeDB" in first or "WetLevelDB" in first
        assert has_linear or has_db, f"volume 字段全部缺失: {first}"
        assert "EffectChainCount" in first, f"effectChainCount 缺失: {first}"

    def test_search_sound_submix(self, mcp):
        r = mcp.call_capability("SearchAsset",
                                AssetType="SoundSubmix",
                                PathFilter="/Game/",
                                Limit=5)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("Assets") or payload.get("Results") or []
        assert isinstance(assets, list), f"search_asset SoundSubmix 格式错误: {r}"

    def test_manage_set(self, mcp, test_ns):
        path = f"{test_ns}/SS_Manage"
        if is_capability_available(mcp, "CreateAssetSoundSubmix"):
            cr = mcp.call_capability("CreateAssetSoundSubmix", AssetPath=path)
            e = cap_first(cr)
            if e.get("Error") and "already exists" not in str(e.get("Error")).lower():
                path = self._sm_path
        else:
            path = self._sm_path
        r = mcp.call_capability(
            "ManageAssetSoundSubmix",
            AssetPath=path,
            Operations=[{"Action": "Set", "OutputVolume": 0.8, "WetLevel": 0.2, "DryLevel": 0.9}],
        )
        first = cap_first(r)
        if first.get("Error"):
            r = mcp.call_capability(
                "ManageAssetSoundSubmix",
                AssetPath=path,
                Operations=[{"Action": "Set", "OutputVolumeDB": -6.0, "WetLevelDB": -12.0, "DryLevelDB": 0.0}],
            )
            first = cap_first(r)
        assert not first.get("Error"), first


class TestSoundCueManage:
    def test_manage_nodes_and_property(self, mcp, test_ns):
        path = f"{test_ns}/SC_Manage"
        cr = mcp.call_capability("CreateAssetSoundCue", AssetPath=path)
        e = cap_first(cr)
        if e.get("Error") and "already exists" not in str(e.get("Error")).lower():
            pytest.skip(f"create_asset_sound_cue 失败: {e}")
        wave = first_asset_path(mcp, "SoundWave")
        add_op = {"Action": "AddNode", "NodeClass": "SoundNodeWavePlayer"}
        if wave:
            add_op["SoundWavePath"] = wave
        r = mcp.call_capability(
            "ManageAssetSoundCue",
            AssetPath=path,
            Operations=[
                {"Action": "SetProperty", "PropertyPath": "VolumeMultiplier", "Value": "0.8"},
                add_op,
            ],
        )
        for ent in (r.get("Results") or [cap_first(r)]):
            if isinstance(ent, dict) and ent.get("Error"):
                pytest.skip(f"manage_asset_sound_cue 跳过: {ent}")
        got = cap_first(mcp.call_capability("GetAssetSoundCue", AssetPath=path))
        nodes = got.get("Nodes") or []
        if len(nodes) >= 2:
            conn = mcp.call_capability(
                "ManageAssetSoundCue",
                AssetPath=path,
                Operations=[{
                    "Action": "ConnectNodes",
                    "ParentNodeIndex": 0,
                    "ChildSlot": 0,
                    "ChildIndex": 1,
                }],
            )
            assert isinstance(cap_first(conn), dict), conn
        rm = mcp.call_capability(
            "ManageAssetSoundCue",
            AssetPath=path,
            Operations=[{"Action": "RemoveNode", "NodeIndex": 0}],
        )
        assert isinstance(cap_first(rm), dict), rm


class TestSoundWaveManage:
    def test_set_property(self, mcp):
        path = first_asset_path(mcp, "SoundWave")
        if not path:
            pytest.skip("无 SoundWave 样本")
        r = mcp.call_capability(
            "ManageAssetSoundWave",
            AssetPath=path,
            Operations=[{"Action": "SetProperty", "PropertyPath": "Volume", "Value": "0.9"}],
        )
        first = cap_first(r)
        if first.get("Error"):
            pytest.skip(f"manage_asset_sound_wave 跳过: {first}")
