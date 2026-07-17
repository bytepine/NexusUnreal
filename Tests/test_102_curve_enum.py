# Copyright byteyang. All Rights Reserved.
"""Tier4-4a: CurveFloat/Vector/LinearColor/CurveTable 创建/读取/管理 + UserDefinedEnum 创建/读取/管理。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_entries, cap_first

pytestmark = pytest.mark.l3_asset


# ── 工具路径常量 ──────────────────────────────────────────────────────────────

_CURVE_FLOAT_PATH  = "/Game/_NexusTest/T4/TestCurveFloat"
_CURVE_VECTOR_PATH = "/Game/_NexusTest/T4/TestCurveVector"
_CURVE_COLOR_PATH  = "/Game/_NexusTest/T4/TestCurveLinearColor"
_ENUM_PATH         = "/Game/_NexusTest/T4/TestUserDefinedEnum"


# ── Curve Float ───────────────────────────────────────────────────────────────

class TestCurveFloat:
    def test_create(self, mcp):
        r = mcp.call_capability("create_asset_curve",
                                assetPath=_CURVE_FLOAT_PATH,
                                curveType="float")
        results = cap_entries(r)
        assert results, f"create_asset_curve float 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert (not first.get("error") and first.get("success") is not False) or first.get("name"), f"创建失败: {first}"

    def test_manage_add_key(self, mcp):
        r = mcp.call_capability("manage_asset_curve",
                                assetPath=_CURVE_FLOAT_PATH,
                                operations=[
                                    {"action": "add_key", "channel": "Value", "time": 0.0, "value": 0.0, "interp": "linear"},
                                    {"action": "add_key", "channel": "Value", "time": 1.0, "value": 100.0, "interp": "linear"},
                                ])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("error") and e.get("success") is not False for e in results), f"add_key 无成功: {r}"

    def test_get(self, mcp):
        r = mcp.call_capability("get_asset_curve", assetPath=_CURVE_FLOAT_PATH)
        results = cap_entries(r)
        assert results, f"get_asset_curve float 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert first.get("assetType") == "CurveFloat", f"assetType 不符: {first}"
        channels = first.get("channels", [])
        assert channels, "无 channels"
        assert channels[0].get("keyCount", 0) >= 2, "关键帧数不足"

    def test_manage_set_key(self, mcp):
        r = mcp.call_capability("manage_asset_curve",
                                assetPath=_CURVE_FLOAT_PATH,
                                operations=[{"action": "set_key", "channel": "Value", "time": 1.0, "value": 200.0}])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("error") and e.get("success") is not False for e in results), f"set_key 失败: {r}"

    def test_manage_set_interp(self, mcp):
        r = mcp.call_capability("manage_asset_curve",
                                assetPath=_CURVE_FLOAT_PATH,
                                operations=[{"action": "set_interp", "channel": "Value", "interp": "cubic"}])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("error") and e.get("success") is not False for e in results), f"set_interp 失败: {r}"

    def test_manage_remove_key(self, mcp):
        r = mcp.call_capability("manage_asset_curve",
                                assetPath=_CURVE_FLOAT_PATH,
                                operations=[{"action": "remove_key", "channel": "Value", "time": 1.0}])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("error") and e.get("success") is not False for e in results), f"remove_key 失败: {r}"


# ── Curve Vector ──────────────────────────────────────────────────────────────

class TestCurveVector:
    def test_create(self, mcp):
        r = mcp.call_capability("create_asset_curve",
                                assetPath=_CURVE_VECTOR_PATH,
                                curveType="vector")
        results = cap_entries(r)
        assert results, f"create_asset_curve vector 无结果: {r}"

    def test_manage_add_key(self, mcp):
        r = mcp.call_capability("manage_asset_curve",
                                assetPath=_CURVE_VECTOR_PATH,
                                operations=[
                                    {"action": "add_key", "channel": "X", "time": 0.0, "value": 1.0},
                                    {"action": "add_key", "channel": "Y", "time": 0.0, "value": 2.0},
                                    {"action": "add_key", "channel": "Z", "time": 0.0, "value": 3.0},
                                ])
        results = cap_entries(r)
        assert len([e for e in results if isinstance(e, dict) and not e.get("error") and e.get("success") is not False]) >= 3

    def test_get(self, mcp):
        r = mcp.call_capability("get_asset_curve", assetPath=_CURVE_VECTOR_PATH)
        results = cap_entries(r)
        assert results
        first = results[0] if isinstance(results[0], dict) else {}
        assert first.get("assetType") == "CurveVector"
        channels = first.get("channels", [])
        assert len(channels) == 3, f"CurveVector 应有3通道: {channels}"


# ── Curve LinearColor ─────────────────────────────────────────────────────────

class TestCurveLinearColor:
    def test_create(self, mcp):
        r = mcp.call_capability("create_asset_curve",
                                assetPath=_CURVE_COLOR_PATH,
                                curveType="linear_color")
        results = cap_entries(r)
        assert results

    def test_get(self, mcp):
        r = mcp.call_capability("get_asset_curve", assetPath=_CURVE_COLOR_PATH)
        results = cap_entries(r)
        assert results
        first = results[0] if isinstance(results[0], dict) else {}
        assert first.get("assetType") == "CurveLinearColor"
        assert len(first.get("channels", [])) == 4, "CurveLinearColor 应有4通道(R/G/B/A)"


# ── search_asset for curves ───────────────────────────────────────────────────

class TestSearchCurve:
    def test_search_curve_type(self, mcp):
        r = mcp.call_capability("search_asset",
                                assetType="curve",
                                pathFilter="/Game/_NexusTest/",
                                limit=10)
        assert isinstance(r, dict), f"search_asset 返回非字典: {r}"


# ── UserDefinedEnum ───────────────────────────────────────────────────────────

class TestUserDefinedEnum:
    def test_create(self, mcp):
        r = mcp.call_capability("create_asset_enum", assetPath=_ENUM_PATH)
        results = cap_entries(r)
        assert results, f"create_asset_enum 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert not first.get("error") and first.get("success") is not False, f"创建失败: {first}"

    def test_get(self, mcp):
        r = mcp.call_capability("get_asset_enum", assetPath=_ENUM_PATH)
        results = cap_entries(r)
        assert results, f"get_asset_enum 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert first.get("entryCount", 0) >= 1, "枚举应至少有1项（初始项）"

    def test_manage_set_display_name(self, mcp):
        r = mcp.call_capability("manage_asset_enum",
                                assetPath=_ENUM_PATH,
                                operations=[{"action": "set_display_name", "index": 0, "displayName": "DefaultEntry"}])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("error") and e.get("success") is not False for e in results), f"set_display_name 失败: {r}"

    def test_manage_add_entry(self, mcp):
        r = mcp.call_capability("manage_asset_enum",
                                assetPath=_ENUM_PATH,
                                operations=[{"action": "add_entry"}])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("error") and e.get("success") is not False for e in results), f"add_entry 失败: {r}"

    def test_manage_remove_entry(self, mcp):
        r = mcp.call_capability("get_asset_enum", assetPath=_ENUM_PATH)
        results = cap_entries(r)
        count = results[0].get("entryCount", 0) if results and isinstance(results[0], dict) else 0
        if count < 2:
            pytest.skip("枚举项不足2项，跳过 remove_entry")
        r2 = mcp.call_capability("manage_asset_enum",
                                 assetPath=_ENUM_PATH,
                                 operations=[{"action": "remove_entry", "index": count - 1}])
        results2 = cap_entries(r2)
        assert any(isinstance(e, dict) and not e.get("error") and e.get("success") is not False for e in results2), f"remove_entry 失败: {r2}"

    def test_search_enum_type(self, mcp):
        r = mcp.call_capability("search_asset",
                                assetType="enum",
                                pathFilter="/Game/_NexusTest/",
                                limit=10)
        assert isinstance(r, dict), f"search_asset enum 返回非字典: {r}"
