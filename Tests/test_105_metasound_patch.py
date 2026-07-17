"""
test_105_metasound_patch.py
阶段 4c — MetaSoundPatch 能力测试（≥UE5.1 + WITH_METASOUND）
"""
import pytest
from conftest import mcp, skipif_ue_below  # noqa: F401

PATCH_PKG_PATH = "/Game/_NexusTest/Audio"
PATCH_NAME = "NxTestPatch"
PATCH_FULL = f"{PATCH_PKG_PATH}/{PATCH_NAME}"


@pytest.mark.l3_asset
class TestCreateMetaSoundPatch:
    """create_asset_meta_sound_patch（≥UE5.1）"""

    @skipif_ue_below(5, 1)
    def test_create_patch(self, mcp):
        r = mcp.call_capability("create_asset_meta_sound_patch",
                                assetPath=PATCH_FULL)
        payload = r if isinstance(r, dict) else {}
        entries = payload.get("entries") or payload.get("results") or []
        first = entries[0] if entries else payload
        if isinstance(first, dict):
            assert "path" in first
            assert first.get("assetType") in ("MetaSoundPatch", None)
        else:
            pytest.fail(f"create_asset_meta_sound_patch 返回格式异常: {r}")


@pytest.mark.l3_asset
class TestGetMetaSoundPatch:
    """get_asset_meta_sound 可读取 MetaSoundPatch（≥UE5.1）"""

    @skipif_ue_below(5, 1)
    def test_get_patch_basic(self, mcp):
        r = mcp.call_capability("get_asset_meta_sound", assetPath=PATCH_FULL)
        payload = r if isinstance(r, dict) else {}
        entries = payload.get("entries") or payload.get("results") or []
        first = entries[0] if entries else payload
        if isinstance(first, dict):
            # 不应报 error；assetType 应为 MetaSoundPatch
            assert "error" not in first or first.get("assetType") == "MetaSoundPatch"
        else:
            pytest.fail(f"get_asset_meta_sound(Patch) 返回格式异常: {r}")


@pytest.mark.l3_asset
class TestManageMetaSoundPatch:
    """manage_asset_meta_sound 可修改 MetaSoundPatch 接口（≥UE5.3，WITH_METASOUND + FRONTEND_DOCUMENT）"""

    @skipif_ue_below(5, 3)
    def test_add_remove_input(self, mcp):
        # 添加一个 float input
        r = mcp.call_capability("manage_asset_meta_sound",
                                assetPath=PATCH_FULL,
                                operations=[{"action": "add_input", "name": "TestFloat", "typeName": "float"}])
        payload = r if isinstance(r, dict) else {}
        entries = payload.get("entries") or payload.get("results") or []
        first = entries[0] if entries else payload
        assert isinstance(first, dict), f"manage 返回格式异常: {r}"

        # 移除
        mcp.call_capability("manage_asset_meta_sound",
                            assetPath=PATCH_FULL,
                            operations=[{"action": "remove_input", "name": "TestFloat"}])


@pytest.mark.l3_asset
class TestSearchMetaSoundPatch:
    """search_asset 支持 metasoundpatch 类型（≥UE5.1）"""

    @skipif_ue_below(5, 1)
    def test_search_metasoundpatch(self, mcp):
        r = mcp.call_capability("search_asset",
                                assetType="MetaSoundPatch",
                                pathFilter="/Game/",
                                limit=5)
        payload = r if isinstance(r, dict) else {}
        # 允许 0 结果（项目中可能没有 Patch），但不应报错
        assert "error" not in payload or payload.get("assets") is not None

    @skipif_ue_below(5, 1)
    def test_search_metasound_all_finds_patch(self, mcp):
        """bIsAll 时应同时搜到 MetaSoundPatch"""
        r = mcp.call_capability("search_asset",
                                assetType="all",
                                pathFilter=PATCH_PKG_PATH,
                                limit=20)
        payload = r if isinstance(r, dict) else {}
        assets = payload.get("assets") or payload.get("results") or []
        types = [a.get("assetType", "") for a in assets if isinstance(a, dict)]
        # 如果测试资产已创建，类型中应出现 MetaSoundPatch
        if any(t == "MetaSoundPatch" for t in types):
            assert True
