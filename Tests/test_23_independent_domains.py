# Copyright byteyang. All Rights Reserved.
"""独立领域实现的 C++ 集成回归，不要求任何官方 Toolset。"""
import pytest

from test_15_editor_operations import operation_result


@pytest.mark.parametrize("name", [
    "NexusLink.Smoke.PluginAndRegistry.SchemaDump",
    "NexusLink.Independent.DiscoveryContract",
    "NexusLink.Independent.SettingsAndPlugins",
    "NexusLink.Independent.Skills.Metadata",
    "NexusLink.Animation.IndependentContractsAndChannels",
    "NexusLink.Independent.PCG.Parameters",
    "NexusLink.Independent.Niagara.ActionDiscovery",
    "NexusLink.Independent.Material.DeleteUnusedNamedReroute",
])
def test_independent_domain_automation(mcp, require_tools, name):
    require_tools("ControlEditorAutomation", "ListEditorAutomationTests")
    operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Discover"))
    listed = operation_result(mcp, mcp.call("ListEditorAutomationTests", NameFilter=name))
    assert name in listed["Tests"], listed
    result = operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Run", TestNames=[name]))
    assert len(result["Tests"]) == 1 and result["Tests"][0]["Name"] == name, result
    assert result["Tests"][0]["Outcome"] == "Passed", result


@pytest.mark.skipif_ue_below("5.8")
def test_independent_niagara_external_api_automation(mcp, require_tools):
    test_independent_domain_automation(mcp, require_tools, "NexusLink.Independent.Niagara.SchemaAndVariables")
