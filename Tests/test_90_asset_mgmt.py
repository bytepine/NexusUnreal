# Copyright byteyang. All Rights Reserved.
"""阶段十 + 十二：资产管理 + 日志健康。"""

from __future__ import annotations

import pytest

from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l3_asset


def test_create_data_asset_rename_list(test_ns, mcp):
    """10.1–10.3：create → rename → search_asset 校验旧路径消失。"""
    orig = f"{test_ns}/DA_TestConfig"
    renamed = f"{test_ns}/DA_TestConfig_Renamed"

    mcp.call("create_data_asset", assetPath=orig, parentClass="PrimaryAssetLabel")
    r = mcp.call("rename_asset", assetPath=orig, newPath=renamed)
    assert r, f"rename returned empty: {r!r}"

    listing = mcp.call("search_asset", assetType="all", pathFilter=test_ns, limit=200)
    payload = cap_first(listing)
    paths = [a.get("assetPath") or a.get("path")
             for a in (payload.get("assets") or [])]
    # Exact path membership — avoids the subtle trap where `DA_TestConfig` is
    # a substring of `DA_TestConfig_Renamed` in a space-joined dump.
    assert renamed in paths, f"renamed asset missing from listing: {paths}"
    assert orig not in paths, f"original asset still in listing: {paths}"


def test_duplicate_asset(test_ns, mcp, require_tools):
    """duplicate_asset：从已有 DataAsset 复制到新路径。"""
    require_tools("duplicate_asset")
    src = f"{test_ns}/DA_TestConfig_Renamed"
    dup = f"{test_ns}/DA_TestConfig_Copy"
    listing = mcp.call("search_asset", assetType="DataAsset", pathFilter=test_ns, limit=20)
    paths = [a.get("assetPath") or a.get("path") for a in (cap_first(listing).get("assets") or [])]
    if src not in paths:
        pytest.skip(f"源资产 {src} 不存在，需先跑 test_create_data_asset_rename_list")
    r = mcp.call_capability("duplicate_asset", assetPath=src, newPath=dup)
    results = r.get("results") or [r]
    entry = results[0] if results else r
    assert not entry.get("error"), entry
    assert entry.get("newPath") == dup or entry.get("path") == dup, entry


def test_multi_asset_overview(test_ns, mcp):
    """10.4：单 Blueprint 资产概览（原 get_asset 多类型批量已拆分为类型专用 capability）。"""
    listing = mcp.call("search_asset", assetType="Blueprint", pathFilter=test_ns, limit=5)
    assets = cap_first(listing).get("assets") or []
    if not assets:
        pytest.skip("test_ns 中无 Blueprint 资产可查询")
    bp_path = assets[0].get("assetPath") or assets[0].get("path")
    if not bp_path:
        pytest.skip(f"无法从资产条目解析路径：{assets[0]!r}")
    r = mcp.call_capability("get_asset_blueprint", assetPath=bp_path, sections=["all"])
    assert isinstance(r, dict), f"get_asset_blueprint returned unexpected type: {r!r}"


# ────────────────────────────────────────────────
# 阶段十二：日志健康
# ────────────────────────────────────────────────


def test_log_health_ensure_failed_is_zero(mcp):
    r = mcp.call("get_output_log", textFilter="Ensure condition failed", limit=20)
    entries = r.get("entries") or []
    assert len(entries) == 0, f"Ensure failures: {entries!r}"


def test_log_health_no_crash(mcp):
    r = mcp.call("get_output_log", textFilter="crash", limit=10)
    entries = r.get("entries") or []
    # Soft assertion — there may be fully unrelated logs containing the word.
    hard = [e for e in entries if "FATAL" in str(e).upper()]
    assert not hard, f"fatal crash lines: {hard!r}"
