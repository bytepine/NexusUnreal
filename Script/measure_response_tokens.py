#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright byteyang. All Rights Reserved.
"""量化 MCP 响应默认值压缩带来的 byte / token 节省。

用法：
    # 连接现成 UE 编辑器（默认 45000 端口）
    python nexus-unreal/Script/measure_response_tokens.py

    # 指定完整 MCP stream URL
    python nexus-unreal/Script/measure_response_tokens.py --ue-url http://127.0.0.1:45002/stream

脚本对若干典型只读工具发起调用，本地反演压缩前原始条目，对比：
    - 压缩后 JSON 字节数（即 UE 实际回传的体积）
    - 还原后 JSON 字节数（假设关闭默认值压缩应有的体积）
    - token 估算（tiktoken 可用时用 cl100k_base，否则按 4 字符 ≈ 1 token 粗估）
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
TESTS_DIR = SCRIPT_DIR.parent / "Tests"
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from _framework.mcp_client import MCPClient, MCPError  # noqa: E402


# ─────────────────────────────────────────────────────────────
# 还原：把 <prefix>_defaults 合并回每个条目
# ─────────────────────────────────────────────────────────────

def _expand_defaults(container: Dict[str, Any], list_key: str, prefix: str) -> Dict[str, Any]:
    """返回副本：把 defaults 合并到列表每项后，删除 defaults 键。"""
    dup = copy.deepcopy(container)
    items = dup.get(list_key)
    defaults = dup.get(f"{prefix}_defaults") or {}
    if isinstance(items, list) and isinstance(defaults, dict) and defaults:
        for i, entry in enumerate(items):
            if not isinstance(entry, dict):
                continue
            combined = dict(defaults)
            combined.update(entry)
            items[i] = combined
    dup.pop(f"{prefix}_defaults", None)
    return dup


def _expand_nested_defaults(
    container: Dict[str, Any],
    outer_list_key: str,
    inner_list_key: str,
    inner_prefix: str,
) -> Dict[str, Any]:
    """对 container[outer_list_key] 里每个 entry 独立反演其 <inner_prefix>_defaults。

    用于 get_asset_refs：refs_defaults 嵌在每个 results[i] 里。
    """
    dup = copy.deepcopy(container)
    outer = dup.get(outer_list_key)
    if not isinstance(outer, list):
        return dup
    for entry in outer:
        if not isinstance(entry, dict):
            continue
        inner = entry.get(inner_list_key)
        defaults = entry.get(f"{inner_prefix}_defaults") or {}
        if isinstance(inner, list) and isinstance(defaults, dict) and defaults:
            for i, sub in enumerate(inner):
                if not isinstance(sub, dict):
                    continue
                combined = dict(defaults)
                combined.update(sub)
                inner[i] = combined
        entry.pop(f"{inner_prefix}_defaults", None)
    return dup


def _expand_diff_baseline(container: Dict[str, Any]) -> Dict[str, Any]:
    """把 baseline.values 回填到每条 diff 的 valueA 字段，反演 P2 压缩。"""
    dup = copy.deepcopy(container)
    baseline = dup.get("baseline") or {}
    values = baseline.get("Values") if isinstance(baseline, dict) else None
    if not isinstance(values, dict) or not values:
        return dup

    for comp in dup.get("comparisons") or []:
        if not isinstance(comp, dict):
            continue
        for d in comp.get("Diffs") or []:
            if not isinstance(d, dict):
                continue
            path = d.get("Path")
            if isinstance(path, str) and path in values and "ValueA" not in d:
                d["ValueA"] = values[path]
    baseline.pop("Values", None)
    return dup


# ─────────────────────────────────────────────────────────────
# 字节 / token 估算
# ─────────────────────────────────────────────────────────────

def _json_bytes(obj: Any) -> int:
    return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _token_count(obj: Any, encoder) -> int:
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


# ─────────────────────────────────────────────────────────────
# 场景定义
# ─────────────────────────────────────────────────────────────

def _probe_asset_path(mcp: MCPClient) -> Optional[str]:
    try:
        r = mcp.call("SearchAsset", AssetType="Blueprint", Limit=1)
    except MCPError:
        return None
    assets = r.get("Assets") or []
    if not assets:
        return None
    first = assets[0]
    return first.get("Path") or first.get("AssetPath")


def _probe_actor_names(mcp: MCPClient, max_count: int = 5) -> List[str]:
    try:
        r = mcp.call("list_actors", Limit=50)
    except MCPError:
        return []
    out: List[str] = []
    defaults = r.get("actors_defaults") or {}
    for a in r.get("Actors") or []:
        if not isinstance(a, dict):
            continue
        name = a.get("name") or defaults.get("name")
        if name:
            out.append(name)
        if len(out) >= max_count:
            break
    return out


def _scenarios(mcp: MCPClient) -> List[Tuple[str, Dict[str, Any], List[Tuple[str, str]]]]:
    """
    返回 [(场景名, 响应体, [(list_key, prefix), ...]), ...]；特殊工具 diff_actors 单独处理。
    """
    out: List[Tuple[str, Dict[str, Any], List[Tuple[str, str]]]] = []

    # list_actors
    try:
        r = mcp.call("list_actors", Limit=200)
        out.append(("list_actors", r, [("Actors", "Actors")]))
    except MCPError as e:
        print(f"[skip] list_actors: {e}", File=sys.stderr)

    # search_asset (Blueprint-only 扎堆)
    try:
        r = mcp.call("SearchAsset", AssetType="Blueprint", Limit=200)
        out.append(("search_asset(AssetType=Blueprint)", r, [("Assets", "Assets")]))
    except MCPError as e:
        print(f"[skip] search_asset Blueprint: {e}", File=sys.stderr)

    # search_asset all
    try:
        r = mcp.call("SearchAsset", AssetType="All", Limit=200)
        out.append(("search_asset(AssetType=all)", r, [("Assets", "Assets")]))
    except MCPError as e:
        print(f"[skip] search_asset all: {e}", File=sys.stderr)

    # get_asset Section=all（单个 BP）
    bp = _probe_asset_path(mcp)
    if bp:
        try:
            r = mcp.call("GetAsset", assetPaths=[bp], Section="All")
            # get_asset 是批量返回 results[]，每项一个 BP；取第一个做度量
            first = (r.get("Results") or [{}])[0]
            if isinstance(first, dict) and not first.get("Error"):
                out.append((
                    f"get_asset({bp}, Section=all)", first,
                    [("properties", "properties"), ("Graphs", "Graphs")],
                ))
        except MCPError as e:
            print(f"[skip] get_asset: {e}", File=sys.stderr)

    # get_asset BP Section=defaults（inherited:true 占主导）
    if bp:
        try:
            r = mcp.call("GetAsset", assetPaths=[bp], Section="Defaults", Limit=200)
            first = (r.get("Results") or [{}])[0]
            if isinstance(first, dict) and not first.get("Error") and isinstance(first.get("Defaults"), list):
                out.append((
                    f"get_asset({bp.rsplit('/', 1)[-1]}, Section=defaults)",
                    first, [("Defaults", "Defaults")],
                ))
        except MCPError as e:
            print(f"[skip] get_asset defaults: {e}", File=sys.stderr)

    # get_asset BP Section=graph（指定 graphName，单图内节点 nodeClass 扎堆最高）
    if bp:
        try:
            overview = mcp.call("GetAsset", assetPaths=[bp], Section="graph")
            entries = overview.get("Results") or []
            first = entries[0] if entries else {}
            graphs_list = first.get("Graphs") or []
            graphs_defaults = first.get("graphs_defaults") or {}
            target_graph = None
            for g in graphs_list:
                if not isinstance(g, dict):
                    continue
                node_count = g.get("NodeCount", graphs_defaults.get("NodeCount", 0))
                if node_count and node_count > 0 and g.get("GraphName"):
                    target_graph = g["GraphName"]
                    break
            if target_graph:
                gr = mcp.call("GetAsset", assetPaths=[bp], Section="graph", GraphName=target_graph)
                gfirst = (gr.get("Results") or [{}])[0]
                if isinstance(gfirst, dict) and not gfirst.get("Error"):
                    out.append((
                        f"get_asset(graph={target_graph}, BP={bp.rsplit('/', 1)[-1]})",
                        gfirst, [("Nodes", "Nodes")],
                    ))
        except MCPError as e:
            print(f"[skip] get_asset graph: {e}", File=sys.stderr)

    # get_asset Material Section=params
    mat = None
    try:
        lr = mcp.call("SearchAsset", AssetType="Material", Limit=1)
        la = lr.get("Assets") or []
        if la:
            mat_defaults = lr.get("assets_defaults") or {}
            combined = dict(mat_defaults); combined.update(la[0])
            mat = combined.get("Path") or combined.get("AssetPath")
    except MCPError:
        pass
    if mat:
        try:
            r = mcp.call("GetAsset", assetPaths=[mat], Section="Params")
            first = (r.get("Results") or [{}])[0]
            if isinstance(first, dict) and not first.get("Error") and isinstance(first.get("Parameters"), list):
                out.append((
                    f"get_asset(Material params)", first,
                    [("Parameters", "Parameters")],
                ))
        except MCPError as e:
            print(f"[skip] get_asset Material params: {e}", File=sys.stderr)

    # get_asset UserDefinedStruct
    uds = None
    try:
        lr = mcp.call("SearchAsset", AssetType="UserDefinedStruct", Limit=1)
        la = lr.get("Assets") or []
        if la:
            uds_defaults = lr.get("assets_defaults") or {}
            combined = dict(uds_defaults); combined.update(la[0])
            uds = combined.get("Path") or combined.get("AssetPath")
    except MCPError:
        pass
    if uds:
        try:
            r = mcp.call("GetAsset", assetPaths=[uds])
            first = (r.get("Results") or [{}])[0]
            if isinstance(first, dict) and not first.get("Error") and isinstance(first.get("Fields"), list):
                out.append((
                    f"get_asset(Struct fields)", first,
                    [("Fields", "Fields")],
                ))
        except MCPError as e:
            print(f"[skip] get_asset Struct: {e}", File=sys.stderr)

    # get_asset_user_widget
    wbp = None
    try:
        lr = mcp.call("SearchAsset", AssetType="WidgetBlueprint", Limit=1)
        la = lr.get("Assets") or []
        if la:
            wbp_defaults = lr.get("assets_defaults") or {}
            combined = dict(wbp_defaults); combined.update(la[0])
            wbp = combined.get("Path") or combined.get("AssetPath")
    except MCPError:
        pass
    if wbp:
        try:
            r = mcp.call("GetAssetUserWidget", AssetPath=wbp, Limit=500)
            out.append((
                f"get_asset_user_widget({wbp.rsplit('/', 1)[-1]})", r,
                [("Widgets", "Widgets")],
            ))
        except MCPError as e:
            print(f"[skip] get_asset_user_widget: {e}", File=sys.stderr)

    # list_runtime_widgets（PIE 中才有数据；无数据自动无场景）
    try:
        r = mcp.call("ListRuntimeWidgets", Limit=500)
        if r.get("Widgets"):
            out.append(("ListRuntimeWidgets", r, [("Widgets", "Widgets")]))
    except MCPError as e:
        print(f"[skip] list_runtime_widgets: {e}", File=sys.stderr)

    # get_output_log（无 categoryFilter，统计路径）
    try:
        r = mcp.call("GetOutputLog", Limit=500, Verbosity="Log")
        if r.get("Entries"):
            out.append(("get_output_log(Limit=500)", r, [("Entries", "Entries")]))
    except MCPError as e:
        print(f"[skip] get_output_log: {e}", File=sys.stderr)

    # get_output_log（categoryFilter 强制默认路径，P0 优化）
    try:
        r = mcp.call("GetOutputLog", CategoryFilter="LogTemp", Limit=200, Verbosity="All")
        if r.get("Entries"):
            out.append(("get_output_log(CategoryFilter=LogTemp)", r, [("Entries", "Entries")]))
    except MCPError as e:
        print(f"[skip] get_output_log categoryFilter: {e}", File=sys.stderr)

    # get_gameplay_tags hierarchy（树 children 或扁平 tags）
    try:
        r = mcp.call("GetGameplayTags", Section="Hierarchy", Limit=500)
        if r.get("Tags"):
            out.append(("get_gameplay_tags(hierarchy)", r, [("Tags", "Tags")]))
    except MCPError as e:
        print(f"[skip] get_gameplay_tags: {e}", File=sys.stderr)

    # get_actor_animation Section=variables（type + value 字段扎堆）
    try:
        actors_r = mcp.call("list_actors", Limit=50)
        actors = actors_r.get("Actors") or []
        act_def = actors_r.get("actors_defaults") or {}
        anim_target = None
        for a in actors:
            combined = dict(act_def); combined.update(a)
            cls = combined.get("Class", "")
            if "Character" in cls or "Pawn" in cls:
                anim_target = combined.get("name")
                break
        if anim_target:
            r = mcp.call("get_actor_animation", ActorName=anim_target, Section="Variables")
            results = r.get("Results") or []
            first = results[0] if results else {}
            if isinstance(first.get("Variables"), list):
                out.append((
                    f"get_actor_animation(variables,{anim_target})",
                    first, [("Variables", "Variables")],
                ))
    except MCPError as e:
        print(f"[skip] get_actor_animation variables: {e}", File=sys.stderr)

    # get_behavior_tree blackboard（P2：type 字段扎堆）
    bt_asset = None
    try:
        lr = mcp.call("SearchAsset", AssetType="BehaviorTree", Limit=1)
        la = lr.get("Assets") or []
        if la:
            bt_defaults = lr.get("assets_defaults") or {}
            combined = dict(bt_defaults); combined.update(la[0])
            bt_asset = combined.get("Path") or combined.get("AssetPath")
    except MCPError:
        pass
    if bt_asset:
        try:
            r = mcp.call("get_behavior_tree", Section="Blackboard", AssetPath=bt_asset)
            if r.get("Keys"):
                out.append((
                    f"get_behavior_tree(blackboard,{bt_asset.rsplit('/', 1)[-1]})",
                    r, [("Keys", "Keys")],
                ))
        except MCPError as e:
            print(f"[skip] get_behavior_tree blackboard: {e}", File=sys.stderr)

    # get_property Section=all（Actor 组件树；components_defaults / hierarchy_defaults 压缩）
    actor_names = _probe_actor_names(mcp, max_count=1)
    if actor_names:
        try:
            r = mcp.call("get_property", ActorName=actor_names[0], Section="All")
            if r.get("Components") or r.get("Hierarchy"):
                out.append((
                    f"get_property({actor_names[0][:20]},Section=all)",
                    r,
                    [("Components", "Components"), ("Hierarchy", "Hierarchy")],
                ))
        except MCPError as e:
            print(f"[skip] get_property Section=all: {e}", File=sys.stderr)

    return out


def _measure_asset_refs(mcp: MCPClient) -> Optional[Tuple[str, Dict[str, Any]]]:
    """get_asset_refs 的 refs_defaults 嵌在每个 results[i] 里，需走嵌套反演。"""
    bp = _probe_asset_path(mcp)
    if not bp:
        return None
    try:
        r = mcp.call("GetAssetRefs", assetPaths=[bp], Direction="Dependencies", Limit=500)
    except MCPError as e:
        print(f"[skip] get_asset_refs: {e}", File=sys.stderr)
        return None
    if not r.get("Results"):
        return None
    return (f"get_asset_refs({bp.rsplit('/', 1)[-1]})", r)


def _measure_diff_actors(mcp: MCPClient) -> Optional[Tuple[str, Dict[str, Any]]]:
    names = _probe_actor_names(mcp, max_count=4)
    if len(names) < 2:
        return None
    try:
        r = mcp.call("diff_actors", actorNames=names)
    except MCPError as e:
        print(f"[skip] diff_actors: {e}", File=sys.stderr)
        return None
    return (f"diff_actors(N={len(names)})", r)


# ─────────────────────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Measure NexusMCP response compaction savings")
    ap.add_argument("--ue-url", default="http://127.0.0.1:45000/stream",
                    help="MCP Streamable HTTP endpoint (default: http://127.0.0.1:45000/stream)")
    args = ap.parse_args()

    encoder = _load_tiktoken()
    if encoder is None:
        print("[info] tiktoken not installed — token count is a 4-char heuristic", File=sys.stderr)

    mcp = MCPClient(args.ue_url)
    try:
        mcp.initialize()
    except Exception as e:
        print(f"[fatal] initialize failed: {e}", File=sys.stderr)
        return 2

    rows: List[Tuple[str, int, int, int, int]] = []  # (name, after_bytes, before_bytes, after_tokens, before_tokens)

    for name, body, pairs in _scenarios(mcp):
        expanded = body
        for list_key, prefix in pairs:
            expanded = _expand_defaults(expanded, list_key, prefix)
        after_b = _json_bytes(body)
        before_b = _json_bytes(expanded)
        after_t = _token_count(body, encoder)
        before_t = _token_count(expanded, encoder)
        rows.append((name, after_b, before_b, after_t, before_t))

    refs = _measure_asset_refs(mcp)
    if refs:
        name, body = refs
        expanded = _expand_nested_defaults(body, "Results", "Refs", "Refs")
        after_b = _json_bytes(body)
        before_b = _json_bytes(expanded)
        after_t = _token_count(body, encoder)
        before_t = _token_count(expanded, encoder)
        rows.append((name, after_b, before_b, after_t, before_t))

    diff = _measure_diff_actors(mcp)
    if diff:
        name, body = diff
        expanded = _expand_diff_baseline(body)
        after_b = _json_bytes(body)
        before_b = _json_bytes(expanded)
        after_t = _token_count(body, encoder)
        before_t = _token_count(expanded, encoder)
        rows.append((name, after_b, before_b, after_t, before_t))

    # 输出表格
    header = f"{'scenario':<42}{'after(B)':>12}{'before(B)':>12}{'save':>10}{'after(tok)':>12}{'before(tok)':>14}{'save':>10}"
    print(header)
    print("-" * len(header))
    total_after_b = total_before_b = total_after_t = total_before_t = 0
    for name, ab, bb, at, bt in rows:
        save_b = 1.0 - (ab / bb) if bb > 0 else 0.0
        save_t = 1.0 - (at / bt) if bt > 0 else 0.0
        print(f"{name[:42]:<42}{ab:>12}{bb:>12}{save_b*100:>9.1f}%{at:>12}{bt:>14}{save_t*100:>9.1f}%")
        total_after_b += ab
        total_before_b += bb
        total_after_t += at
        total_before_t += bt

    if rows:
        print("-" * len(header))
        tsb = 1.0 - (total_after_b / total_before_b) if total_before_b else 0.0
        tst = 1.0 - (total_after_t / total_before_t) if total_before_t else 0.0
        print(
            f"{'TOTAL':<42}{total_after_b:>12}{total_before_b:>12}{tsb*100:>9.1f}%"
            f"{total_after_t:>12}{total_before_t:>14}{tst*100:>9.1f}%"
        )
    else:
        print("[warn] no scenarios were measured", File=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
