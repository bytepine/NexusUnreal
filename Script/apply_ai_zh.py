#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 MCP 暴露给 AI 的 Description / WhenToUse / Schema 参数描述批量替换为中文。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
PLUGIN_SRC = REPO_ROOT / "nexus-unreal/Plugins/Developer/NexusLink/Source/NexusLink/Private"

# Capability Out.Description（≤100 字符，供注册校验）
CAP_DESC_ZH: dict[str, str] = {
    "capture_viewport": "截图编辑器/PIE/Actor/Widget。target=editor|pie|actor|widget。",
    "control_pie": "启动/停止/查询 PIE。action=start|stop|status。",
    "exec_command": "执行 UE 控制台命令并捕获输出。silent=true 可跳过捕获。",
    "get_editor_info": "返回 UE 版本、项目名、平台与构建配置。无参数。",
    "get_gameplay_tags": "检查 GAS 标签树或 Actor/资产标签。sections=hierarchy|actor|asset。",
    "get_output_log": "读取 UE 控制台缓冲。按 category/verbosity/text 过滤，offset+limit 分页。",
    "set_log_capture_filter": "配置写入缓冲的日志分类。空=全部；影响 get_output_log。",
    "delete_asset": "永久删除单个资产包。尽力清理重定向器；不可逆。",
    "duplicate_asset": "复制编辑器资产到新路径。源资产不变。",
    "get_asset_refs": "查包依赖或引用方。direction=dependencies|referencers；可选递归。",
    "rename_asset": "移动或重命名资产。自动生成重定向器修复引用。",
    "save_asset": "将资产包持久化到磁盘。先标记 Dirty 再保存。",
    "search_asset": "查找资产路径。必须先调；指定 assetType+pathFilter；禁止猜 /Game 路径。",
    "create_asset_blueprint": "创建新 BP 资产，自动编译；用 manage 添加变量/节点/连线。",
    "get_asset_blueprint": "从编辑器读 BP。回答蓝图问题前必须先调；禁止从源码推断。",
    "manage_asset_blueprint": "编辑 BP：图/变量/节点/连线、SCS、CDO。SCS/defaults 限 Actor BP。",
    "create_asset_anim_blueprint": "为骨骼创建 ABP，自动关联；用 manage 填充状态机。",
    "create_asset_anim_montage": "为骨骼创建 Montage；用 manage 添加片段。",
    "get_asset_anim_blueprint": "检查 ABP 结构。sections=variables|statemachines|defaults。",
    "get_asset_anim_montage": "检查 Montage 时间轴快照。只读，不触发播放。",
    "get_runtime_actor_animation": "从运行中骨骼网格取 AnimInstance。sections=state|slots|variables。",
    "manage_asset_anim_blueprint": "编辑 ABP 状态机。增删 state_machine/state/transition；须保存。",
    "manage_asset_anim_montage": "编辑 Montage 结构。增删槽位/片段/分段；须 save_asset。",
    "create_asset_material": "创建材质或材质实例。MI 需 parentMaterial；domain 与 type 一致。",
    "get_asset_material": "检查 Mat/MI/MF 节点与参数。sections=overview|params|graph；可过滤分页。",
    "manage_asset_material": "批量编辑材质/MI：set_param/add_node/connect/recompile。",
    "create_asset_struct": "创建 UDS 文件，自动编译；用 manage_asset_struct_field 加字段。",
    "get_asset_struct": "检查 UDS 字段定义。含 name/type/subType/defaultValue；可 propertyPaths 过滤。",
    "manage_asset_struct_field": "批量编辑 UDS 字段：add/remove/modify；修改后自动编译。",
    "create_asset_data_asset": "创建类型化 DataAsset。需子类名；非抽象类。",
    "create_asset_data_table": "创建带行结构体的 DT；用 manage_asset_data_table 填行。",
    "get_asset_data_asset": "读 DataAsset 属性。含类型/值/是否继承；可路径过滤。",
    "get_asset_data_table": "检查 DT 行或 Schema。mode=schema|rows；可 propertyPaths 过滤。",
    "manage_asset_data_asset": "批量编辑 DataAsset。set=ImportText 校验；reset=CDO；ops[] 非空。",
    "manage_asset_data_table": "批量编辑 DT 行：add/remove/set；ImportText 校验。",
    "create_asset_user_widget": "创建 WBP。parentClass 设 UI 基类；用 manage 填控件树。",
    "get_asset_user_widget": "从编辑器读 WBP 树与动画。回答 Widget 问题前必须先调；勿从源码推断。",
    "manage_asset_user_widget": "批量编辑 WBP 层级。按类型/名称增删面板子控件；须保存。",
    "dofile_runtime_lua": "从 Content/Script/ 加载执行 .lua。相对路径；需 UnLua+PIE。",
    "eval_runtime_lua": "在 PIE/Game 执行 Lua 片段，返回压栈值。",
    "gc_runtime_lua": "控制 PIE 中 Lua GC。mode=collect|stop|restart|count。",
    "get_asset_lua_binding": "解析 BP 绑定的 UnLua 模块。返回 bound/fileExists；需 UnLua。",
    "get_runtime_lua_env": "枚举 _G 或嵌套表键。支持 nameFilter+limit。",
    "get_runtime_lua_loaded": "枚举 package.loaded 已加载模块。支持名称过滤。",
    "get_runtime_lua_memory": "报告 Lua VM 堆用量（KB/字节）。配合 gc_runtime_lua 诊断。",
    "get_runtime_lua_metatable": "沿 __index 链转储 OOP 类表。用于 UnLua 继承链调试。",
    "get_runtime_lua_object": "读 UnLua 绑定 Actor/UObject 的实例 Lua 表。",
    "get_runtime_lua_stack": "转储 Lua 调用栈与局部/上值。detail=locals|upvalues|all。",
    "get_runtime_lua_value": "按点路径读 Lua 全局或嵌套字段。返回类型与值。",
    "hotreload_runtime_lua": "热重载所有 UnLua 模块，无需重启 PIE。UnLua 2.X。",
    "set_runtime_lua": "为 Lua 全局或嵌套字段赋值。点路径；string/number/bool/null。",
    "destroy_runtime_actor": "从 PIE/Game 移除运行时 Actor，标记 Level 已修改。",
    "diff_runtime_actors": "对比两个运行时 Actor 属性差异。最多 50 条；可 propertyPaths 过滤。",
    "get_runtime_actor_property": "查询运行时 Actor 字段。支持批量 propertyPaths 与组件树。",
    "get_runtime_slate_widget": "按十六进制地址检查原生 SWidget（来自 Widget Reflector）。",
    "get_runtime_widget_property": "读运行时 UMG 元素字段。widgetName+ownerClass 定位。",
    "interact_runtime_widget": "触发运行时 UMG 事件。action=click|check|toggle|set|read。",
    "list_runtime_actors": "枚举 PIE/Game 中 Actor。按类/标签/名过滤；返回引用非属性。",
    "list_runtime_widgets": "枚举 PIE/Game 视口 UMG 实例。按类/名/displayText 过滤。",
    "set_runtime_actor_property": "批量修改运行时 Actor 可编辑字段。updates[] 每项一结果。",
    "set_runtime_widget_property": "批量修改运行时 UMG 字段。updates[] 含控件名/路径/值。",
    "spawn_runtime_actor": "在 PIE 实例化 Actor。blueprintPath 或 className；可设位置/旋转。",
    "spawn_runtime_widget": "在 PIE/Game 视口创建并显示 UMG 面板。需 assetPath+zOrder。",
    "create_asset_behavior_tree": "创建空白 BT。用 manage 的 set_blackboard 关联 BB 后填节点。",
    "create_asset_blackboard": "创建无键 BB。用 manage BT 的 set_blackboard 关联。",
    "get_asset_behavior_tree": "检查 BT 结构快照。含路径索引与节点属性；只读。",
    "get_asset_blackboard": "检查 BB 键定义。返回名称与类型快照；只读。",
    "get_runtime_actor_behavior_tree": "查运行中 AI 的活动 BT 节点与 BB 键值。目标 AIController/Pawn。",
    "manage_asset_behavior_tree": "批量编辑 BT 节点/装饰器/服务。Graph 与运行时树同步刷新。",
    "manage_asset_blackboard": "批量编辑 BB 键：增删/重命名/改父 BB；须 save_asset。",
}

CAP_WHEN_ZH: dict[str, str] = {
    "create_asset_blueprint": "创建空白 BP；不用于编辑现有 BP",
    "get_asset_blueprint": "用户问蓝图变量/Graph/函数 — 必须先调，勿 grep 源码",
    "manage_asset_blueprint": "写操作：增删变量、图节点、连线",
    "create_asset_anim_blueprint": "创建空白 ABP；需要 skeletonPath",
    "create_asset_anim_montage": "创建空白 Montage；需要 skeletonPath",
    "get_asset_anim_blueprint": "读 ABP 变量/状态机/默认值；不含写操作",
    "get_asset_anim_montage": "读 Montage 结构；运行时播放用 get_runtime_actor_animation",
    "manage_asset_anim_blueprint": "写操作：增删状态机、状态、过渡",
    "manage_asset_anim_montage": "写操作：增删 Montage 片段/分段/槽位",
    "create_asset_material": "创建空白 Material 或 MaterialInstance",
    "get_asset_material": "读节点图/参数/连线；不含编辑",
    "manage_asset_material": "写操作：设参数、增删节点、连线、重编译",
    "create_asset_struct": "创建空白 UDS；用 manage 添加字段",
    "get_asset_struct": "读 UDS 字段定义；不含编辑",
    "manage_asset_struct_field": "写操作：增删/修改 UDS 字段",
    "create_asset_data_asset": "创建 DataAsset；parentClass 默认 PrimaryDataAsset",
    "create_asset_data_table": "创建空白 DT；需要 rowStructName",
    "get_asset_data_asset": "读 DataAsset 属性；不含编辑",
    "get_asset_data_table": "读 DT Schema 或行值；不含编辑",
    "manage_asset_data_asset": "写操作：设置或重置 DataAsset 为 CDO 默认",
    "manage_asset_data_table": "写操作：增删/设置 DT 行值",
    "create_asset_user_widget": "创建空白 WBP；parentClass 可选（默认 UserWidget）",
    "get_asset_user_widget": "用户问控件树/UMG 动画 — 必须先调，勿 grep 源码",
    "manage_asset_user_widget": "写操作：在面板中增删子控件",
    "get_asset_lua_binding": "读/编 Lua 前先找绑定文件路径",
    "get_runtime_lua_env": "浏览所有键（env）或读单键（value）",
    "get_runtime_lua_memory": "gc collect 前后检查堆大小",
    "get_runtime_lua_value": "读单键用此工具；浏览键用 env",
    "get_runtime_actor_property": "只读字段，不做修改",
    "get_runtime_slate_widget": "持有 Widget Reflector 十六进制地址时用",
    "get_runtime_widget_property": "只读 UMG 字段，不做修改",
    "set_runtime_actor_property": "运行时修改 Actor 实时字段",
    "set_runtime_widget_property": "运行时修改 UMG 实时字段",
    "create_asset_behavior_tree": "创建空白 BT；无节点、未关联 BB",
    "create_asset_blackboard": "创建空白 BB；用 manage_asset_blackboard 加键",
    "get_asset_behavior_tree": "读 BT 路径索引/属性/装饰器参数",
    "get_asset_blackboard": "读 BB 键列表；运行时值用 get_runtime_actor_behavior_tree",
    "manage_asset_behavior_tree": "写操作：增删节点/装饰器/服务、设属性",
    "manage_asset_blackboard": "写操作：增删/重命名 BB 键、改父 BB",
}

# 元工具 Out.Description（无 100 字限制）
META_DESC_ZH: dict[str, str] = {
    "search_capabilities": (
        "【首要入口】发现 Capability。回答蓝图/Widget/材质/资产问题前必须先调。"
        "已知名称优先 capabilityName=<精确名>；query 用 1-2 词 AND 匹配。"
        "匹配≤2 返回完整 parameters[]，否则用 capabilityName 精确查询。"
        "响应含 _feedbackHint 时必须立即调用 submit_feedback。"
    ),
    "call_capability": (
        "执行 Capability（在 search_asset/get_asset_* 读取之后）。"
        "单条：capability+arguments；批量：calls=[{capability,arguments},...]，顺序执行，不可混用。"
        "重试一次仍有歧义请 submit_feedback。响应含 _feedbackHint 时必须立即调用。"
    ),
    "submit_feedback": (
        "上报工具/Capability 使用摩擦。触发：重试≥2 次无进展、找不到合适 Capability、"
        "Schema 需猜测、被迫串行≥3 次。category：wrong_tool|misuse|schema_guess|"
        "search_zero|search_overflow|other。优先填 attemptedArgs/actualError/expectedField。"
    ),
}

# Schema 参数 / Enum label 英文 → 中文（按出现频次与通用性）
PARAM_DESC_ZH: dict[str, str] = {
    "Exact capability name": "Capability 精确名称",
    "Nested payload for this item": "本条的嵌套参数对象",
    "Single-call capability name": "单次调用的 Capability 名称",
    "Single-call nested payload": "单次调用的嵌套参数",
    "Batch: ordered list of {capability,arguments?}": "批量：有序列表 [{capability,arguments?},...]",
    "Feedback category": "反馈分类",
    "Free-text description of the issue (encouraged)": "问题自由文本描述（建议填写）",
    "MCP tool name involved": "涉及的 MCP 工具名",
    "Capability name involved": "涉及的 Capability 名称",
    "search_capabilities query that caused the issue": "引发问题的 search_capabilities 查询词",
    "Summary of the arguments that triggered the issue": "触发问题的参数摘要",
    "Actual error message snippet received": "实际收到的错误信息片段",
    "Field name that was missing, ambiguous or had to be guessed": "缺失、歧义或需猜测的字段名",
    "Call BEFORE answering blueprint/asset/widget questions. 1-2 words AND-matched to capability name. Exact name returns full schema.": (
        "回答蓝图/资产/Widget 问题前先调。1-2 词 AND 匹配 Capability 名；精确名返回完整 Schema。"
    ),
    "Exact capability name (e.g. 'get_asset_blueprint'). When provided, returns full parameter list for that capability.": (
        "Capability 精确名（如 get_asset_blueprint）。提供时返回该 Capability 完整参数列表。"
    ),
    "/Game/ path to the asset": "/Game/ 资产路径",
    "Asset path under /Game/": "/Game/ 下资产路径",
    "One or more /Game/ asset paths": "一个或多个 /Game/ 资产路径",
    "Batch of /Game/ asset paths": "批量 /Game/ 资产路径",
    "Actor name in the world": "世界中 Actor 名称",
    "Actor class filter (optional)": "Actor 类过滤（可选）",
    "Actor tag filter (optional)": "Actor 标签过滤（可选）",
    "Name filter (optional, substring)": "名称过滤（可选，子串）",
    "Widget instance name in viewport": "视口中 Widget 实例名",
    "Owner class name for disambiguation": "用于消歧的 Owner 类名",
    "Property path(s) to read or write": "要读写的属性路径",
    "Lua dot-path (e.g. MyModule.Config)": "Lua 点路径（如 MyModule.Config）",
    "Relative path under Content/Script/": "Content/Script/ 下相对路径",
    "Lua code to execute": "要执行的 Lua 代码",
    "Console command string": "控制台命令字符串",
    "Skip output capture when true": "为 true 时跳过输出捕获",
    "Search query (name substring)": "搜索关键词（名称子串）",
    "Asset type filter (required)": "资产类型过滤（必填）",
    "Path prefix under /Game/ (required)": "/Game/ 路径前缀（必填）",
    "Sections to return": "要返回的 section 列表",
    "Action to perform": "要执行的操作",
    "Batch operations array": "批量操作数组",
    "New asset path under /Game/": "/Game/ 下新资产路径",
    "Source asset path": "源资产路径",
    "Target asset path": "目标资产路径",
    "Skeleton asset path": "骨骼资产路径",
    "Parent material path (for MI)": "父材质路径（材质实例用）",
    "Parent class name": "父类名",
    "Row struct name for DataTable": "DataTable 行结构体名",
    "Widget Blueprint asset path": "Widget 蓝图资产路径",
    "Blueprint asset path": "蓝图资产路径",
    "Class name (native or BP)": "类名（原生或 BP）",
    "World location (optional)": "世界坐标（可选）",
    "World rotation (optional)": "世界旋转（可选）",
    "Z-order for widget layering": "Widget 层级 Z 序",
    "Hex address from Widget Reflector": "Widget Reflector 提供的十六进制地址",
    "Log category filter": "日志分类过滤",
    "Log verbosity filter": "日志详细级别过滤",
    "Text substring filter": "文本子串过滤",
    "Pagination offset": "分页偏移",
    "Max items to return": "最大返回条数",
    "PIE action": "PIE 操作",
    "Screenshot target": "截图目标",
    "Gameplay tag query": "Gameplay 标签查询",
    "Direction: dependencies or referencers": "方向：dependencies 或 referencers",
    "Recursive search": "递归搜索",
    "Include inherited values": "包含继承值",
    "Name filter for keys or nodes": "键或节点名称过滤",
    "Type filter for widgets": "Widget 类型过滤",
    "Graph name (from graphOverview, not function name)": "图名（来自 graphOverview，非函数名）",
    "Variable name": "变量名",
    "Variable type string": "变量类型字符串",
    "Default value as string": "默认值字符串",
    "Node ID from get response": "get 响应中的节点 ID",
    "Pin name to connect": "要连接的引脚名",
    "Component name in SCS": "SCS 中组件名",
    "Component class name": "组件类名",
    "Property path on component or CDO": "组件或 CDO 上的属性路径",
    "Montage slot name": "Montage 槽位名",
    "Animation sequence path": "动画序列路径",
    "State machine name": "状态机名",
    "State name": "状态名",
    "Transition target state": "过渡目标状态",
    "Blackboard key name": "黑板键名",
    "Blackboard key type": "黑板键类型",
    "Behavior tree node type": "行为树节点类型",
    "Updates array for batch property writes": "批量写属性的 updates 数组",
    "Value to set (string form)": "要设置的值（字符串形式）",
    "Check state for checkbox": "复选框勾选状态",
    "Slider value": "滑条值",
    "Text to set on TextBlock": "TextBlock 要设置的文本",
    "Mode: schema or rows": "模式：schema 或 rows",
    "Field operations batch": "字段操作批量",
    "Material parameter name": "材质参数名",
    "Material parameter value": "材质参数值",
    "Node class or type": "节点类或类型",
    "Source node ID": "源节点 ID",
    "Target node ID": "目标节点 ID",
    "Lua GC mode": "Lua GC 模式",
    "Detail level for stack dump": "栈转储详细级别",
    "Frame index for drill-down": "向下钻取的帧索引",
    "Object path or name": "对象路径或名称",
    "Metatable path": "元表路径",
    "Limit number of results": "限制结果数量",
    "Display text filter": "显示文本过滤",
    "Owner widget class filter": "Owner Widget 类过滤",
    "Second actor name for diff": "对比的第二个 Actor 名",
    "Categories to capture (empty=all)": "要捕获的分类（空=全部）",
}

RE_NAME = re.compile(r'Out\.Name\s*=\s*TEXT\("([^"]+)"\)')
RE_DESC = re.compile(r'(Out\.Description\s*=\s*TEXT\(")([^"]+)("\))')
RE_WHEN = re.compile(r'(Out\.WhenToUse\s*=\s*TEXT\(")([^"]+)("\))')
RE_SCHEMA_TEXT = re.compile(r'(TEXT\(")([^"]{4,})("\))')


def replace_cap_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    orig = text

    m_name = RE_NAME.search(text)
    if not m_name:
        return False
    name = m_name.group(1)

    if name in CAP_DESC_ZH:
        text = RE_DESC.sub(lambda m: m.group(1) + CAP_DESC_ZH[name] + m.group(3), text, count=1)

    if name in CAP_WHEN_ZH:
        text = RE_WHEN.sub(lambda m: m.group(1) + CAP_WHEN_ZH[name] + m.group(3), text, count=1)

    if text != orig:
        # 校验 Description 长度
        m = RE_DESC.search(text)
        if m and len(m.group(2)) > 100:
            print(f"WARN {path.name}: Description {len(m.group(2))} chars > 100: {m.group(2)[:60]}...")
        path.write_text(text, encoding="utf-8")
        return True
    return False


def replace_meta_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    orig = text
    m_name = RE_NAME.search(text)
    if m_name and m_name.group(1) in META_DESC_ZH:
        name = m_name.group(1)
        text = RE_DESC.sub(lambda m: m.group(1) + META_DESC_ZH[name] + m.group(3), text, count=1)
    if text != orig:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def replace_param_descs_in_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    count = 0

    def sub_fn(m: re.Match) -> str:
        nonlocal count
        en = m.group(2)
        if en in PARAM_DESC_ZH:
            count += 1
            return m.group(1) + PARAM_DESC_ZH[en] + m.group(3)
        return m.group(0)

    new_text = RE_SCHEMA_TEXT.sub(sub_fn, text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return count


def main() -> int:
    cap_dir = PLUGIN_SRC / "Capabilities"
    tools_dir = PLUGIN_SRC / "Tools"
    changed_caps = 0
    for cpp in sorted(cap_dir.rglob("*.cpp")):
        if replace_cap_file(cpp):
            changed_caps += 1
            print(f"cap: {cpp.name}")

    changed_meta = 0
    for cpp in sorted(tools_dir.glob("NexusMcpTool*.cpp")):
        if replace_meta_file(cpp):
            changed_meta += 1
            print(f"meta: {cpp.name}")

    param_total = 0
    for cpp in sorted(list(cap_dir.rglob("*.cpp")) + list(tools_dir.glob("*.cpp"))):
        param_total += replace_param_descs_in_file(cpp)

    print(f"\nDone: {changed_caps} capabilities, {changed_meta} meta tools, {param_total} param desc replacements")
    return 0


if __name__ == "__main__":
    sys.exit(main())
