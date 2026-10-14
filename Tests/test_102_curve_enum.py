# Copyright byteyang. All Rights Reserved.
"""Tier4-4a: CurveFloat/Vector/LinearColor/CurveTable 创建/读取/管理 + UserDefinedEnum 创建/读取/管理。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_entries, cap_first

pytestmark = pytest.mark.l3_asset


@pytest.fixture(scope="session")
def curve_float_path(test_ns):
    return f"{test_ns}/TestCurveFloat"


@pytest.fixture(scope="session")
def curve_vector_path(test_ns):
    return f"{test_ns}/TestCurveVector"


@pytest.fixture(scope="session")
def curve_color_path(test_ns):
    return f"{test_ns}/TestCurveLinearColor"


@pytest.fixture(scope="session")
def enum_path(test_ns):
    return f"{test_ns}/TestUserDefinedEnum"


def _create_ok(first: dict) -> bool:
    err = str(first.get("Error") or "")
    if err and "already exists" not in err.lower() and "已存在" not in err:
        return False
    return True


# ── Curve Float ───────────────────────────────────────────────────────────────

class TestCurveFloat:
    def test_create(self, mcp, curve_float_path):
        r = mcp.call_capability("CreateAssetCurve",
                                AssetPath=curve_float_path,
                                CurveType="float")
        results = cap_entries(r)
        assert results, f"create_asset_curve float 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert _create_ok(first) or first.get("name"), f"创建失败: {first}"

    def test_manage_add_key(self, mcp, curve_float_path):
        r = mcp.call_capability("ManageAssetCurve",
                                AssetPath=curve_float_path,
                                Operations=[
                                    {"Action": "AddKey", "Channel": "Value", "Time": 0.0, "Value": 0.0, "Interp": "linear"},
                                    {"Action": "AddKey", "Channel": "Value", "Time": 1.0, "Value": 100.0, "Interp": "linear"},
                                ])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("Error") and e.get("bSuccess") is not False for e in results), f"add_key 无成功: {r}"

    def test_get(self, mcp, curve_float_path):
        r = mcp.call_capability("GetAssetCurve", AssetPath=curve_float_path)
        results = cap_entries(r)
        assert results, f"get_asset_curve float 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert first.get("AssetType") == "CurveFloat", f"assetType 不符: {first}"
        channels = first.get("Channels", [])
        assert channels, "无 channels"
        assert channels[0].get("KeyCount", 0) >= 2, "关键帧数不足"

    def test_manage_set_key(self, mcp, curve_float_path):
        r = mcp.call_capability("ManageAssetCurve",
                                AssetPath=curve_float_path,
                                Operations=[{"Action": "SetKey", "Channel": "Value", "Time": 1.0, "Value": 200.0}])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("Error") and e.get("bSuccess") is not False for e in results), f"set_key 失败: {r}"

    def test_manage_set_interp(self, mcp, curve_float_path):
        r = mcp.call_capability("ManageAssetCurve",
                                AssetPath=curve_float_path,
                                Operations=[{"Action": "SetInterp", "Channel": "Value", "Interp": "cubic"}])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("Error") and e.get("bSuccess") is not False for e in results), f"set_interp 失败: {r}"

    def test_manage_remove_key(self, mcp, curve_float_path):
        r = mcp.call_capability("ManageAssetCurve",
                                AssetPath=curve_float_path,
                                Operations=[{"Action": "RemoveKey", "Channel": "Value", "Time": 1.0}])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("Error") and e.get("bSuccess") is not False for e in results), f"remove_key 失败: {r}"


# ── Curve Vector ──────────────────────────────────────────────────────────────

class TestCurveVector:
    def test_create(self, mcp, curve_vector_path):
        r = mcp.call_capability("CreateAssetCurve",
                                AssetPath=curve_vector_path,
                                CurveType="Vector")
        results = cap_entries(r)
        assert results, f"create_asset_curve vector 无结果: {r}"

    def test_manage_add_key(self, mcp, curve_vector_path):
        r = mcp.call_capability("ManageAssetCurve",
                                AssetPath=curve_vector_path,
                                Operations=[
                                    {"Action": "AddKey", "Channel": "X", "Time": 0.0, "Value": 1.0},
                                    {"Action": "AddKey", "Channel": "Y", "Time": 0.0, "Value": 2.0},
                                    {"Action": "AddKey", "Channel": "Z", "Time": 0.0, "Value": 3.0},
                                ])
        results = cap_entries(r)
        assert len([e for e in results if isinstance(e, dict) and not e.get("Error") and e.get("bSuccess") is not False]) >= 3

    def test_get(self, mcp, curve_vector_path):
        r = mcp.call_capability("GetAssetCurve", AssetPath=curve_vector_path)
        results = cap_entries(r)
        assert results
        first = results[0] if isinstance(results[0], dict) else {}
        assert first.get("AssetType") == "CurveVector"
        channels = first.get("Channels", [])
        assert len(channels) == 3, f"CurveVector 应有3通道: {channels}"


# ── Curve LinearColor ─────────────────────────────────────────────────────────

class TestCurveLinearColor:
    def test_create(self, mcp, curve_color_path):
        r = mcp.call_capability("CreateAssetCurve",
                                AssetPath=curve_color_path,
                                CurveType="LinearColor")
        results = cap_entries(r)
        assert results

    def test_get(self, mcp, curve_color_path):
        r = mcp.call_capability("GetAssetCurve", AssetPath=curve_color_path)
        results = cap_entries(r)
        assert results
        first = results[0] if isinstance(results[0], dict) else {}
        assert first.get("AssetType") == "CurveLinearColor"
        assert len(first.get("Channels", [])) == 4, "CurveLinearColor 应有4通道(R/G/B/A)"


# ── search_asset for curves ───────────────────────────────────────────────────

class TestSearchCurve:
    def test_search_curve_type(self, mcp, test_ns):
        r = mcp.call_capability("SearchAsset",
                                AssetType="curve",
                                PathFilter=test_ns,
                                Limit=10)
        assert isinstance(r, dict), f"search_asset 返回非字典: {r}"


# ── UserDefinedEnum ───────────────────────────────────────────────────────────

class TestUserDefinedEnum:
    def test_create(self, mcp, enum_path):
        r = mcp.call_capability("CreateAssetEnum", AssetPath=enum_path)
        results = cap_entries(r)
        assert results, f"create_asset_enum 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        if first.get("Error") and "already exists" in str(first.get("Error")):
            return
        assert not first.get("Error") and first.get("bSuccess") is not False, f"创建失败: {first}"

    def test_get(self, mcp, enum_path):
        r = mcp.call_capability("GetAssetEnum", AssetPath=enum_path)
        results = cap_entries(r)
        assert results, f"get_asset_enum 无结果: {r}"
        first = results[0] if isinstance(results[0], dict) else {}
        assert first.get("EntryCount", 0) >= 1, "枚举应至少有1项（初始项）"

    def test_manage_set_display_name(self, mcp, enum_path):
        r = mcp.call_capability("ManageAssetEnum",
                                AssetPath=enum_path,
                                Operations=[{"Action": "SetDisplayName", "Index": 0, "DisplayName": "DefaultEntry"}])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("Error") and e.get("bSuccess") is not False for e in results), f"set_display_name 失败: {r}"

    def test_manage_add_entry(self, mcp, enum_path):
        r = mcp.call_capability("ManageAssetEnum",
                                AssetPath=enum_path,
                                Operations=[{"Action": "AddEntry"}])
        results = cap_entries(r)
        assert any(isinstance(e, dict) and not e.get("Error") and e.get("bSuccess") is not False for e in results), f"add_entry 失败: {r}"

    def test_manage_remove_entry(self, mcp, enum_path):
        r = mcp.call_capability("GetAssetEnum", AssetPath=enum_path)
        results = cap_entries(r)
        count = results[0].get("EntryCount", 0) if results and isinstance(results[0], dict) else 0
        if count < 2:
            pytest.skip("枚举项不足2项，跳过 remove_entry")
        r2 = mcp.call_capability("ManageAssetEnum",
                                 AssetPath=enum_path,
                                 Operations=[{"Action": "RemoveEntry", "Index": count - 1}])
        results2 = cap_entries(r2)
        assert any(isinstance(e, dict) and not e.get("Error") and e.get("bSuccess") is not False for e in results2), f"remove_entry 失败: {r2}"

    def test_search_enum_type(self, mcp, test_ns):
        r = mcp.call_capability("SearchAsset",
                                AssetType="enum",
                                PathFilter=test_ns,
                                Limit=10)
        assert isinstance(r, dict), f"search_asset enum 返回非字典: {r}"
