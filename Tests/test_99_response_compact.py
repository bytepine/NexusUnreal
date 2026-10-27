# Copyright byteyang. All Rights Reserved.
"""阶段十三：响应默认值压缩 —— 验证 list/get/diff 工具的 defaults 抽取契约。

软断言策略：当 defaults 存在时必须是 dict，合并回原条目后必须覆盖所有
"条目里可能被省略"的字段；当数据量不足触发压缩阈值时允许无 defaults，
但条目本身的结构必须保持完整。
"""

from __future__ import annotations

import pytest

from _framework.assertions import (
    assert_respecting_defaults,
    merge_with_defaults,
)
from _framework.asset_helpers import (
    ensure_blueprint,
    ensure_material,
    ensure_struct,
    ensure_widget,
    first_asset_path,
)
from _framework.mcp_client import MCPError, cap_first


pytestmark = pytest.mark.smoke


def test_search_asset_defaults_shape(mcp):
    """search_asset 返回体若产生 assets_defaults，必须是合法 dict 且合并后字段完整。"""
    r = mcp.call("SearchAsset", AssetType="Blueprint", Limit=200)
    merged = assert_respecting_defaults(
        cap_first(r),
        list_key="Assets",
        defaults_prefix="Assets",
        required_fields=("name", "Path", "AssetType"),
        context="search_asset Blueprint",
    )
    for entry in merged:
        assert entry["AssetType"], f"assetType empty after merge: {entry!r}"


def test_search_asset_all_still_valid(mcp):
    """AssetType='All' 下 assetType 值五花八门，多半不触发压缩；条目字段依然完整。"""
    try:
        r = mcp.call("SearchAsset", AssetType="All",
                     PathFilter="/Game/ThirdPersonBP", Limit=50)
    except MCPError as e:
        pytest.skip(f"search_asset all 被安全策略拒绝：{e}")
    assert_respecting_defaults(
        cap_first(r),
        list_key="Assets",
        defaults_prefix="Assets",
        required_fields=("name", "Path", "AssetType"),
        context="search_asset all",
    )


@pytest.mark.requires_gui
def test_list_actors_defaults_shape(mcp, pie):
    """list_runtime_actors 返回体若产生 actors_defaults，必须是合法 dict 且合并后字段完整。"""
    try:
        r = mcp.call("ListRuntimeActors", Limit=200)
    except MCPError as e:
        pytest.skip(f"ListRuntimeActors 需要 PIE：{e}")
    assert_respecting_defaults(
        cap_first(r),
        list_key="Actors",
        defaults_prefix="Actors",
        required_fields=("name", "Class", "Location"),
        context="ListRuntimeActors",
    )


def test_get_asset_blueprint_defaults_shape(mcp):
    """对任意一个 BP 发 Sections=['All']，properties_defaults / graphs_defaults 可选，
    出现时必须是合法 dict 且合并后字段完整。"""
    listing = mcp.call("SearchAsset", AssetType="Blueprint", Limit=1)
    assets = cap_first(listing).get("Assets") or []
    if not assets:
        pytest.skip("项目中无 Blueprint 资产可用于探测")
    bp_path = assets[0].get("Path") or assets[0].get("AssetPath")
    if not bp_path:
        pytest.skip(f"无法从资产列表解析 BP 路径：{assets[0]!r}")

    try:
        bp = mcp.call_capability("GetAssetBlueprint", AssetPath=bp_path, Sections=["All"])
    except MCPError as e:
        pytest.skip(f"get_asset_blueprint 调用失败（{bp_path}）：{e}")

    if bp.get("Error"):
        pytest.skip(f"get_asset_blueprint 返回错误：{bp['Error']}")

    if isinstance(bp.get("properties"), list):
        assert_respecting_defaults(
            bp,
            list_key="properties",
            defaults_prefix="properties",
            required_fields=("name", "Kind"),
            context=f"get_asset_blueprint {bp_path} properties",
        )
    if isinstance(bp.get("Graphs"), list):
        assert_respecting_defaults(
            bp,
            list_key="Graphs",
            defaults_prefix="Graphs",
            required_fields=("GraphName", "GraphType"),
            context=f"get_asset_blueprint {bp_path} graphs",
        )


@pytest.mark.requires_gui
def test_diff_actors_baseline_values_shape(mcp, pie):
    """diff_runtime_actors 批量模式若产出任何 diff，baseline.values 必须是字符串字典，
    且 comparisons[].diffs[] 里不再出现 valueA。"""
    listing = mcp.call("ListRuntimeActors", Limit=10)
    payload = cap_first(listing)
    actors = payload.get("Actors") or []
    merged = merge_with_defaults(actors, payload.get("actors_defaults") or {})
    names = [a.get("name") for a in merged if a.get("name")]
    if len(names) < 2:
        pytest.skip(f"need at least 2 actors for diff_runtime_actors: {names!r}")

    try:
        r = mcp.call(
            "DiffRuntimeActors",
            ActorNameA=names[0],
            ActorNameB=names[1],
        )
    except MCPError as e:
        pytest.skip(f"diff_runtime_actors rejected: {e}")

    baseline = r.get("baseline") or {}
    values = baseline.get("Values")
    if values is not None:
        assert isinstance(values, dict), f"baseline.values must be dict: {values!r}"
        for k, v in values.items():
            assert isinstance(k, str) and k, f"bad baseline.values key: {k!r}"
            assert isinstance(v, str), f"baseline.values[{k}] must be str: {v!r}"

    comparisons = r.get("comparisons") or []
    for comp in comparisons:
        if not isinstance(comp, dict):
            continue
        for d in comp.get("Diffs") or []:
            assert "ValueA" not in d, (
                f"diff still carries valueA (should migrate to baseline.values): {d!r}"
            )


# ─────────────────────────────────────────────────────────────
# 扩展覆盖：P0/P1/P2 新增 7 处接入点
# ─────────────────────────────────────────────────────────────


def _probe_blueprint(mcp, test_ns: str | None = None) -> str | None:
    path = first_asset_path(mcp, "Blueprint")
    if not path and test_ns:
        path = ensure_blueprint(mcp, test_ns, "BP_CompactProbe")
    return path


def _probe_struct(mcp, test_ns: str) -> str:
    path = first_asset_path(mcp, "UserDefinedStruct", path_filter=test_ns)
    if not path:
        path = first_asset_path(mcp, "UserDefinedStruct")
    return path or ensure_struct(mcp, test_ns, "S_CompactProbe")


def _probe_material(mcp, test_ns: str) -> str:
    path = first_asset_path(mcp, "Material") or first_asset_path(mcp, "MaterialInstance")
    return path or ensure_material(mcp, test_ns, "M_CompactProbe")


def _probe_widget(mcp, test_ns: str) -> str:
    path = first_asset_path(mcp, "WidgetBlueprint")
    return path or ensure_widget(mcp, test_ns, "WBP_CompactProbe")


def _probe_blackboard(mcp, test_ns: str) -> str:
    path = first_asset_path(mcp, "Blackboard", path_filter=test_ns)
    if not path:
        path = first_asset_path(mcp, "Blackboard")
    if path:
        return path
    path = f"{test_ns}/BB_CompactProbe"
    mcp.call("CreateAssetBlackboard", AssetPath=path)
    return path


def test_get_asset_refs_defaults_shape(mcp, test_ns):
    """get_asset_refs 的 refs_defaults 嵌在条目内（单条提升后即顶层）。"""
    bp = _probe_blueprint(mcp, test_ns)
    assert bp, "无法定位或创建 Blueprint 探测资产"

    try:
        r = mcp.call("GetAssetRefs", AssetPath=bp, Direction="Dependencies")
    except MCPError as e:
        pytest.skip(f"get_asset_refs 调用失败：{e}")

    entries = [cap_first(r)] if cap_first(r) else []
    assert entries, f"get_asset_refs returned no results: {r!r}"
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("Error"):
            continue
        if not isinstance(entry.get("Refs"), list):
            continue
        assert_respecting_defaults(
            entry,
            list_key="Refs",
            defaults_prefix="Refs",
            required_fields=("Path",),
            context=f"get_asset_refs {entry.get('AssetPath') or entry.get('Path')}",
        )


def test_get_asset_graph_nodes_defaults_shape(mcp, test_ns):
    """BP Sections=['graph'] 指定 graphName 的 nodes_defaults（候选 nodeClass）。"""
    bp = _probe_blueprint(mcp, test_ns)
    assert bp, "无法定位或创建 Blueprint 探测资产"

    try:
        overview = mcp.call_capability("GetAssetBlueprint", AssetPath=bp, Sections=["graph"])
    except MCPError as e:
        pytest.skip(f"get_asset_blueprint graph 概览失败：{e}")

    if overview.get("Error"):
        pytest.skip(f"get_asset_blueprint graph 概览返回错误：{overview['Error']!r}")
    graphs_list = overview.get("Graphs") or []
    graphs = merge_with_defaults(graphs_list, overview.get("graphs_defaults") or {})
    target_graph = next(
        (g.get("GraphName") for g in graphs if g.get("NodeCount", 0) > 0 and g.get("GraphName")),
        None,
    )
    if not target_graph:
        pytest.skip(f"no non-empty graph on {bp}: {graphs!r}")

    try:
        r = mcp.call_capability("GetAssetBlueprint", AssetPath=bp,
                                Sections=["graph"], GraphName=target_graph)
    except MCPError as e:
        pytest.skip(f"get_asset_blueprint graph {target_graph} 失败：{e}")

    if r.get("Error"):
        pytest.skip(f"graph 节点查询返回错误：{r['Error']!r}")
    assert_respecting_defaults(
        r,
        list_key="Nodes",
        defaults_prefix="Nodes",
        required_fields=("NodeId", "NodeClass"),
        context=f"get_asset_blueprint graph {bp}:{target_graph}",
    )


def test_get_asset_struct_fields_defaults_shape(mcp, test_ns):
    """UserDefinedStruct fields_defaults（候选 type）。"""
    path = _probe_struct(mcp, test_ns)

    try:
        r = mcp.call_capability("GetAssetStruct", AssetPath=path)
    except MCPError as e:
        pytest.skip(f"get_asset_struct 调用失败：{e}")

    if r.get("Error"):
        pytest.skip(f"get_asset_struct 返回错误：{r['Error']!r}")
    if not isinstance(r.get("Fields"), list):
        pytest.skip(f"struct 无 fields 列表：{r!r}")

    assert_respecting_defaults(
        r,
        list_key="Fields",
        defaults_prefix="Fields",
        required_fields=("name", "type"),
        context=f"get_asset_struct {path}",
    )


def test_get_asset_material_params_defaults_shape(mcp, test_ns):
    """Material/MaterialInstance params 返回体的 parameters_defaults（候选 paramType）。"""
    path = _probe_material(mcp, test_ns)

    try:
        r = mcp.call_capability("GetAssetMaterial", AssetPath=path, Sections=["Params"])
    except MCPError as e:
        pytest.skip(f"get_asset_material 调用失败：{e}")

    if r.get("Error"):
        pytest.skip(f"get_asset_material 返回错误：{r['Error']!r}")
    if not isinstance(r.get("Parameters"), list):
        pytest.skip(f"返回体无 parameters 列表：{r!r}")

    merged = merge_with_defaults(r["Parameters"], r.get("parameters_defaults") or {})
    for entry in merged:
        assert "ParamType" in entry, (
            f"parameters[].paramType missing after merge: {entry!r} "
            f"Defaults={r.get('parameters_defaults')!r}"
        )


def test_get_asset_user_widget_defaults_shape(mcp, test_ns):
    """get_asset_user_widget widgets_defaults（候选 class）。"""
    path = _probe_widget(mcp, test_ns)

    try:
        r = mcp.call("GetAssetUserWidget", AssetPath=path)
    except MCPError as e:
        pytest.skip(f"get_asset_user_widget 调用失败：{e}")

    payload = cap_first(r)
    assert_respecting_defaults(
        payload,
        list_key="Widgets",
        defaults_prefix="Widgets",
        required_fields=("name", "Class"),
        context=f"get_asset_user_widget {path}",
    )


@pytest.mark.requires_gui
def test_list_runtime_widgets_defaults_shape(mcp, pie):
    """list_runtime_widgets widgets_defaults（候选 widgetClass + class）。
    非 PIE 时可能无数据，跳过。"""
    try:
        r = mcp.call("ListRuntimeWidgets", Limit=200)
    except MCPError as e:
        pytest.skip(f"list_runtime_widgets 失败（可能未进入 PIE）：{e}")

    widgets = r.get("Widgets") or []
    if not widgets:
        pytest.skip("无运行时 Widget（PIE 未启动？）")

    assert_respecting_defaults(
        r,
        list_key="Widgets",
        defaults_prefix="Widgets",
        required_fields=("name", "WidgetClass", "Class"),
        context="ListRuntimeWidgets",
    )


def test_get_output_log_defaults_shape(mcp):
    """get_output_log Entries_defaults（候选 category + verbosity）。"""
    try:
        r = mcp.call("GetOutputLog", Limit=200, Verbosity="Log")
    except MCPError as e:
        pytest.skip(f"get_output_log 调用失败：{e}")

    entries = r.get("Entries") or []
    if not entries:
        pytest.skip("无日志条目")

    merged = merge_with_defaults(entries, r.get("Entries_defaults") or {})
    for entry in merged:
        assert "Verbosity" in entry, (
            f"entries[].verbosity missing after merge: {entry!r} "
            f"Defaults={r.get('Entries_defaults')!r}"
        )


def test_get_output_log_category_filter_forced_default(mcp):
    """categoryFilter 命中后，仅当本页实际 category 全员一致才 ForcedDefault 该值（不是过滤子串）。"""
    try:
        r = mcp.call("GetOutputLog", CategoryFilter="LogTemp", Limit=100, Verbosity="All")
    except MCPError as e:
        pytest.skip(f"get_output_log 调用失败：{e}")

    entries = r.get("Entries") or []
    if not entries:
        pytest.skip("无 LogTemp 日志条目")

    merged = merge_with_defaults(entries, r.get("Entries_defaults") or {})
    cats = {e.get("Category") for e in merged if e.get("Category")}
    if len(cats) != 1:
        pytest.skip(f"本页 category 不唯一，无法断言 ForcedDefault: {cats!r}")

    only = next(iter(cats))
    defaults = r.get("Entries_defaults") or {}
    assert defaults.get("Category") == only, (
        f"expected Entries_defaults.Category={only!r} (actual unanimous), got: {defaults!r}"
    )


def test_get_gameplay_tags_hierarchy_defaults_shape(mcp):
    """get_gameplay_tags Sections=['Hierarchy']：扁平 tags 或树 children 均可；合并后每条含 tag。"""
    try:
        r = mcp.call("GetGameplayTags", Sections=["Hierarchy"], Limit=200)
    except MCPError as e:
        pytest.skip(f"get_gameplay_tags 调用失败：{e}")

    tags = r.get("Tags") or []
    if len(tags) < 3:
        pytest.skip(f"tag 数量不足以触发压缩（{len(tags)} 条）")

    def _walk(nodes, defaults):
        merged = merge_with_defaults(nodes, defaults)
        for entry in merged:
            assert "Tag" in entry, f"tags[].tag missing after merge: {entry!r}"
            children = entry.get("Children") or []
            if isinstance(children, list) and children:
                _walk(children, entry.get("children_defaults") or {})

    _walk(tags, r.get("tags_defaults") or {})


def test_get_asset_blackboard_type_defaults(mcp, test_ns):
    """get_asset_blackboard：keys_defaults 候选 type。"""
    path = _probe_blackboard(mcp, test_ns)

    try:
        bt_r = mcp.call("GetAssetBlackboard", AssetPath=path)
    except MCPError as e:
        pytest.skip(f"get_asset_behavior_tree blackboard 调用失败：{e}")

    keys = bt_r.get("Keys") or []
    if len(keys) < 3:
        pytest.skip(f"blackboard key 数量不足以触发压缩（{len(keys)} 条）")

    defaults = bt_r.get("keys_defaults") or {}
    merged = merge_with_defaults(keys, defaults)
    for entry in merged:
        assert "name" in entry, f"keys[].name missing after merge: {entry!r}"


def test_get_asset_bp_defaults_section_inherited_compression(mcp, test_ns):
    """get_asset_blueprint Sections=['Defaults']：inherited 全员写出（true/false），
    主流值可抽到 defaults_defaults；合并后每条均为 bool。"""
    bp = _probe_blueprint(mcp, test_ns)
    assert bp, "无法定位或创建 Blueprint 探测资产"

    try:
        payload = mcp.call_capability("GetAssetBlueprint", AssetPath=bp,
                                      Sections=["Defaults"], Limit=100)
    except MCPError as e:
        pytest.skip(f"get_asset_blueprint defaults 调用失败：{e}")

    if payload.get("Error"):
        pytest.skip(f"get_asset_blueprint defaults 返回错误：{payload['Error']!r}")

    defs_list = payload.get("Defaults") or []
    if len(defs_list) < 3:
        pytest.skip(f"too few defaults to trigger compaction (got {len(defs_list)})")

    merged = assert_respecting_defaults(
        payload,
        list_key="Defaults",
        defaults_prefix="Defaults",
        required_fields=("Path", "type", "bInherited"),
        context=f"get_asset_blueprint defaults {bp}",
    )
    for entry in merged:
        assert isinstance(entry.get("bInherited"), bool), (
            f"defaults[].inherited must be bool after merge: {entry!r}"
        )


def test_auto_discover_undeclared_fields_in_defaults(mcp):
    """自动扫描模式覆盖验证：assets_defaults 里出现的任何字段（包括未被显式 AddCandidate
    声明的字段）合并回条目后仍必须存在；同时 name/path 等身份字段不得出现在 defaults 里。"""
    r = mcp.call("SearchAsset", AssetType="Blueprint", Limit=200)
    payload = cap_first(r)
    defaults = payload.get("assets_defaults") or {}
    assets = payload.get("Assets") or []

    # 身份字段绝对不能出现在 defaults 里（AutoDiscoverExclusions 保护）
    identity_fields = {"name", "Path", "AssetPath", "Id", "Label", "Error"}
    for field in identity_fields:
        assert field not in defaults, (
            f"identity field '{field}' must not appear in assets_defaults: {defaults!r}"
        )

    # defaults 里出现的任意字段，合并后每条 entry 都必须含有（或本来就有）
    if defaults and assets:
        merged = merge_with_defaults(assets, defaults)
        for entry in merged:
            for key in defaults:
                assert key in entry, (
                    f"auto-discovered default field '{key}' missing after merge: {entry!r}"
                )


@pytest.mark.requires_gui
def test_get_actor_animation_variables_defaults_shape(mcp, pie):
    """get_runtime_actor_animation View=variables：variables_defaults 候选 type + value。
    需要 PIE 运行中的 Actor；若无 Actor 或 AnimInstance 则跳过。"""
    try:
        actors_r = mcp.call("ListRuntimeActors", Limit=50)
    except MCPError as e:
        pytest.skip(f"list_runtime_actors 失败：{e}")

    actors_payload = cap_first(actors_r)
    actors = actors_payload.get("Actors") or []
    actors_defaults = actors_payload.get("actors_defaults") or {}
    merged_actors = merge_with_defaults(actors, actors_defaults)

    # 找第一个带 AnimInstance 的 Actor（有骨骼网格且动画已初始化）
    target = None
    for a in merged_actors:
        name = a.get("name", "")
        cls = a.get("Class", "")
        # 优先选 Character 类
        if "Character" in cls or "Pawn" in cls:
            target = name
            break
    if not target and merged_actors:
        target = merged_actors[0].get("name", "")
    if not target:
        pytest.skip("PIE 世界中无 Actor")

    try:
        r = mcp.call("GetRuntimeActorAnimation", ActorName=target, Sections=["Variables"])
    except MCPError as e:
        pytest.skip(f"get_runtime_actor_animation 调用失败：{e}")

    results = r.get("Results") or []
    if not results or results[0].get("Error"):
        pytest.skip(f"get_runtime_actor_animation 返回错误：{results!r}")

    entry = results[0]
    variables = entry.get("Variables") or []
    if len(variables) < 3:
        pytest.skip(f"变量数量不足以触发压缩（{len(variables)} 条）")

    # 若触发压缩则校验 defaults 契约；未触发允许无 defaults
    defaults = entry.get("variables_defaults") or {}
    merged = merge_with_defaults(variables, defaults)
    for var in merged:
        assert "name" in var, f"variables[].name missing after merge: {var!r}"
        assert "type" in var, f"variables[].type missing after merge: {var!r}"


def test_structured_content_toggle(mcp):
    """验证：ContentMode 枚举二选一逻辑。
    Content（默认）：仅 content，无 structuredContent；
    StructuredContent：仅 structuredContent，无 content。"""
    result = mcp.try_call("GetEditorInfo")
    content = result.get("content") or []
    structured = result.get("structuredContent")

    if structured is not None:
        # ContentMode=StructuredContent：应有 structuredContent，无 content
        assert isinstance(structured, dict), "structuredContent should be a dict"
        assert len(structured) > 0, "structuredContent should not be empty"
        assert content == [], f"content should be empty when structuredContent is used, got: {content!r}"
    else:
        # ContentMode=Content（默认）：应有 content，无 structuredContent
        assert content, "content array should not be empty"
        text = content[0].get("text", "")
        import json
        parsed = json.loads(text)
        assert isinstance(parsed, dict), "content text should be valid JSON dict"
