# Copyright byteyang. All Rights Reserved.
"""Tier4-4b: SoundClass/SoundAttenuation/SoundConcurrency 创建/读取/管理 + SoundSubmix 读取/管理。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l3_asset

# ── 资产路径常量 ──────────────────────────────────────────────────────────────

_SOUND_CLASS_PATH       = "/Game/_NexusTest/T4/TestSoundClass"
_SOUND_ATTENUATION_PATH = "/Game/_NexusTest/T4/TestSoundAttenuation"
_SOUND_CONCURRENCY_PATH = "/Game/_NexusTest/T4/TestSoundConcurrency"


# ── SoundClass ────────────────────────────────────────────────────────────────

class TestSoundClass:
    def test_create(self, mcp):
        r = mcp.call_capability("create_asset_sound_class",
                                assetPath=_SOUND_CLASS_PATH,
                                volume=0.8, pitch=1.0)
        first = cap_first(r)
        # 固定路径资产跨次运行可能已存在，视为可继续后续 get/manage
        if first.get("error") and "already exists" in str(first.get("error")):
            return
        assert (not first.get("error") and first.get("success") is not False) or first.get("name"), (
            f"create_asset_sound_class 失败: {r}"
        )

    def test_get(self, mcp):
        r = mcp.call_capability("get_asset_sound_class", assetPath=_SOUND_CLASS_PATH)
        first = cap_first(r)
        assert "volume" in first and "pitch" in first, f"字段缺失: {first}"
        assert abs(first.get("volume", 0) - 0.8) < 0.01, f"volume 不符: {first}"

    def test_manage_volume(self, mcp):
        r = mcp.call_capability("manage_asset_sound_class",
                                assetPath=_SOUND_CLASS_PATH,
                                volume=0.5, pitch=1.2)
        first = cap_first(r)
        assert not first.get("error") and first.get("success") is not False, f"manage 失败: {first}"

    def test_get_after_manage(self, mcp):
        r = mcp.call_capability("get_asset_sound_class", assetPath=_SOUND_CLASS_PATH)
        first = cap_first(r)
        assert abs(first.get("volume", 0) - 0.5) < 0.01, f"manage 后 volume 不符: {first}"

    def test_search_sound_class(self, mcp):
        r = mcp.call_capability("search_asset",
                                assetType="SoundClass",
                                pathFilter="/Game/_NexusTest/",
                                limit=5)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("assets") or payload.get("results") or []
        assert isinstance(assets, list), f"search_asset SoundClass 格式错误: {r}"


# ── SoundAttenuation ──────────────────────────────────────────────────────────

class TestSoundAttenuation:
    def test_create(self, mcp):
        r = mcp.call_capability("create_asset_sound_attenuation",
                                assetPath=_SOUND_ATTENUATION_PATH,
                                innerRadius=500.0, falloffDistance=4000.0)
        first = cap_first(r)
        if first.get("error") and "already exists" in str(first.get("error")):
            return
        assert (not first.get("error") and first.get("success") is not False) or first.get("name"), (
            f"create_asset_sound_attenuation 失败: {r}"
        )

    def test_get(self, mcp):
        r = mcp.call_capability("get_asset_sound_attenuation", assetPath=_SOUND_ATTENUATION_PATH)
        first = cap_first(r)
        assert "innerRadius" in first and "falloffDistance" in first, f"字段缺失: {first}"
        assert abs(first.get("innerRadius", 0) - 500.0) < 1.0, f"innerRadius 不符: {first}"

    def test_manage(self, mcp):
        r = mcp.call_capability("manage_asset_sound_attenuation",
                                assetPath=_SOUND_ATTENUATION_PATH,
                                innerRadius=800.0, falloffDistance=5000.0)
        first = cap_first(r)
        assert not first.get("error") and first.get("success") is not False, f"manage 失败: {first}"

    def test_search_sound_attenuation(self, mcp):
        r = mcp.call_capability("search_asset",
                                assetType="SoundAttenuation",
                                pathFilter="/Game/_NexusTest/",
                                limit=5)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("assets") or payload.get("results") or []
        assert isinstance(assets, list), f"search_asset SoundAttenuation 格式错误: {r}"


# ── SoundConcurrency ──────────────────────────────────────────────────────────

class TestSoundConcurrency:
    def test_create(self, mcp):
        r = mcp.call_capability("create_asset_sound_concurrency",
                                assetPath=_SOUND_CONCURRENCY_PATH,
                                maxCount=8)
        first = cap_first(r)
        if first.get("error") and "already exists" in str(first.get("error")):
            return
        assert (not first.get("error") and first.get("success") is not False) or first.get("name"), (
            f"create_asset_sound_concurrency 失败: {r}"
        )

    def test_get(self, mcp):
        r = mcp.call_capability("get_asset_sound_concurrency", assetPath=_SOUND_CONCURRENCY_PATH)
        first = cap_first(r)
        assert "maxCount" in first and "resolutionRule" in first, f"字段缺失: {first}"
        assert first.get("maxCount") == 8, f"maxCount 不符: {first}"

    def test_manage(self, mcp):
        r = mcp.call_capability("manage_asset_sound_concurrency",
                                assetPath=_SOUND_CONCURRENCY_PATH,
                                maxCount=4, retriggerTime=0.1)
        first = cap_first(r)
        assert not first.get("error") and first.get("success") is not False, f"manage 失败: {first}"

    def test_get_after_manage(self, mcp):
        r = mcp.call_capability("get_asset_sound_concurrency", assetPath=_SOUND_CONCURRENCY_PATH)
        first = cap_first(r)
        assert first.get("maxCount") == 4, f"manage 后 maxCount 不符: {first}"

    def test_search_sound_concurrency(self, mcp):
        r = mcp.call_capability("search_asset",
                                assetType="SoundConcurrency",
                                pathFilter="/Game/_NexusTest/",
                                limit=5)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("assets") or payload.get("results") or []
        assert isinstance(assets, list), f"search_asset SoundConcurrency 格式错误: {r}"


# ── SoundSubmix ───────────────────────────────────────────────────────────────

class TestSoundSubmix:
    """get/manage SoundSubmix；需项目中存在 SoundSubmix 资产。"""

    @pytest.fixture(autouse=True)
    def _find_submix(self, mcp):
        r = mcp.call_capability("search_asset",
                                assetType="SoundSubmix",
                                pathFilter="/Game/",
                                limit=1)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("assets") or payload.get("results") or []
        if not assets:
            pytest.skip("项目中未找到 SoundSubmix 资产，跳过测试")
        first = assets[0] if isinstance(assets[0], dict) else {}
        self._sm_path = first.get("assetPath") or first.get("path") or ""
        if not self._sm_path:
            pytest.skip("SoundSubmix 路径解析失败，跳过测试")

    def test_get(self, mcp):
        r = mcp.call_capability("get_asset_sound_submix", assetPath=self._sm_path)
        first = cap_first(r)
        # UE4/5.0 输出线性字段；UE5.1+ 输出 dB 字段
        has_linear = "outputVolume" in first or "wetLevel" in first
        has_db = "outputVolumeDB" in first or "wetLevelDB" in first
        assert has_linear or has_db, f"volume 字段全部缺失: {first}"
        assert "effectChainCount" in first, f"effectChainCount 缺失: {first}"

    def test_search_sound_submix(self, mcp):
        r = mcp.call_capability("search_asset",
                                assetType="SoundSubmix",
                                pathFilter="/Game/",
                                limit=5)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("assets") or payload.get("results") or []
        assert isinstance(assets, list), f"search_asset SoundSubmix 格式错误: {r}"
