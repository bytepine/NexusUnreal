# Copyright byteyang. All Rights Reserved.
"""Tier4-4a-P1: AnimComposite 创建/读取/管理 + PhysicalMaterial 读取/管理 + RenderTarget 创建/读取/管理。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_entries, cap_first

pytestmark = pytest.mark.l3_asset

# ── AnimComposite ──────────────────────────────────────────────────────────────

class TestAnimComposite:
    @pytest.fixture(autouse=True)
    def _paths(self, test_ns):
        self.path = f"{test_ns}/TestAnimComposite"
        self.ns = test_ns

    def test_create(self, mcp):
        r = mcp.call_capability("CreateAssetAnimComposite",
                                AssetPath=self.path)
        results = cap_entries(r)
        assert results, f"create_asset_anim_composite 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        if first.get("Error") and "already exists" in str(first.get("Error")):
            return
        assert (not first.get("Error") and first.get("bSuccess") is not False) or first.get("name"), f"创建失败: {first}"

    def test_get_empty(self, mcp):
        r = mcp.call_capability("GetAssetAnimComposite", AssetPath=self.path)
        results = cap_entries(r)
        assert results, f"get_asset_anim_composite 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert first.get("name"), f"缺少 name: {first}"
        assert first.get("SegmentCount", -1) == 0, f"初始应为 0 segments: {first}"

    def test_manage_add_segment(self, mcp):
        """add_segment 无 animPath 时应能添加空占位片段。"""
        r = mcp.call_capability("ManageAssetAnimComposite",
                                AssetPath=self.path,
                                Operations=[{
                                    "Action": "AddSegment",
                                    "AnimStartTime": 0.0,
                                    "AnimEndTime": 1.0,
                                    "PlayRate": 1.0,
                                }])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("Error") and e.get("bSuccess") is not False for e in results), \
            f"add_segment 无成功: {r}"

    def test_get_after_add(self, mcp):
        r = mcp.call_capability("GetAssetAnimComposite", AssetPath=self.path)
        results = cap_entries(r)
        first = results[0] if results and isinstance(results[0], dict) else {}
        assert first.get("SegmentCount", 0) >= 1, f"add_segment 后 segmentCount 应 ≥1: {first}"
        segs = first.get("Segments", [])
        assert segs, "无 segments 数组"
        seg0 = segs[0] if isinstance(segs[0], dict) else {}
        assert "StartPos" in seg0 and "PlayRate" in seg0, f"片段字段缺失: {seg0}"

    def test_manage_remove_segment(self, mcp):
        r = mcp.call_capability("ManageAssetAnimComposite",
                                AssetPath=self.path,
                                Operations=[{"Action": "RemoveSegment", "SegmentIndex": 0}])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("Error") and e.get("bSuccess") is not False for e in results), \
            f"remove_segment 无成功: {r}"

    def test_search_anim_composite(self, mcp):
        r = mcp.call_capability("SearchAsset",
                                AssetType="AnimComposite",
                                PathFilter=self.ns,
                                Limit=5)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("Assets") or payload.get("Results") or []
        assert isinstance(assets, list), f"search_asset AnimComposite 返回格式错误: {r}"


# ── PhysicalMaterial ───────────────────────────────────────────────────────────

class TestPhysicalMaterial:
    """get/manage PhysicalMaterial；需要项目中存在任一 PM 资产。"""

    @pytest.fixture(autouse=True)
    def _find_pm_path(self, mcp):
        """在项目中搜索一个可用的 PhysicalMaterial，找不到则 skip。"""
        r = mcp.call_capability("SearchAsset",
                                AssetType="PhysicalMaterial",
                                PathFilter="/Game/",
                                Limit=1)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("Assets") or payload.get("Results") or []
        if not assets:
            pytest.skip("项目中未找到 PhysicalMaterial 资产，跳过测试")
        first = assets[0] if isinstance(assets[0], dict) else {}
        self._pm_path = first.get("AssetPath") or first.get("Path") or ""
        if not self._pm_path:
            pytest.skip("PhysicalMaterial 路径解析失败，跳过测试")

    def test_get(self, mcp):
        r = mcp.call_capability("GetAssetPhysicalMaterial", AssetPath=self._pm_path)
        results = cap_entries(r)
        assert results, f"get_asset_physical_material 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert "Friction" in first and "Restitution" in first, f"字段缺失: {first}"

    def test_manage_friction(self, mcp):
        r_before = mcp.call_capability("GetAssetPhysicalMaterial", AssetPath=self._pm_path)
        original = (cap_first(r_before)).get("Friction", 0.5)

        new_val = round(original + 0.01, 4) if original < 0.99 else round(original - 0.01, 4)
        r = mcp.call_capability("ManageAssetPhysicalMaterial",
                                AssetPath=self._pm_path,
                                Operations=[{"Action": "Set", "Friction": new_val}])
        results = cap_entries(r)
        assert results, f"manage_asset_physical_material 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert (not first.get("Error") and first.get("bSuccess") is not False) or abs(first.get("Friction", 0) - new_val) < 0.001, \
            f"设置 friction 失败: {first}"

        # 恢复原值
        mcp.call_capability("ManageAssetPhysicalMaterial",
                            AssetPath=self._pm_path,
                            Operations=[{"Action": "Set", "Friction": float(original)}])

    def test_search_physical_material(self, mcp):
        r = mcp.call_capability("SearchAsset",
                                AssetType="PhysicalMaterial",
                                PathFilter="/Game/",
                                Limit=5)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("Assets") or payload.get("Results") or []
        assert isinstance(assets, list), f"search_asset PhysicalMaterial 格式错误: {r}"

    def test_create(self, mcp, test_ns):
        path = f"{test_ns}/PM_Created"
        r = mcp.call_capability(
            "CreateAssetPhysicalMaterial",
            AssetPath=path,
            Friction=0.7,
            Restitution=0.2,
        )
        first = cap_first(r)
        if first.get("Error") and "already exists" in str(first.get("Error")):
            return
        assert not first.get("Error"), r
        got = cap_first(mcp.call_capability("GetAssetPhysicalMaterial", AssetPath=path))
        assert "Friction" in got, got


# ── TextureRenderTarget2D ──────────────────────────────────────────────────────

class TestRenderTarget:
    @pytest.fixture(autouse=True)
    def _paths(self, test_ns):
        self.path = f"{test_ns}/TestRenderTarget"
        self.ns = test_ns

    def test_create(self, mcp):
        r = mcp.call_capability("CreateAssetRenderTarget",
                                AssetPath=self.path,
                                SizeX=512, SizeY=256)
        results = cap_entries(r)
        assert results, f"create_asset_render_target 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        if first.get("Error") and "already exists" in str(first.get("Error")):
            return
        assert (not first.get("Error") and first.get("bSuccess") is not False) or first.get("name"), f"创建失败: {first}"

    def test_get(self, mcp):
        r = mcp.call_capability("GetAssetRenderTarget", AssetPath=self.path)
        results = cap_entries(r)
        assert results, f"get_asset_render_target 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert first.get("SizeX") == 512, f"sizeX 不符: {first}"
        assert first.get("SizeY") == 256, f"sizeY 不符: {first}"
        assert "Format" in first and "ClearColor" in first, f"字段缺失: {first}"

    def test_manage_resize(self, mcp):
        r = mcp.call_capability("ManageAssetRenderTarget",
                                AssetPath=self.path,
                                Operations=[{"Action": "Set", "SizeX": 1024, "SizeY": 1024}])
        results = cap_entries(r)
        assert results, f"manage_asset_render_target 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert (not first.get("Error") and first.get("bSuccess") is not False) or first.get("SizeX") == 1024, f"resize 失败: {first}"

    def test_get_after_resize(self, mcp):
        r = mcp.call_capability("GetAssetRenderTarget", AssetPath=self.path)
        results = cap_entries(r)
        first = results[0] if results and isinstance(results[0], dict) else {}
        assert first.get("SizeX") == 1024 and first.get("SizeY") == 1024, \
            f"resize 后尺寸不符: {first}"

    def test_manage_clear_color(self, mcp):
        r = mcp.call_capability("ManageAssetRenderTarget",
                                AssetPath=self.path,
                                Operations=[{"Action": "Set",
                                             "ClearColorR": 1.0, "ClearColorG": 0.0,
                                             "ClearColorB": 0.0, "ClearColorA": 1.0}])
        results = cap_entries(r)
        assert results, f"manage clear_color 无结果: {r}"

    def test_search_render_target(self, mcp):
        r = mcp.call_capability("SearchAsset",
                                AssetType="TextureRenderTarget2D",
                                PathFilter=self.ns,
                                Limit=5)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("Assets") or payload.get("Results") or []
        assert isinstance(assets, list), f"search_asset TextureRenderTarget2D 格式错误: {r}"
