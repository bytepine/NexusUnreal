#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright byteyang. All Rights Reserved.
"""建立 MCP Token 优化基线。

测量内容：
  1. tools/list 整体响应字节数与 token 估算
  2. 代表工具响应：get_asset(section=all) / list_actors / get_output_log
     - structured_bytes: structuredContent 字节数（AI 实际消费）
     - full_response_bytes: 完整 MCP 响应包字节数（content+structuredContent，用于 P0 前后对比）
  3. 结果写入 nexus-unreal/Tests/_baselines/token_baseline.json

用法：
    python nexus-unreal/Script/measure_token_baseline.py
    python nexus-unreal/Script/measure_token_baseline.py --ue-url http://127.0.0.1:45002/stream
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
TESTS_DIR = SCRIPT_DIR.parent / "Tests"
BASELINES_DIR = TESTS_DIR / "_baselines"

if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from _framework.mcp_client import MCPClient, MCPError  # noqa: E402


# ─────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────

def _json_bytes(obj: Any) -> int:
    """序列化为紧凑 JSON 后的 UTF-8 字节数。"""
    return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _token_estimate(obj: Any, encoder) -> int:
    """token 估算：tiktoken 可用时用 cl100k_base，否则 4 字符 ≈ 1 token。"""
    text = json.dumps(obj, ensure_ascii=False)
    if encoder is None:
        return max(1, len(text) // 4)
    return len(encoder.encode(text))


def _load_tiktoken():
    try:
        import tiktoken  # type: ignore
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def _probe_asset_path(mcp: MCPClient) -> Optional[str]:
    """探测一个 Blueprint 资产路径，用于 get_asset 测量。"""
    try:
        r = mcp.call("search_asset", assetType="Blueprint", limit=1)
    except MCPError:
        return None
    assets = r.get("assets") or []
    if not assets:
        return None
    first = assets[0]
    # 兼容 assets_defaults 压缩
    defaults = r.get("assets_defaults") or {}
    combined = dict(defaults)
    combined.update(first)
    return combined.get("path") or combined.get("assetPath")


def _measure_entry(structured: Any, full_response: Any, encoder) -> Dict[str, Any]:
    """计算 structuredContent 和完整响应包的字节数与 token 数。"""
    sb = _json_bytes(structured)
    st = _token_estimate(structured, encoder)
    fb = _json_bytes(full_response)
    ft = _token_estimate(full_response, encoder)
    return {
        "structured_bytes": sb,
        "structured_tokens": st,
        "full_response_bytes": fb,
        "full_response_tokens": ft,
    }


# ─────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="建立 NexusMCP Token 优化基线")
    ap.add_argument("--ue-url", default="http://127.0.0.1:45000/stream",
                    help="MCP Streamable HTTP 端点（默认: http://127.0.0.1:45000/stream）")
    ap.add_argument("--output", default=str(BASELINES_DIR / "token_baseline.json"),
                    help="输出 JSON 文件路径")
    args = ap.parse_args()

    encoder = _load_tiktoken()
    if encoder is None:
        print("[info] tiktoken 未安装 — token 数按 4 字符 ≈ 1 token 粗估", file=sys.stderr)

    mcp = MCPClient(args.ue_url)
    try:
        mcp.initialize()
    except Exception as e:
        print(f"[fatal] initialize 失败: {e}", file=sys.stderr)
        return 2

    baseline: Dict[str, Any] = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "ue_url": args.ue_url,
        "token_estimator": "cl100k_base" if encoder else "4char_heuristic",
        "tools_list": {},
        "tool_responses": {},
    }

    # ── 1. tools/list 整体尺寸 ──
    print("测量 tools/list ...", end=" ", flush=True)
    try:
        tools = mcp.list_tools()
        # tools/list 无 structuredContent 概念，两者相同
        tools_list_result = {"tools": tools}
        entry = _measure_entry(tools_list_result, tools_list_result, encoder)
        entry["tool_count"] = len(tools)
        baseline["tools_list"] = entry
        print(f"OK  {len(tools)} 工具, {entry['structured_bytes']} 字节, ~{entry['structured_tokens']} tokens")
    except MCPError as e:
        print(f"FAIL 失败: {e}", file=sys.stderr)

    # ── 2. 代表工具响应 ──
    probe_tools = []

    # list_actors
    print("测量 list_actors ...", end=" ", flush=True)
    try:
        full = mcp.try_call("list_actors", limit=200)
        structured = full.get("structuredContent") or {}
        entry = _measure_entry(structured, full, encoder)
        entry["item_count"] = len(structured.get("actors") or [])
        baseline["tool_responses"]["list_actors"] = entry
        probe_tools.append("list_actors")
        print(f"OK  structured={entry['structured_bytes']}B full={entry['full_response_bytes']}B ~{entry['structured_tokens']} tokens")
    except MCPError as e:
        print(f"SKIP 跳过: {e}", file=sys.stderr)

    # get_asset(section=all)
    bp = _probe_asset_path(mcp)
    if bp:
        print(f"测量 get_asset(section=all, {bp.rsplit('/', 1)[-1]}) ...", end=" ", flush=True)
        try:
            full = mcp.try_call("get_asset", assetPaths=[bp], section="all")
            structured = full.get("structuredContent") or {}
            entry = _measure_entry(structured, full, encoder)
            entry["asset_path"] = bp
            baseline["tool_responses"]["get_asset_section_all"] = entry
            probe_tools.append("get_asset")
            print(f"OK  structured={entry['structured_bytes']}B full={entry['full_response_bytes']}B ~{entry['structured_tokens']} tokens")
        except MCPError as e:
            print(f"SKIP 跳过: {e}", file=sys.stderr)
    else:
        print("[skip] get_asset — 未找到 Blueprint 资产", file=sys.stderr)

    # get_output_log
    print("测量 get_output_log ...", end=" ", flush=True)
    try:
        full = mcp.try_call("get_output_log", limit=500, verbosity="log")
        structured = full.get("structuredContent") or {}
        entry = _measure_entry(structured, full, encoder)
        entry["item_count"] = len(structured.get("entries") or [])
        baseline["tool_responses"]["get_output_log"] = entry
        probe_tools.append("get_output_log")
        print(f"OK  structured={entry['structured_bytes']}B full={entry['full_response_bytes']}B ~{entry['structured_tokens']} tokens")
    except MCPError as e:
        print(f"SKIP 跳过: {e}", file=sys.stderr)

    mcp.close()

    # ── 3. 写入基线文件 ──
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)

    print(f"\n基线已写入: {output_path}")

    # ── 4. 汇总打印 ──
    print("\n── 基线摘要 ──")
    tl = baseline.get("tools_list", {})
    if tl:
        print(f"  tools/list : {tl.get('tool_count', '?')} 工具, "
              f"{tl.get('structured_bytes', '?')} 字节, ~{tl.get('structured_tokens', '?')} tokens")
    for key, entry in baseline.get("tool_responses", {}).items():
        print(f"  {key:<30}: structured={entry.get('structured_bytes', '?')}B "
              f"full={entry.get('full_response_bytes', '?')}B "
              f"~{entry.get('structured_tokens', '?')} tokens")

    return 0


if __name__ == "__main__":
    sys.exit(main())
