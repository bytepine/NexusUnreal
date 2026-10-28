# Copyright byteyang. All Rights Reserved.
"""项目设置及插件发现：只读枚举、定向读取与依赖关系。"""
import pytest
from _framework.mcp_client import cap_first
from _framework.assertions import merge_with_defaults


def test_project_settings_discovery_and_value(mcp, require_tools):
    require_tools("GetProjectSettings")
    containers = cap_first(mcp.call("GetProjectSettings", Sections=["Containers"]))
    assert "Project" in [item["Name"] for item in containers["Containers"]], containers
    categories = cap_first(mcp.call("GetProjectSettings", Sections=["Categories"], Container="Project"))
    assert "Project" in [item["Name"] for item in categories["Categories"]], categories
    sections = cap_first(mcp.call("GetProjectSettings", Sections=["Sections"], Container="Project", Category="Project"))
    assert "General" in [item["Name"] for item in sections["Sections"]], sections
    target = dict(Container="Project", Category="Project", Section="General")
    properties = cap_first(mcp.call("GetProjectSettings", Sections=["Properties"], **target))
    assert "ProjectName" in [item["Name"] for item in properties["Properties"]], properties
    values = cap_first(mcp.call("GetProjectSettings", Sections=["Values"], PropertyNames=["ProjectName"], **target))
    assert len(values["Values"]) == 1 and values["Values"][0]["Name"] == "ProjectName", values
    assert isinstance(values["Values"][0]["Value"], str), values
    invalid = mcp.try_call("GetProjectSettings", Sections=["Values"], **target)
    assert invalid.get("isError") or "Error" in str(invalid), invalid


def test_project_plugins_info_and_dependencies(mcp, require_tools):
    require_tools("GetProjectPlugins")
    plugins = cap_first(mcp.call("GetProjectPlugins", Sections=["Plugins"], NameFilter="NexusLink", bEnabledOnly=True))
    rows = merge_with_defaults(plugins["Plugins"], plugins.get("Plugins_defaults", {}))
    assert any(p["Name"] == "NexusLink" and p["bEnabled"] for p in rows), plugins
    result = cap_first(mcp.call("GetProjectPlugins", PluginName="NexusLink", Sections=["Info", "Dependencies", "Dependents"]))
    assert result["Info"]["Name"] == "NexusLink" and result["Info"]["Modules"], result
    assert isinstance(result["Dependencies"], list) and isinstance(result["Dependents"], list), result
    missing = mcp.try_call("GetProjectPlugins", PluginName="__NexusMissingPlugin__", Sections=["Info"])
    assert missing.get("isError") or "Error" in str(missing), missing


def test_project_plugin_asset_mount_owner(mcp, require_tools, test_ns):
    require_tools("GetProjectPlugins", "CreateAssetUserWidget")
    path = f"{test_ns}/WBP_MountOwner"
    mcp.call("CreateAssetUserWidget", AssetPath=path)
    owner = cap_first(mcp.call("GetProjectPlugins", Sections=["AssetOwner"], AssetPath=path))
    assert owner["AssetOwner"]["Name"] == "Project", owner
