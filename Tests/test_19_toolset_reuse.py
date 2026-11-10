# Copyright byteyang. All Rights Reserved.
"""独立实现保持同步结构、设置插件契约与版本行为。"""
from _framework.mcp_client import cap_first
from test_15_editor_operations import operation_result
from test_17_native_toolsets import native_domain


def test_legacy_discovery_contract(mcp, require_tools):
    require_tools("GetProjectSettings", "GetProjectPlugins")
    settings = cap_first(mcp.call("GetProjectSettings", Sections=["Containers"]))
    assert settings["Containers"] and "OperationId" not in settings, settings
    plugins = cap_first(mcp.call("GetProjectPlugins", Sections=["Plugins"], NameFilter="NexusLink", Limit=1))
    assert len(plugins["Plugins"]) == 1 and plugins["PluginsTotalCount"] >= 1, plugins
    assert "OperationId" not in plugins, plugins


def test_independent_discovery_backend(mcp, require_tools):
    native_domain(mcp, require_tools, "GetProjectSettings", "ConfigSettingsToolset")
    native_domain(mcp, require_tools, "GetProjectPlugins", "PluginToolset")
    settings = cap_first(mcp.call("GetProjectSettings", Sections=["Containers"]))
    assert settings["Backend"] == "Independent", settings
    plugins = cap_first(mcp.call("GetProjectPlugins", Sections=["Plugins"], NameFilter="NexusLink", Limit=1))
    assert plugins["Backend"] == "Independent", plugins


def test_independent_settings_and_plugins_contract(mcp, require_tools):
    native_domain(mcp, require_tools, "GetProjectPlugins", "PluginToolset")
    operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Discover"))
    result = operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Run", TestNames=["NexusLink.Independent.SettingsAndPlugins"]))
    assert result["Tests"][0]["Outcome"] == "Passed", result


def test_independent_sequencer_rate(mcp, require_tools, test_ns):
    native_domain(mcp, require_tools, "ControlEditorAnimation", "AnimationAssistantToolset")
    path = f"{test_ns}/LS_BackendRate"
    mcp.call("CreateAssetLevelSequence", AssetPath=path)
    result = cap_first(mcp.call("ManageAssetLevelSequence", AssetPath=path, Operations=[{"Action": "SetDisplayRate", "Numerator": 24, "Denominator": 1}]))
    assert result["Backend"] == "Independent" and result["DisplayRate"] == "24/1", result
