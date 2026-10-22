# Copyright byteyang. All Rights Reserved.
"""公共协议与写路径的定向回归；资产均落在本轮 test_ns。"""

import pytest

from _framework.mcp_client import MCPClient, MCPError, cap_first


def test_reliability_protocol_contract(mcp, _ue_url):
    second = MCPClient(_ue_url)
    try:
        initialized = second.initialize()
        assert "capabilities" in initialized, initialized
        assert "instructions" in initialized, initialized
        assert initialized["capabilities"]["tools"]["listChanged"] is True
        for tool in second.list_tools():
            assert isinstance(tool.get("inputSchema"), dict), tool
            assert "InputSchema" not in tool and "Annotations" not in tool, tool
        with pytest.raises(MCPError) as error:
            second._rpc("tools/call", {"name": "__invalid_tool__"})
        assert error.value.code == -32601, error.value.raw
    finally:
        second.close()


@pytest.mark.parametrize("section", ["CurrentMap", "All"])
def test_reliability_editor_sections(mcp, section):
    result = cap_first(mcp.call_capability("GetEditorContext", Sections=[section]))
    assert not result.get("SectionErrors"), result
    assert result.get("bIsEditorWorld") is True and result.get("MapName"), result


@pytest.fixture
def reliability_table(mcp, test_ns, request):
    path = f"{test_ns}/DT_Reliability_{request.node.name}"
    mcp.call_capability("CreateAssetDataTable", AssetPath=path, RowStructName="NexusReliabilityTestRow")
    return path


def test_reliability_datatable_fields(mcp, reliability_table):
    mcp.call_capability(
        "ManageAssetDataTable", AssetPath=reliability_table, bSaveToDisk=True,
        Operations=[{"Action": "Add", "RowName": "Initial", "Fields": {
            "Label": "stored", "Count": 42, "bEnabled": True, "Values": "(1,2,3)",
        }}],
    )
    row = cap_first(mcp.call_capability(
        "GetAssetDataTable", AssetPath=reliability_table, Mode="Rows", RowNames=["Initial"],
    ))
    fields = {field["name"]: {**row.get("Fields_defaults", {}), **field} for field in row["Fields"]}
    assert fields["Count"]["Value"] == "42", row
    assert "stored" in fields["Label"]["Value"], row
    failed = mcp.try_call("ManageAssetDataTable", AssetPath=reliability_table,
                          Operations=[{"Action": "Add", "RowName": "Bad", "Fields": {"Unknown": 1}}])
    assert failed["isError"] and "Error" in str(failed["structuredContent"]), failed


def test_reliability_batch_business_failure(mcp, reliability_table):
    response = mcp.try_call("CallCapability", Calls=[
        {"Capability": "ManageAssetDataTable", "Arguments": {
            "AssetPath": reliability_table, "bSaveToDisk": True,
            "Operations": [{"Action": "Add", "RowName": "RevertMe"}],
        }},
        {"Capability": "ManageAssetDataTable", "Arguments": {
            "AssetPath": reliability_table,
            "Operations": [{"Action": "Remove", "RowName": "Missing"}],
        }},
    ])
    assert response["isError"], response
    batch = response["structuredContent"]
    assert batch["FailureCount"] == 1 and batch["bRolledBack"] is True, batch
    table = cap_first(mcp.call_capability("GetAssetDataTable", AssetPath=reliability_table, Mode="Schema"))
    assert "RevertMe" not in table["RowNames"], table


def test_reliability_independent_reads(mcp, _ue_url, test_ns):
    path = f"{test_ns}/M_Reliability"
    mcp.call_capability("CreateAssetMaterial", AssetPath=path)
    mcp.call_capability("GetAssetMaterial", AssetPath=path, Sections=["All"])
    with MCPClient(_ue_url) as second:
        result = cap_first(second.call_capability("GetAssetMaterial", AssetPath=path, Sections=["Params"]))
        assert "Parameters" in result and "Skipped:" not in str(result), result
