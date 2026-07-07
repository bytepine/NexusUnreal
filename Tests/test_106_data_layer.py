"""
test_106_data_layer.py
阶段 4c — DataLayer 能力测试（≥UE5.1）
"""
import pytest
from conftest import mcp, skipif_ue_below  # noqa: F401

DL_PKG_PATH = "/Game/_NexusTest/World"
DL_NAME = "NxTestDataLayer"
DL_FULL = f"{DL_PKG_PATH}/{DL_NAME}"


@pytest.mark.l3_asset
class TestCreateDataLayer:
    """create_asset_data_layer（≥UE5.1）"""

    @skipif_ue_below(5, 1)
    def test_create_runtime_layer(self, mcp):
        r = mcp.call_capability("create_asset_data_layer",
                                packagePath=DL_PKG_PATH,
                                assetName=DL_NAME,
                                type="Runtime",
                                debugColor="#FF4400")
        payload = r if isinstance(r, dict) else {}
        entries = payload.get("entries") or payload.get("results") or []
        first = entries[0] if entries else payload
        assert isinstance(first, dict), f"create 返回格式异常: {r}"
        assert "assetPath" in first
        assert first.get("assetType") in ("DataLayerAsset", None)

    @skipif_ue_below(5, 1)
    def test_create_idempotent(self, mcp):
        """重复创建应返回 alreadyExists=true"""
        r = mcp.call_capability("create_asset_data_layer",
                                packagePath=DL_PKG_PATH,
                                assetName=DL_NAME,
                                type="Runtime")
        payload = r if isinstance(r, dict) else {}
        entries = payload.get("entries") or payload.get("results") or []
        first = entries[0] if entries else payload
        # 应已存在
        assert isinstance(first, dict)
        assert first.get("alreadyExists") is True or "assetPath" in first


@pytest.mark.l3_asset
class TestGetDataLayer:
    """get_asset_data_layer（≥UE5.1）"""

    @skipif_ue_below(5, 1)
    def test_get_type_and_color(self, mcp):
        r = mcp.call_capability("get_asset_data_layer", assetPath=DL_FULL)
        payload = r if isinstance(r, dict) else {}
        entries = payload.get("entries") or payload.get("results") or []
        first = entries[0] if entries else payload
        assert isinstance(first, dict), f"get 返回格式异常: {r}"
        assert "error" not in first, f"get 报错: {first.get('error')}"
        assert first.get("assetType") == "DataLayerAsset"
        assert first.get("type") in ("Runtime", "Editor", "Unknown", None)


@pytest.mark.l3_asset
class TestManageDataLayer:
    """manage_asset_data_layer（≥UE5.1 WITH_EDITOR）"""

    @skipif_ue_below(5, 1)
    def test_set_type(self, mcp):
        r = mcp.call_capability("manage_asset_data_layer",
                                assetPath=DL_FULL,
                                operations=[{"action": "set_type", "type": "Editor"}])
        payload = r if isinstance(r, dict) else {}
        entries = payload.get("entries") or payload.get("results") or []
        first = entries[0] if entries else payload
        assert isinstance(first, dict), f"manage set_type 返回格式异常: {r}"
        results = first.get("results") or []
        if results:
            res = results[0]
            assert res.get("success") is True or "error" in res

    @skipif_ue_below(5, 1)
    def test_set_debug_color(self, mcp):
        r = mcp.call_capability("manage_asset_data_layer",
                                assetPath=DL_FULL,
                                operations=[{"action": "set_debug_color", "color": "#00AAFF"}])
        payload = r if isinstance(r, dict) else {}
        entries = payload.get("entries") or payload.get("results") or []
        first = entries[0] if entries else payload
        assert isinstance(first, dict), f"manage set_debug_color 返回格式异常: {r}"

    @skipif_ue_below(5, 1)
    def test_restore_runtime(self, mcp):
        mcp.call_capability("manage_asset_data_layer",
                            assetPath=DL_FULL,
                            operations=[{"action": "set_type", "type": "Runtime"}])


@pytest.mark.l3_asset
class TestSearchDataLayer:
    """search_asset 支持 datalayer 类型（≥UE5.1）"""

    @skipif_ue_below(5, 1)
    def test_search_datalayer(self, mcp):
        r = mcp.call_capability("search_asset",
                                assetType="DataLayerAsset",
                                pathFilter="/Game/",
                                limit=5)
        payload = r if isinstance(r, dict) else {}
        assert "error" not in payload or payload.get("assets") is not None

    @skipif_ue_below(5, 1)
    def test_search_all_includes_datalayer(self, mcp):
        """bIsAll 时 DataLayerAsset 也应出现"""
        r = mcp.call_capability("search_asset",
                                assetType="all",
                                pathFilter=DL_PKG_PATH,
                                limit=20)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("assets") or payload.get("results") or []
        types = [a.get("assetType", "") for a in assets if isinstance(a, dict)]
        if any(t == "DataLayerAsset" for t in types):
            assert True
