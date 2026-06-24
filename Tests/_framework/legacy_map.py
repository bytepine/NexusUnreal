# Copyright byteyang. All Rights Reserved.
"""旧 MCP 工具名 → 当前 Capability 名映射表。

在 v1.8–v1.10 的 Capability 命名规范化重构中，多个工具被重命名。
此映射由 MCPClient.call() 使用，以便旧测试代码可在不改调用形式的情况下
自动路由到正确的新 capability，避免大规模批量修改。

对于真正已拆分（原工具变成多个 capability）的情况（get_lua / manage_lua 等），
此处不做映射，需在对应测试文件中显式改写。
"""

from typing import Dict

# 旧工具名 → 新 capability 名（1:1 rename，参数名称未变）
LEGACY_CAP_NAMES: Dict[str, str] = {
    # Asset 创建类
    "create_blueprint":      "create_asset_blueprint",
    "create_material":       "create_asset_material",
    "create_widget":         "create_asset_user_widget",
    "create_struct":         "create_asset_struct",
    "create_data_asset":     "create_asset_data_asset",
    "create_data_table":     "create_asset_data_table",
    "create_behavior_tree":  "create_asset_behavior_tree",
    "create_blackboard":     "create_asset_blackboard",
    "create_anim_blueprint": "create_asset_anim_blueprint",
    "create_anim_montage":   "create_asset_anim_montage",

    # Asset 读取类（注意 get_asset 拆分为按类型，不在此处统一映射）
    "get_behavior_tree":       "get_asset_behavior_tree",

    # Asset 管理类
    "manage_struct_field":     "manage_asset_struct_field",
    "manage_blueprint_variable": "manage_asset_blueprint",  # action 语义不变
    "manage_blueprint_graph":    "manage_asset_blueprint",
    "manage_blueprint_wires":    "manage_asset_blueprint",
    "manage_blueprint_component":"manage_asset_blueprint",
    "manage_material":         "manage_asset_material",
    "manage_widget":           "manage_asset_user_widget",

    # Runtime 类（已加 _runtime_ 中缀）
    "list_actors":             "list_runtime_actors",
    "spawn_actor":             "spawn_runtime_actor",
    "destroy_actor":           "destroy_runtime_actor",
    "diff_actors":             "diff_runtime_actors",
    "get_actor_animation":     "get_runtime_actor_animation",
    "get_actor_behavior_tree": "get_runtime_actor_behavior_tree",
    "spawn_widget":            "spawn_runtime_widget",
    "list_runtime_widgets":    "list_runtime_widgets",  # 已是新名，无需改动但保留以防旧拼写
    "get_asset_slate_widget":  "get_runtime_slate_widget",
    "interact_widget":         "interact_runtime_widget",

    # Runtime 属性读写
    "get_property": "get_runtime_actor_property",
    "set_property": "set_runtime_actor_property",
}

# 直接由 AI 通过 tools/call 调用的元工具（不通过 call_capability 转发）
META_TOOLS = frozenset({
    "search_capabilities",
    "call_capability",
    "submit_feedback",
    # 代理层工具（rider/vscode 本地处理，不转发给 UE）
    "list_unreal_instances",
    "connect_unreal_instance",
})
