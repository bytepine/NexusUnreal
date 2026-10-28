# Copyright byteyang. All Rights Reserved.
"""UE 5.8 官方领域适配：技能、语义搜索、PCG 和 Niagara。"""
import pytest
from _framework.mcp_client import MCPError, cap_first
from test_15_editor_operations import operation_result

pytestmark = pytest.mark.skipif_ue_below("5.8")


def native_domain(mcp, require_tools, capability, plugin):
    require_tools(capability, "GetProjectPlugins")
    info = cap_first(mcp.call("GetProjectPlugins", PluginName=plugin, Sections=["Info"]))
    if not info["Info"]["bEnabled"]:
        pytest.skip(f"Host has not enabled {plugin}")


def official(mcp, capability, **arguments):
    result = operation_result(mcp, mcp.call(capability, **arguments))
    assert isinstance(result.get("OfficialResult"), dict), result
    return result["OfficialResult"]


def test_project_skill_list_and_detail(mcp, require_tools, test_ns):
    native_domain(mcp, require_tools, "GetProjectSkills", "ToolsetRegistry")
    path = f"{test_ns}/SK_DiscoveryProbe"
    mcp.call("CreateAssetBlueprint", AssetPath=path, ParentClass="AgentSkill")
    mcp.call("ManageAssetBlueprint", AssetPath=path, Operations=[
        {"Action": "SetDefaults", "PropertyPath": "Description", "Value": "Nexus read-only discovery fixture"},
        {"Action": "SetDefaults", "PropertyPath": "Instructions", "Value": "Read the fixture description."},
    ])
    listed = official(mcp, "GetProjectSkills")
    matches = [key for key in listed if "SK_DiscoveryProbe" in key and test_ns in key]
    assert len(matches) == 1, listed
    details = official(mcp, "GetProjectSkills", Action="Details", SkillPath=matches[0])
    assert matches[0] in details and isinstance(details[matches[0]], dict), details
    invalid = mcp.try_call("GetProjectSkills", Action="Details")
    assert invalid.get("isError"), invalid


def test_semantic_search_adapter(mcp, require_tools, test_ns):
    native_domain(mcp, require_tools, "SearchAssetsSemantic", "SemanticSearchToolset")
    invalid = mcp.try_call("SearchAssetsSemantic", Query="materials", ClassPaths=[])
    assert invalid.get("isError"), invalid
    try:
        result = official(mcp, "SearchAssetsSemantic", Query="simple surface material", ClassPaths=["/Script/Engine.Material"], PathRegexes=["^" + test_ns + "/"], Limit=3)
    except MCPError as error:
        text = str(error).lower()
        if "no embedding provider" in text or "embedding generation failed" in text:
            pytest.skip(f"SemanticSearch environment unavailable: {error}")
        raise
    assert isinstance(result.get("Items"), list), result


def test_pcg_graph_instance_execution(mcp, require_tools, test_ns):
    native_domain(mcp, require_tools, "GetEditorPCG", "PCGToolset")
    require_tools("CreateAssetPCGGraph", "ControlEditorPCG")
    path = f"{test_ns}/PCG_ExecuteProbe"
    mcp.call("CreateAssetPCGGraph", AssetPath=path)
    object_path = f"{path}.{path.rsplit('/', 1)[1]}"
    mcp.call("ManageAssetPCGGraph", AssetPath=path, Operations=[{"Action": "AddNode", "SettingsClass": "PCGCreatePointsGridSettings"}])
    graph = cap_first(mcp.call("GetAssetPCGGraph", AssetPath=path))
    grid = next(node for node in graph["Nodes"] if node["SettingsClass"] == "PCGCreatePointsGridSettings")
    output = graph["OutputNode"]
    mcp.call("ManageAssetPCGGraph", AssetPath=path, Operations=[{
        "Action": "AddEdge", "FromNodeId": grid["Id"], "FromPin": grid["OutputPins"][0],
        "ToNodeId": output["Id"], "ToPin": output["InputPins"][0],
    }])
    structure = official(mcp, "GetEditorPCG", Action="GraphStructure", AssetPath=object_path)
    schema = official(mcp, "GetEditorPCG", Action="GraphSchema", AssetPath=object_path)
    assert structure and schema, (structure, schema)
    spawned = official(mcp, "ControlEditorPCG", Action="Spawn", AssetPath=object_path, ActorName="NexusPcgExecuteProbe")
    instances = official(mcp, "GetEditorPCG", Action="Instances")
    def refs(value):
        if isinstance(value, dict):
            if isinstance(value.get("refPath"), str):
                yield value["refPath"]
            for child in value.values():
                yield from refs(child)
        elif isinstance(value, list):
            for child in value:
                yield from refs(child)
    actor_paths = [ref for ref in refs(spawned) if ":PersistentLevel." in ref]
    assert actor_paths and actor_paths[0] in str(instances), (spawned, instances)
    try:
        official(mcp, "GetEditorPCG", Action="NodeData", ActorPath=actor_paths[0], NodePath=grid["Path"], PinLabel=grid["OutputPins"][0], Limit=2)
    except MCPError as error:
        assert "inspection" in str(error).lower(), str(error)[:1000]
    executed = official(mcp, "ControlEditorPCG", Action="Execute", ActorPath=actor_paths[0])
    assert isinstance(executed, dict), executed
    data = official(mcp, "GetEditorPCG", Action="NodeData", ActorPath=actor_paths[0], NodePath=grid["Path"], PinLabel=grid["OutputPins"][0], Limit=2)
    assert data["totalElements"] > 0 and "element_0" in data, data
    assert len([name for name in data if name.startswith("element_")]) <= 2, data


def test_niagara_compile_and_stack_diagnostics(mcp, require_tools, test_ns):
    native_domain(mcp, require_tools, "GetEditorNiagara", "NiagaraToolsets")
    require_tools("CreateAssetNiagaraSystem", "ExecNiagaraStackFix")
    path = f"{test_ns}/NS_DiagnosticsProbe"
    mcp.call("CreateAssetNiagaraSystem", AssetPath=path)
    object_path = f"{path}.{path.rsplit('/', 1)[1]}"
    for action in ["CompileState", "StackIssues", "Dependencies", "SystemData"]:
        result = official(mcp, "GetEditorNiagara", Action=action, AssetPath=object_path)
        assert isinstance(result, dict), (action, result)
    renderer = official(mcp, "GetEditorNiagara", Action="RendererSchema", ClassPath="/Script/Niagara.NiagaraSpriteRendererProperties")
    assert renderer, renderer
    invalid = mcp.try_call("ExecNiagaraStackFix", AssetPath=object_path, IssueId="", FixId="")
    assert invalid.get("isError"), invalid
