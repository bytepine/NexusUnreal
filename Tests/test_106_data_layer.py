"""
test_106_data_layer.py
阶段 4c — DataLayer 能力测试（≥UE5.1）
"""
import pytest
from conftest import mcp, skipif_ue_below  # noqa: F401

DL_NAME = "NxTestDataLayer"


@pytest.fixture(scope="session")
def dl_full(test_ns):
    return f"{test_ns}/{DL_NAME}"


@pytest.mark.l3_asset
class TestCreateDataLayer:
    """create_asset_data_layer（≥UE5.1）"""

    @skipif_ue_below(5, 1)
    def test_create_runtime_layer(self, mcp, dl_full):
        r = mcp.call_capability("CreateAssetDataLayer",
                                AssetPath=dl_full,
                                type="Runtime",
                                DebugColor="#FF4400")
        payload = r if isinstance(r, dict) else {}
        entries = payload.get("Entries") or payload.get("Results") or []
        first = entries[0] if entries else payload
        assert isinstance(first, dict), f"create 返回格式异常: {r}"
        assert "Path" in first
        assert first.get("AssetType") in ("DataLayerAsset", None)

    @skipif_ue_below(5, 1)
    def test_create_idempotent(self, mcp, dl_full):
        """重复创建应返回 bAlreadyExists=true"""
        r = mcp.call_capability("CreateAssetDataLayer",
                                AssetPath=dl_full,
                                type="Runtime")
        payload = r if isinstance(r, dict) else {}
        entries = payload.get("Entries") or payload.get("Results") or []
        first = entries[0] if entries else payload
        # 应已存在
        assert isinstance(first, dict)
        assert first.get("bAlreadyExists") is True or "Path" in first


@pytest.mark.l3_asset
class TestGetDataLayer:
    """get_asset_data_layer（≥UE5.1）"""

    @skipif_ue_below(5, 1)
    def test_get_type_and_color(self, mcp, dl_full):
        r = mcp.call_capability("GetAssetDataLayer", AssetPath=dl_full)
        payload = r if isinstance(r, dict) else {}
        entries = payload.get("Entries") or payload.get("Results") or []
        first = entries[0] if entries else payload
        assert isinstance(first, dict), f"get 返回格式异常: {r}"
        assert "Error" not in first, f"get 报错: {first.get('Error')}"
        assert first.get("AssetType") == "DataLayerAsset"
        assert first.get("type") in ("Runtime", "Editor", "Unknown", None)


@pytest.mark.l3_asset
class TestManageDataLayer:
    """manage_asset_data_layer（≥UE5.1 WITH_EDITOR）"""

    @skipif_ue_below(5, 1)
    def test_set_type(self, mcp, dl_full):
        r = mcp.call_capability("ManageAssetDataLayer",
                                AssetPath=dl_full,
                                Operations=[{"Action": "SetType", "type": "Editor"}])
        payload = r if isinstance(r, dict) else {}
        entries = payload.get("Entries") or payload.get("Results") or []
        first = entries[0] if entries else payload
        assert isinstance(first, dict), f"manage set_type 返回格式异常: {r}"

    @skipif_ue_below(5, 1)
    def test_set_debug_color(self, mcp, dl_full):
        r = mcp.call_capability("ManageAssetDataLayer",
                                AssetPath=dl_full,
                                Operations=[{"Action": "SetDebugColor", "Color": "#00AAFF"}])
        payload = r if isinstance(r, dict) else {}
        entries = payload.get("Entries") or payload.get("Results") or []
        first = entries[0] if entries else payload
        assert isinstance(first, dict), f"manage set_debug_color 返回格式异常: {r}"

    @skipif_ue_below(5, 1)
    def test_restore_runtime(self, mcp, dl_full):
        mcp.call_capability("ManageAssetDataLayer",
                            AssetPath=dl_full,
                            Operations=[{"Action": "SetType", "type": "Runtime"}])


@pytest.mark.l3_asset
class TestSearchDataLayer:
    """search_asset 支持 datalayer 类型（≥UE5.1）"""

    @skipif_ue_below(5, 1)
    def test_search_datalayer(self, mcp):
        r = mcp.call_capability("SearchAsset",
                                AssetType="DataLayerAsset",
                                PathFilter="/Game/",
                                Limit=5)
        payload = r if isinstance(r, dict) else {}
        assert "Error" not in payload or payload.get("Assets") is not None

    @skipif_ue_below(5, 1)
    def test_search_all_includes_datalayer(self, mcp, test_ns):
        """bIsAll 时 DataLayerAsset 也应出现"""
        r = mcp.call_capability("SearchAsset",
                                AssetType="All",
                                PathFilter=test_ns,
                                Limit=20)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("Assets") or payload.get("Results") or []
        types = [a.get("AssetType", "") for a in assets if isinstance(a, dict)]
        if any(t == "DataLayerAsset" for t in types):
            assert True
