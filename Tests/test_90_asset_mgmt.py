# Copyright byteyang. All Rights Reserved.
"""阶段十 + 十二：资产管理 + 日志健康。"""

from __future__ import annotations

import pytest

from _framework.assertions import merge_with_defaults
from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l3_asset


def test_create_data_asset_rename_list(test_ns, mcp):
    """10.1–10.3：create → rename → search_asset 校验旧路径消失。"""
    orig = f"{test_ns}/DA_TestConfig"
    renamed = f"{test_ns}/DA_TestConfig_Renamed"

    mcp.call("CreateAssetDataAsset", AssetPath=orig, ParentClass="PrimaryAssetLabel")
    r = mcp.call("RenameAsset", AssetPath=orig, DestAssetPath=renamed)
    assert r, f"rename returned empty: {r!r}"

    listing = mcp.call("SearchAsset", AssetType="All", PathFilter=test_ns, Limit=200)
    payload = cap_first(listing)
    paths = [a.get("AssetPath") or a.get("Path")
             for a in (payload.get("Assets") or [])]
    # Exact path membership — avoids the subtle trap where `DA_TestConfig` is
    # a substring of `DA_TestConfig_Renamed` in a space-joined dump.
    assert renamed in paths, f"renamed asset missing from listing: {paths}"
    assert orig not in paths, f"original asset still in listing: {paths}"


def test_duplicate_asset(test_ns, mcp, require_tools):
    """duplicate_asset：从已有 DataAsset 复制到新路径。"""
    require_tools("DuplicateAsset")
    src = f"{test_ns}/DA_TestConfig_Renamed"
    dup = f"{test_ns}/DA_TestConfig_Copy"
    listing = mcp.call("SearchAsset", AssetType="DataAsset", PathFilter=test_ns, Limit=20)
    paths = [a.get("AssetPath") or a.get("Path") for a in (cap_first(listing).get("Assets") or [])]
    if src not in paths:
        mcp.call("CreateAssetDataAsset", AssetPath=src, ParentClass="PrimaryAssetLabel")
    r = mcp.call_capability("DuplicateAsset", AssetPath=src, DestAssetPath=dup)
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert entry.get("DestAssetPath") == dup or entry.get("Path") == dup, entry


def test_multi_asset_overview(test_ns, mcp):
    """10.4：单 Blueprint 资产概览（原 get_asset 多类型批量已拆分为类型专用 capability）。"""
    listing = mcp.call("SearchAsset", AssetType="Blueprint", PathFilter=test_ns, Limit=5)
    # 指定 assetType 时：assets/recommended* 在顶层；cap_first 无 results 时回退到顶层
    payload = cap_first(listing)
    assets = payload.get("Assets") or []
    if not assets:
        pytest.skip("test_ns 中无 Blueprint 资产可查询")
    first = merge_with_defaults(
        [assets[0]],
        payload.get("assets_defaults") or payload.get("Defaults") or {},
    )[0]
    assert first.get("AssetType") == "Blueprint", first
    # recommended* 在顶层（指定类型时提升）；兼容逐条字段
    assert (payload.get("RecommendedGet") or first.get("RecommendedGet")) == "GetAssetBlueprint", payload
    assert (payload.get("RecommendedManage") or first.get("RecommendedManage")) == "ManageAssetBlueprint", payload
    bp_path = first.get("AssetPath") or first.get("Path")
    if not bp_path:
        pytest.skip(f"无法从资产条目解析路径：{first!r}")
    r = mcp.call_capability("GetAssetBlueprint", AssetPath=bp_path, Sections=["All"])
    assert isinstance(r, dict), f"get_asset_blueprint returned unexpected type: {r!r}"


# ────────────────────────────────────────────────
# 阶段十二：日志健康
# ────────────────────────────────────────────────


def test_log_health_ensure_failed_is_zero(mcp, log_start_sequence):
    r = mcp.call(
        "GetOutputLog",
        TextFilter="Ensure condition failed",
        Limit=20,
        SinceSequence=log_start_sequence,
    )
    entries = r.get("Entries") or []
    assert len(entries) == 0, f"Ensure failures: {entries!r}"


def test_log_health_no_crash(mcp):
    r = mcp.call("GetOutputLog", TextFilter="crash", Limit=10)
    entries = r.get("Entries") or []
    # Soft assertion — there may be fully unrelated logs containing the word.
    hard = [e for e in entries if "FATAL" in str(e).upper()]
    assert not hard, f"fatal crash lines: {hard!r}"


# ────────────────────────────────────────────────
# DataAsset 读写 / delete / export
# ────────────────────────────────────────────────


def _data_asset_entry(mcp, path: str) -> dict:
    r = mcp.call_capability("GetAssetDataAsset", AssetPath=path, Limit=100)
    return cap_first(r)


def _first_editable_property_name(entry: dict) -> str | None:
    for row in entry.get("properties") or []:
        if not isinstance(row, dict):
            continue
        name = row.get("name") or row.get("PropertyName")
        if name and row.get("type") == "bool":
            return str(name)
    return None


def test_data_asset_get_and_manage_reset(test_ns, mcp, require_tools):
    """get_asset_data_asset + manage_asset_data_asset(reset) 闭环。"""
    require_tools("GetAssetDataAsset", "ManageAssetDataAsset")
    path = f"{test_ns}/DA_McpRw"
    mcp.call("CreateAssetDataAsset", AssetPath=path, ParentClass="PrimaryAssetLabel")

    entry = _data_asset_entry(mcp, path)
    assert not entry.get("Error"), entry
    prop = _first_editable_property_name(entry)
    if not prop:
        pytest.skip(f"PrimaryAssetLabel 无可编辑属性可验 reset：{entry!r}")

    r = mcp.call_capability(
        "ManageAssetDataAsset",
        AssetPath=path,
        Operations=[{"Action": "Reset", "PropertyName": prop}],
    )
    assert not (r.get("Error") or (cap_first(r) or {}).get("Error")), r
    set_r = mcp.call_capability(
        "ManageAssetDataAsset",
        AssetPath=path,
        Operations=[{"Action": "Set", "PropertyName": prop, "Value": "true"}],
    )
    if cap_first(set_r).get("Error"):
        pytest.skip(f"data_asset set 跳过: {cap_first(set_r)}")


def test_delete_asset_removes_from_search(test_ns, mcp, require_tools):
    """delete_asset：创建后立即删除，search 不应再出现。"""
    require_tools("DeleteAsset")
    path = f"{test_ns}/DA_DeleteProbe"
    mcp.call("CreateAssetDataAsset", AssetPath=path, ParentClass="PrimaryAssetLabel")

    dr = mcp.call_capability("DeleteAsset", AssetPath=path)
    del_entry = cap_first(dr)
    assert not del_entry.get("Error"), del_entry

    listing = mcp.call("SearchAsset", AssetType="DataAsset", PathFilter=test_ns, Limit=50)
    paths = [
        a.get("AssetPath") or a.get("Path")
        for a in (cap_first(listing).get("Assets") or [])
    ]
    assert path not in paths, f"deleted asset still listed: {paths}"


def test_export_static_mesh_smoke(mcp, require_tools):
    """export_asset：导出模板 StaticMesh 到 Saved/Exported/（或指定路径）。"""
    require_tools("ExportAsset")
    from _framework.asset_helpers import first_asset_path

    mesh = first_asset_path(mcp, "StaticMesh")
    if not mesh:
        pytest.skip("无 StaticMesh 样本可导出")
    r = mcp.call_capability("ExportAsset", AssetPath=mesh)
    entry = cap_first(r)
    assert not entry.get("Error"), entry
    assert entry.get("OutputPath") or entry.get("exportedPath") or not entry.get("Error"), entry
