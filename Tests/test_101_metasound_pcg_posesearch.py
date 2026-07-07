# Copyright byteyang. All Rights Reserved.
"""Tier3-3c: MetaSound / PCG Graph / PoseSearch 能力集成测试。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.l3_asset


# ── MetaSound ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def metasound_path(mcp):
    """发现项目中存在的 MetaSoundSource，或跳过。"""
    r = mcp.call_capability(
        "search_asset",
        query="",
        assetType="metasound",
        pathFilter="/Game/",
        limit=1,
    )
    assets = (r.get("results") or []) if isinstance(r, dict) else []
    if not assets:
        pytest.skip("项目中无 MetaSoundSource 资产，跳过只读测试")
    return assets[0].get("path") or assets[0].get("assetPath")


@pytest.mark.skipif_ue_below("5.0")
def test_get_metasound_returns_inputs_outputs(mcp, metasound_path):
    """get_asset_meta_sound 应返回 inputs/outputs 字段。"""
    r = mcp.call_capability("get_asset_meta_sound", assetPath=metasound_path)
    entries = r if isinstance(r, list) else [r]
    entry = next((e for e in entries if isinstance(e, dict) and "error" not in e), None)
    assert entry is not None, f"无有效条目：{r}"
    assert "inputs" in entry or "outputs" in entry, f"缺少 inputs/outputs：{entry}"


@pytest.mark.skipif_ue_below("5.0")
def test_create_metasound_asset(mcp, test_ns):
    """create_asset_meta_sound 应能创建 MetaSoundSource 资产。"""
    pkg  = f"/Game/{test_ns}"
    name = "TestMetaSound_MCP"
    r = mcp.call_capability("create_asset_meta_sound", packagePath=pkg, assetName=name)
    entries = r if isinstance(r, list) else [r]
    entry = next((e for e in entries if isinstance(e, dict)), None)
    assert entry is not None
    assert entry.get("created") or entry.get("alreadyExists"), f"创建失败：{entry}"


@pytest.mark.skipif_ue_below("5.3")
def test_manage_metasound_add_input(mcp, test_ns):
    """manage_asset_meta_sound add_input 应成功。"""
    asset_path = f"/Game/{test_ns}/TestMetaSound_MCP"
    r = mcp.call_capability(
        "manage_asset_meta_sound",
        assetPath=asset_path,
        operations=[{"action": "add_input", "name": "TestInput", "typeName": "float"}],
    )
    entries = r if isinstance(r, list) else [r]
    entry = next((e for e in entries if isinstance(e, dict) and "results" in e), None)
    assert entry is not None, f"无 results：{r}"
    result = entry["results"][0] if entry["results"] else {}
    assert result.get("success") or result.get("alreadyExists"), f"add_input 失败：{result}"


# ── PCG Graph ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pcg_path(mcp):
    """发现项目中存在的 PCGGraph，或跳过。"""
    r = mcp.call_capability(
        "search_asset",
        query="",
        assetType="pcg",
        pathFilter="/Game/",
        limit=1,
    )
    assets = (r.get("results") or []) if isinstance(r, dict) else []
    if not assets:
        pytest.skip("项目中无 PCGGraph 资产，跳过只读测试")
    return assets[0].get("path") or assets[0].get("assetPath")


@pytest.mark.skipif_ue_below("5.4")
def test_get_pcg_graph_nodes(mcp, pcg_path):
    """get_asset_pcg_graph 应返回节点列表。"""
    r = mcp.call_capability("get_asset_pcg_graph", assetPath=pcg_path)
    entries = r if isinstance(r, list) else [r]
    entry = next((e for e in entries if isinstance(e, dict) and "error" not in e), None)
    assert entry is not None, f"无有效条目：{r}"
    assert "nodes" in entry, f"缺少 nodes 字段：{entry}"


@pytest.mark.skipif_ue_below("5.4")
def test_create_pcg_graph(mcp, test_ns):
    """create_asset_pcg_graph 应能创建 PCGGraph 资产。"""
    pkg  = f"/Game/{test_ns}"
    name = "TestPCGGraph_MCP"
    r = mcp.call_capability("create_asset_pcg_graph", packagePath=pkg, assetName=name)
    entries = r if isinstance(r, list) else [r]
    entry = next((e for e in entries if isinstance(e, dict)), None)
    assert entry is not None
    assert entry.get("created") or entry.get("alreadyExists"), f"创建失败：{entry}"


# ── PoseSearch ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pose_search_db_path(mcp):
    """发现项目中存在的 PoseSearchDatabase，或跳过。"""
    r = mcp.call_capability(
        "search_asset",
        query="",
        assetType="posesearch",
        pathFilter="/Game/",
        limit=1,
    )
    assets = (r.get("results") or []) if isinstance(r, dict) else []
    if not assets:
        pytest.skip("项目中无 PoseSearchDatabase 资产，跳过只读测试")
    return assets[0].get("path") or assets[0].get("assetPath")


@pytest.mark.skipif_ue_below("5.4")
def test_get_pose_search_database(mcp, pose_search_db_path):
    """get_asset_pose_search 应返回 schema 或 animationAssetCount。"""
    r = mcp.call_capability("get_asset_pose_search", assetPath=pose_search_db_path)
    entries = r if isinstance(r, list) else [r]
    entry = next((e for e in entries if isinstance(e, dict) and "error" not in e), None)
    assert entry is not None, f"无有效条目：{r}"
    assert entry.get("assetType") == "PoseSearchDatabase", f"类型错误：{entry}"
    assert "animationAssetCount" in entry, f"缺少 animationAssetCount：{entry}"
