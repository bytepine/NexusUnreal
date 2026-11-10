# Copyright byteyang. All Rights Reserved.
"""独立领域实现：技能、语义搜索、PCG 和 Niagara。"""
import math
import uuid

import pytest
from _framework.assertions import merge_with_defaults
from _framework.mcp_client import MCPError, cap_first
from test_15_editor_operations import operation_result

def native_domain(mcp, require_tools, capability, plugin):
    """历史 helper 名保留，门控只检查真正的领域插件。"""
    domains = {"ToolsetRegistry": None, "AnimationAssistantToolset": None,
               "ConfigSettingsToolset": None, "PluginToolset": None,
               "SemanticSearchToolset": "SemanticSearch", "PCGToolset": "PCG",
               "NiagaraToolsets": "Niagara"}
    assert plugin in domains, f"Unreviewed domain dependency: {plugin}"
    require_tools(capability)
    domain = domains[plugin]
    if domain is None:
        return
    require_tools("GetProjectPlugins")
    info = cap_first(mcp.call("GetProjectPlugins", PluginName=domain, Sections=["Info"]))
    if not info["Info"]["bEnabled"]:
        pytest.skip(f"Host has not enabled domain plugin {domain}")


def official(mcp, capability, **arguments):
    """验证独立后端，再解包保留的领域结果容器。"""
    response = cap_first(mcp.call(capability, **arguments))
    assert response["Backend"] == "Independent", response
    result = operation_result(mcp, response)
    assert isinstance(result.get("CompatibilityResult"), dict), result
    return result["CompatibilityResult"]


def pcg_actor_path(spawned):
    actor, name = spawned["ActorPath"], spawned["Name"]
    assert isinstance(name, str) and name, spawned
    assert isinstance(actor, str) and actor.endswith(":PersistentLevel." + name), spawned
    return actor


def assert_pcg_grid_points(data, limit, offset=0):
    """验证旧版点数组与 5.8+ 原生数据视图的真实输出和分页。"""
    total, returned = data["Total"], data["Returned"]
    assert total > offset and returned == min(limit, total - offset), data
    legacy = "Items" in data
    if legacy:
        assert "Datasets" not in data, data
        rows = merge_with_defaults(data["Items"], data.get("Items_defaults", {}))
        assert [row["Index"] for row in rows] == list(range(offset, offset + returned)), data
        properties = ("Transform", "Density", "Seed")
    else:
        datasets = merge_with_defaults(data["Datasets"], data.get("Datasets_defaults", {}))
        assert datasets, data
        rows, dataset_offset = [], 0
        for dataset in datasets:
            count = dataset["TotalElements"]
            assert count >= 0 and dataset["DatasetOffset"] == dataset_offset, dataset
            indices = range(max(0, offset - dataset_offset), min(count, offset + limit - dataset_offset))
            expected = [f"element_{index}" for index in indices]
            assert {key for key in dataset if key.startswith("element_")} == set(expected), dataset
            rows.extend(dataset[key] for key in expected)
            dataset_offset += count
        assert dataset_offset == total, data
        properties = ("@Points.$Transform", "@Points.$Density", "@Points.$Seed")
    assert len(rows) == returned, data
    for row in rows:
        transform, density, seed = (row[key] for key in properties)
        assert type(density) in (int, float) and density == pytest.approx(1.0), row
        if legacy:
            assert isinstance(transform, str) and transform, row
            components = [[float(value) for value in group.split(",")] for group in transform.split("|")]
            assert len(components) == 3 and all(len(group) == 3 for group in components), row
            assert all(math.isfinite(value) for group in components for value in group), row
            assert type(seed) is int and -(2**31) <= seed < 2**31, row
        else:
            assert isinstance(transform, dict) and set(transform) == {"translation", "rotation", "scale"}, row
            for key, size in (("translation", 3), ("rotation", 4), ("scale", 3)):
                values = transform[key]
                assert isinstance(values, list) and len(values) == size, row
                assert all(type(value) in (int, float) and math.isfinite(value) for value in values), row
            assert isinstance(seed, str) and str(int(seed)) == seed and -(2**31) <= int(seed) < 2**31, row


def test_project_skill_list_and_detail(mcp, require_tools):
    require_tools("GetProjectSkills", "ExecPython")
    name = "nexus-discovery-" + uuid.uuid4().hex
    text = "---\nname: " + name + "\ndescription: Nexus independent discovery fixture\n---\nRead the fixture description.\n"
    setup = f"""import pathlib, unreal
_nexus_skill_dir = pathlib.Path(unreal.Paths.project_dir()) / 'Skills' / {name!r}
_nexus_skill_dir.mkdir(parents=True, exist_ok=False)
(_nexus_skill_dir / 'SKILL.md').write_bytes({text!r}.encode('utf-8'))
"""
    mcp.call("ExecPython", Code=setup)
    try:
        listed = official(mcp, "GetProjectSkills")
        matches = [item for item in listed["Skills"] if item["Name"] == name]
        assert len(matches) == 1, listed
        skill = matches[0]
        assert skill["Description"] == "Nexus independent discovery fixture", skill
        assert skill["SkillPath"].replace("\\", "/").endswith("/" + name + "/SKILL.md"), skill
        details = official(mcp, "GetProjectSkills", Action="Details", SkillPath=skill["SkillPath"])
        assert len(details["Skills"]) == 1 and details["Skills"][0]["Instructions"] == text, details
        for arguments in ({"Action": "Details"},
                          {"Action": "Details", "SkillPath": skill["SkillPath"] + ".unlisted"}):
            invalid = mcp.try_call("GetProjectSkills", **arguments)
            assert invalid.get("isError"), invalid
    finally:
        cleanup = f"""import pathlib, unreal
_nexus_skill_dir = pathlib.Path(unreal.Paths.project_dir()) / 'Skills' / {name!r}
_nexus_skill_file = _nexus_skill_dir / 'SKILL.md'
if _nexus_skill_file.exists():
    _nexus_skill_file.unlink()
if _nexus_skill_dir.exists():
    _nexus_skill_dir.rmdir()
"""
        mcp.call("ExecPython", Code=cleanup)
    after = official(mcp, "GetProjectSkills")
    assert not any(item["Name"] == name for item in after["Skills"]), after


@pytest.mark.skipif_ue_below("5.8")
def test_semantic_search_adapter(mcp, require_tools, test_ns):
    native_domain(mcp, require_tools, "SearchAssetsSemantic", "SemanticSearchToolset")
    invalid = mcp.try_call("SearchAssetsSemantic", Query="materials", ClassPaths=[])
    assert invalid.get("isError"), invalid
    try:
        result = official(mcp, "SearchAssetsSemantic", Query="simple surface material", ClassPaths=["/Script/Engine.Material"], PathRegexes=["^" + test_ns + "/"], Limit=3)
    except MCPError as error:
        text = str(error).lower()
        if any(reason in text for reason in ("no embedding provider", "embedding generation failed",
                                            "vector index is not initialized", "vector index is empty")):
            pytest.skip(f"SemanticSearch environment unavailable: {error}")
        raise
    assert isinstance(result.get("Items"), list), result


@pytest.mark.skipif_ue_below("5.4")
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
    actor = pcg_actor_path(spawned)
    items = merge_with_defaults(instances["Items"], instances.get("Items_defaults", {}))
    matches = [item for item in items if item["Path"] == actor]
    assert len(matches) == 1 and matches[0]["Name"] == spawned["Name"], (spawned, instances)
    try:
        official(mcp, "GetEditorPCG", Action="NodeData", ActorPath=actor, NodePath=grid["Path"], PinLabel=grid["OutputPins"][0], Limit=2)
    except MCPError as error:
        assert "inspection" in str(error).lower(), str(error)[:1000]
    executed = official(mcp, "ControlEditorPCG", Action="Execute", ActorPath=actor)
    assert executed["bGenerationFinished"] is True and executed["ActorPath"] == actor, executed
    data = official(mcp, "GetEditorPCG", Action="NodeData", ActorPath=actor, NodePath=grid["Path"], PinLabel=grid["OutputPins"][0], Limit=2)
    assert_pcg_grid_points(data, 2)


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
