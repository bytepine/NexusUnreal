# Copyright byteyang. All Rights Reserved.
"""编辑器 Slate 局部鼠标输入与边界校验。"""
import pytest

from test_15_editor_operations import operation_result


@pytest.mark.requires_gui
def test_editor_slate_pointer_input(mcp, require_tools):
    require_tools("GetEditorSlate", "InteractEditorSlate", "ControlEditorAutomation", "GetEditorOperation")
    operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Discover"))
    name = "NexusLink.EditorOperations.SlatePointer"
    result = operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Run", TestNames=[name]))
    assert len(result["Tests"]) == 1 and result["Tests"][0]["Name"] == name, result
    assert result["Tests"][0]["Outcome"] == "Passed", result
