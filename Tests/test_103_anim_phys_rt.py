# Copyright byteyang. All Rights Reserved.
"""Tier4-4a-P1: AnimComposite 创建/读取/管理 + PhysicalMaterial 读取/管理 + RenderTarget 创建/读取/管理。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_entries, cap_first

pytestmark = pytest.mark.l3_asset

# ── 资产路径常量 ────────────────────────────────────────────────────────────────

_COMPOSITE_PATH   = "/Game/_NexusTest/T4/TestAnimComposite"
_RENDER_TARGET    = "/Game/_NexusTest/T4/TestRenderTarget"


# ── AnimComposite ──────────────────────────────────────────────────────────────

class TestAnimComposite:
    def test_create(self, mcp):
        r = mcp.call_capability("create_asset_anim_composite",
                                assetPath=_COMPOSITE_PATH)
        results = cap_entries(r)
        assert results, f"create_asset_anim_composite 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert (not first.get("error") and first.get("success") is not False) or first.get("name"), f"创建失败: {first}"

    def test_get_empty(self, mcp):
        r = mcp.call_capability("get_asset_anim_composite", assetPath=_COMPOSITE_PATH)
        results = cap_entries(r)
        assert results, f"get_asset_anim_composite 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert first.get("name"), f"缺少 name: {first}"
        assert first.get("segmentCount", -1) == 0, f"初始应为 0 segments: {first}"

    def test_manage_add_segment(self, mcp):
        """add_segment 无 animPath 时应能添加空占位片段。"""
        r = mcp.call_capability("manage_asset_anim_composite",
                                assetPath=_COMPOSITE_PATH,
                                operations=[{
                                    "action": "add_segment",
                                    "animStartTime": 0.0,
                                    "animEndTime": 1.0,
                                    "playRate": 1.0,
                                }])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("error") and e.get("success") is not False for e in results), \
            f"add_segment 无成功: {r}"

    def test_get_after_add(self, mcp):
        r = mcp.call_capability("get_asset_anim_composite", assetPath=_COMPOSITE_PATH)
        results = cap_entries(r)
        first = results[0] if results and isinstance(results[0], dict) else {}
        assert first.get("segmentCount", 0) >= 1, f"add_segment 后 segmentCount 应 ≥1: {first}"
        segs = first.get("segments", [])
        assert segs, "无 segments 数组"
        seg0 = segs[0] if isinstance(segs[0], dict) else {}
        assert "startPos" in seg0 and "playRate" in seg0, f"片段字段缺失: {seg0}"

    def test_manage_remove_segment(self, mcp):
        r = mcp.call_capability("manage_asset_anim_composite",
                                assetPath=_COMPOSITE_PATH,
                                operations=[{"action": "remove_segment", "segmentIndex": 0}])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("error") and e.get("success") is not False for e in results), \
            f"remove_segment 无成功: {r}"

    def test_search_anim_composite(self, mcp):
        r = mcp.call_capability("search_asset",
                                assetType="AnimComposite",
                                pathFilter="/Game/_NexusTest/",
                                limit=5)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("assets") or payload.get("results") or []
        assert isinstance(assets, list), f"search_asset AnimComposite 返回格式错误: {r}"


# ── PhysicalMaterial ───────────────────────────────────────────────────────────

class TestPhysicalMaterial:
    """get/manage PhysicalMaterial；需要项目中存在任一 PM 资产。"""

    @pytest.fixture(autouse=True)
    def _find_pm_path(self, mcp):
        """在项目中搜索一个可用的 PhysicalMaterial，找不到则 skip。"""
        r = mcp.call_capability("search_asset",
                                assetType="PhysicalMaterial",
                                pathFilter="/Game/",
                                limit=1)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("assets") or payload.get("results") or []
        if not assets:
            pytest.skip("项目中未找到 PhysicalMaterial 资产，跳过测试")
        first = assets[0] if isinstance(assets[0], dict) else {}
        self._pm_path = first.get("assetPath") or first.get("path") or ""
        if not self._pm_path:
            pytest.skip("PhysicalMaterial 路径解析失败，跳过测试")

    def test_get(self, mcp):
        r = mcp.call_capability("get_asset_physical_material", assetPath=self._pm_path)
        results = cap_entries(r)
        assert results, f"get_asset_physical_material 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert "friction" in first and "restitution" in first, f"字段缺失: {first}"

    def test_manage_friction(self, mcp):
        r_before = mcp.call_capability("get_asset_physical_material", assetPath=self._pm_path)
        original = (cap_first(r_before)).get("friction", 0.5)

        new_val = round(original + 0.01, 4) if original < 0.99 else round(original - 0.01, 4)
        r = mcp.call_capability("manage_asset_physical_material",
                                assetPath=self._pm_path,
                                friction=new_val)
        results = cap_entries(r)
        assert results, f"manage_asset_physical_material 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert (not first.get("error") and first.get("success") is not False) or abs(first.get("friction", 0) - new_val) < 0.001, \
            f"设置 friction 失败: {first}"

        # 恢复原值
        mcp.call_capability("manage_asset_physical_material",
                            assetPath=self._pm_path,
                            friction=float(original))

    def test_search_physical_material(self, mcp):
        r = mcp.call_capability("search_asset",
                                assetType="PhysicalMaterial",
                                pathFilter="/Game/",
                                limit=5)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("assets") or payload.get("results") or []
        assert isinstance(assets, list), f"search_asset PhysicalMaterial 格式错误: {r}"


# ── TextureRenderTarget2D ──────────────────────────────────────────────────────

class TestRenderTarget:
    def test_create(self, mcp):
        r = mcp.call_capability("create_asset_render_target",
                                assetPath=_RENDER_TARGET,
                                sizeX=512, sizeY=256)
        results = cap_entries(r)
        assert results, f"create_asset_render_target 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert (not first.get("error") and first.get("success") is not False) or first.get("name"), f"创建失败: {first}"

    def test_get(self, mcp):
        r = mcp.call_capability("get_asset_render_target", assetPath=_RENDER_TARGET)
        results = cap_entries(r)
        assert results, f"get_asset_render_target 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert first.get("sizeX") == 512, f"sizeX 不符: {first}"
        assert first.get("sizeY") == 256, f"sizeY 不符: {first}"
        assert "format" in first and "clearColor" in first, f"字段缺失: {first}"

    def test_manage_resize(self, mcp):
        r = mcp.call_capability("manage_asset_render_target",
                                assetPath=_RENDER_TARGET,
                                sizeX=1024, sizeY=1024)
        results = cap_entries(r)
        assert results, f"manage_asset_render_target 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert (not first.get("error") and first.get("success") is not False) or first.get("sizeX") == 1024, f"resize 失败: {first}"

    def test_get_after_resize(self, mcp):
        r = mcp.call_capability("get_asset_render_target", assetPath=_RENDER_TARGET)
        results = cap_entries(r)
        first = results[0] if results and isinstance(results[0], dict) else {}
        assert first.get("sizeX") == 1024 and first.get("sizeY") == 1024, \
            f"resize 后尺寸不符: {first}"

    def test_manage_clear_color(self, mcp):
        r = mcp.call_capability("manage_asset_render_target",
                                assetPath=_RENDER_TARGET,
                                clearColorR=1.0, clearColorG=0.0, clearColorB=0.0, clearColorA=1.0)
        results = cap_entries(r)
        assert results, f"manage clear_color 无结果: {r}"

    def test_search_render_target(self, mcp):
        r = mcp.call_capability("search_asset",
                                assetType="TextureRenderTarget2D",
                                pathFilter="/Game/_NexusTest/",
                                limit=5)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("assets") or payload.get("results") or []
        assert isinstance(assets, list), f"search_asset TextureRenderTarget2D 格式错误: {r}"
