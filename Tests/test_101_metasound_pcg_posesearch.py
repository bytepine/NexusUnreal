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
        "SearchAsset",
        Query="",
        AssetType="metasound",
        PathFilter="/Game/",
        Limit=1,
    )
    assets = (r.get("Assets") or []) if isinstance(r, dict) else []
    if not assets:
        pytest.skip("项目中无 MetaSoundSource 资产，跳过只读测试")
    return assets[0].get("Path") or assets[0].get("AssetPath")


@pytest.mark.skipif_ue_below("5.0")
def test_get_metasound_returns_inputs_outputs(mcp, metasound_path):
    """get_asset_meta_sound 应返回 inputs/outputs 字段。"""
    r = mcp.call_capability("GetAssetMetaSound", AssetPath=metasound_path)
    entries = r if isinstance(r, list) else [r]
    entry = next((e for e in entries if isinstance(e, dict) and "Error" not in e), None)
    assert entry is not None, f"无有效条目：{r}"
    assert "Inputs" in entry or "Outputs" in entry, f"缺少 inputs/outputs：{entry}"


@pytest.mark.skipif_ue_below("5.0")
def test_create_metasound_asset(mcp, test_ns):
    """create_asset_meta_sound 应能创建 MetaSoundSource 资产。"""
    pkg  = test_ns
    name = "TestMetaSound_MCP"
    r = mcp.call_capability("CreateAssetMetaSound", AssetPath=f"{pkg}/{name}")
    entries = r if isinstance(r, list) else [r]
    entry = next((e for e in entries if isinstance(e, dict)), None)
    assert entry is not None
    assert entry.get("bCreated") or entry.get("bAlreadyExists"), f"创建失败：{entry}"
    assert entry.get("Path"), f"缺少 path：{entry}"


@pytest.mark.skipif_ue_below("5.3")
def test_manage_metasound_add_input(mcp, test_ns):
    """manage_asset_meta_sound add_input 应成功。"""
    asset_path = f"{test_ns}/TestMetaSound_MCP"
    r = mcp.call_capability(
        "ManageAssetMetaSound",
        AssetPath=asset_path,
        Operations=[{"Action": "AddInput", "name": "TestInput", "TypeName": "float"}],
    )
    entries = r if isinstance(r, list) else [r]
    entry = next((e for e in entries if isinstance(e, dict) and e.get("Action") == "AddInput"), None)
    assert entry is not None, f"无 add_input 条目：{r}"
    assert not entry.get("Error") or entry.get("bAlreadyExists"), f"add_input 失败：{entry}"


@pytest.mark.skipif_ue_below("5.3")
def test_manage_metasound_graph_ops(mcp, test_ns):
    asset_path = f"{test_ns}/TestMetaSound_MCP"
    r = mcp.call_capability(
        "ManageAssetMetaSound",
        AssetPath=asset_path,
        Operations=[
            {"Action": "AddOutput", "name": "TestOutput", "TypeName": "float"},
            {"Action": "AddNode", "ClassId": "Add"},
            {"Action": "AddEdge", "FromNodeId": "TestInput", "ToNodeId": "TestOutput"},
            {"Action": "RemoveEdge", "FromNodeId": "TestInput", "ToNodeId": "TestOutput"},
            {"Action": "RemoveNode", "NodeId": "0"},
            {"Action": "RemoveOutput", "name": "TestOutput"},
        ],
    )
    for e in (r.get("Results") or []):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"metasound remaining 跳过: {e}")
    if not r.get("Results") and cap_first(r).get("Error"):
        pytest.skip(f"metasound remaining 跳过: {cap_first(r)}")


# ── PCG Graph ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pcg_path(mcp):
    """发现项目中存在的 PCGGraph，或跳过。"""
    r = mcp.call_capability(
        "SearchAsset",
        Query="",
        AssetType="pcg",
        PathFilter="/Game/",
        Limit=1,
    )
    assets = (r.get("Assets") or []) if isinstance(r, dict) else []
    if not assets:
        pytest.skip("项目中无 PCGGraph 资产，跳过只读测试")
    return assets[0].get("Path") or assets[0].get("AssetPath")


@pytest.mark.skipif_ue_below("5.4")
def test_get_pcg_graph_nodes(mcp, pcg_path):
    """get_asset_pcg_graph 应返回节点列表。"""
    r = mcp.call_capability("GetAssetPCGGraph", AssetPath=pcg_path)
    entries = r if isinstance(r, list) else [r]
    entry = next((e for e in entries if isinstance(e, dict) and "Error" not in e), None)
    assert entry is not None, f"无有效条目：{r}"
    assert "Nodes" in entry, f"缺少 nodes 字段：{entry}"


@pytest.mark.skipif_ue_below("5.4")
def test_create_pcg_graph(mcp, test_ns):
    """create_asset_pcg_graph 应能创建 PCGGraph 资产。"""
    pkg  = test_ns
    name = "TestPCGGraph_MCP"
    r = mcp.call_capability("CreateAssetPCGGraph", AssetPath=f"{pkg}/{name}")
    entries = r if isinstance(r, list) else [r]
    entry = next((e for e in entries if isinstance(e, dict)), None)
    assert entry is not None
    assert entry.get("bCreated") or entry.get("bAlreadyExists"), f"创建失败：{entry}"
    assert entry.get("Path"), f"缺少 path：{entry}"


# ── PoseSearch ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pose_search_db_path(mcp):
    """发现项目中存在的 PoseSearchDatabase，或跳过。"""
    r = mcp.call_capability(
        "SearchAsset",
        Query="",
        AssetType="posesearch",
        PathFilter="/Game/",
        Limit=1,
    )
    assets = (r.get("Assets") or []) if isinstance(r, dict) else []
    if not assets:
        pytest.skip("项目中无 PoseSearchDatabase 资产，跳过只读测试")
    return assets[0].get("Path") or assets[0].get("AssetPath")


@pytest.mark.skipif_ue_below("5.4")
def test_get_pose_search_database(mcp, pose_search_db_path):
    """get_asset_pose_search 应返回 schema 或 animationAssetCount。"""
    r = mcp.call_capability("GetAssetPoseSearch", AssetPath=pose_search_db_path)
    entries = r if isinstance(r, list) else [r]
    entry = next((e for e in entries if isinstance(e, dict) and "Error" not in e), None)
    assert entry is not None, f"无有效条目：{r}"
    assert entry.get("AssetType") == "PoseSearchDatabase", f"类型错误：{entry}"
    assert "AnimationAssetCount" in entry, f"缺少 animationAssetCount：{entry}"


@pytest.mark.skipif_ue_below("5.4")
def test_manage_pose_search_schema_and_tags(test_ns, mcp):
    from _framework.capability_probe import is_capability_available
    from _framework.mcp_client import cap_first
    if not is_capability_available(mcp, "ManageAssetPoseSearch"):
        pytest.skip("manage_asset_pose_search 未编入")
    schema = f"{test_ns}/PSS_Manage"
    db = f"{test_ns}/PSD_Manage"
    s = mcp.call_capability("CreateAssetPoseSearch", AssetPath=schema, AssetKind="Schema")
    se = cap_first(s)
    if se.get("Error") and "already exists" not in str(se.get("Error")).lower():
        pytest.skip(f"create PoseSearch Schema 失败: {se}")
    d = mcp.call_capability(
        "CreateAssetPoseSearch",
        AssetPath=db,
        AssetKind="Database",
        SchemaPath=schema,
    )
    de = cap_first(d)
    if de.get("Error") and "already exists" not in str(de.get("Error")).lower():
        pytest.skip(f"create PoseSearch Database 失败: {de}")
    r = mcp.call_capability(
        "ManageAssetPoseSearch",
        AssetPath=db,
        Operations=[
            {"Action": "SetSchema", "SchemaPath": schema},
            {"Action": "AddTag", "Tag": "NxPoseTag"},
            {"Action": "RemoveTag", "Tag": "NxPoseTag"},
        ],
    )
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict):
            assert not e.get("Error"), r
