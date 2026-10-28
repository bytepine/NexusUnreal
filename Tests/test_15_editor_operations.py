# Copyright byteyang. All Rights Reserved.
"""编辑器工具：会话隔离、输出契约与 GUI 只读闭环。"""
import time
import pytest
from _framework.mcp_client import cap_first


def operation_result(mcp, result):
    result = cap_first(result)
    deadline = time.monotonic() + 70
    while result.get("State") == "Running" and time.monotonic() < deadline:
        result = cap_first(mcp.call("GetEditorOperation", OperationId=result["OperationId"], WaitSeconds=1))
    assert result["State"] == "Completed", result
    assert result["bCanCancel"] is False
    return result["Result"]


def test_editor_operation_unknown_id(mcp, require_tools):
    require_tools("GetEditorOperation")
    result = mcp.try_call("GetEditorOperation", OperationId="unknown-operation")
    assert result.get("isError") is True or "Error" in str(result), result


@pytest.mark.requires_gui
def test_editor_slate_read_and_capture(mcp, require_tools):
    require_tools("GetEditorSlate", "CaptureEditorSlate", "GetEditorOperation")
    windows = operation_result(mcp, mcp.call("GetEditorSlate", Action="Windows"))
    assert windows.get("Windows"), windows
    snapshot = operation_result(mcp, mcp.call("GetEditorSlate", Action="Snapshot", MaxDepth=2))
    assert snapshot.get("Nodes") or snapshot.get("Snapshot"), snapshot
    image = operation_result(mcp, mcp.call("CaptureEditorSlate", Ref=windows["Windows"][0]["Ref"]))
    assert image.get("FilePath"), image


def test_editor_automation_local_run(mcp, require_tools):
    require_tools("ControlEditorAutomation", "ListEditorAutomationTests", "GetEditorOperation")
    operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Discover"))
    listed = operation_result(mcp, mcp.call("ListEditorAutomationTests", NameFilter="NexusLink.EditorOperations.OwnerAndContract"))
    name = "NexusLink.EditorOperations.OwnerAndContract"
    assert name in listed["Tests"], listed
    result = operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Run", TestNames=[name]))
    assert len(result["Tests"]) == 1, result
    assert result["Tests"][0]["Name"] == name, result
    assert result["Tests"][0]["Outcome"] == "Passed", result["Tests"][0]
    assert isinstance(result["Tests"][0]["Errors"], list), result
    assert isinstance(result["Tests"][0]["Warnings"], list), result


@pytest.mark.requires_gui
def test_editor_slate_advanced_interactions(mcp, require_tools):
    require_tools("ControlEditorAutomation", "InteractEditorSlate", "GetEditorOperation")
    operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Discover"))
    name = "NexusLink.EditorOperations.SlateInput"
    result = operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Run", TestNames=[name]))
    assert len(result["Tests"]) == 1 and result["Tests"][0]["Name"] == name, result
    assert result["Tests"][0]["Outcome"] == "Passed", result
