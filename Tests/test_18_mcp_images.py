# Copyright byteyang. All Rights Reserved.
"""标准 MCP 图片内容：真实 PNG/JPEG、异步查询、关闭返回和批次透传。"""
import base64
import json
import time
import pytest
from _framework.mcp_client import cap_first
from test_15_editor_operations import operation_result


def payload(raw):
    if "structuredContent" in raw:
        return raw["structuredContent"]
    text = next(item["text"] for item in raw.get("content", []) if item.get("type") == "text")
    return json.loads(text)


def assert_image(raw, mime):
    assert not raw.get("isError"), "Capture returned a tool error"
    images = [item for item in raw.get("content", []) if item.get("type") == "image"]
    assert len(images) == 1, f"Expected one inline image, got {len(images)}"
    assert images[0]["mimeType"] == mime
    image = base64.b64decode(images[0]["data"], validate=True)
    assert image.startswith(b"\x89PNG\r\n\x1a\n" if mime == "image/png" else b"\xff\xd8\xff")
    assert cap_first(payload(raw)).get("FilePath") or cap_first(payload(raw)).get("Result", {}).get("FilePath")


def test_mcp_image_protocol_bounds(mcp, require_tools):
    require_tools("ControlEditorAutomation", "GetEditorOperation")
    operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Discover"))
    result = operation_result(mcp, mcp.call("ControlEditorAutomation", Action="Run", TestNames=["NexusLink.Protocol.ImageContent"]))
    assert result["Tests"][0]["Outcome"] == "Passed", result


@pytest.mark.requires_gui
@pytest.mark.parametrize("format,mime", [("png", "image/png"), ("jpg", "image/jpeg")])
def test_capture_viewport_image_content(mcp, require_tools, format, mime):
    require_tools("CaptureViewport")
    raw = mcp.try_call("CaptureViewport", Target="editor", MaxSize=256, Format=format)
    assert_image(raw, mime)
    assert cap_first(payload(raw))["TtlSeconds"] == 0
    disabled = mcp.try_call("CaptureViewport", Target="Editor", MaxSize=128, bIncludeImage=False)
    assert not disabled.get("isError") and cap_first(payload(disabled)).get("FilePath")
    assert not any(item.get("type") == "image" for item in disabled.get("content", []))


@pytest.mark.requires_gui
def test_slate_capture_image_through_operation_wait(mcp, require_tools):
    require_tools("CaptureEditorSlate", "GetEditorOperation")
    windows = operation_result(mcp, mcp.call("GetEditorSlate", Action="Windows"))["Windows"]
    raw = mcp.try_call("CaptureEditorSlate", Ref=windows[0]["Ref"])
    deadline = time.monotonic() + 30
    while cap_first(payload(raw)).get("State") == "Running" and time.monotonic() < deadline:
        raw = mcp.try_call("GetEditorOperation", OperationId=cap_first(payload(raw))["OperationId"], WaitSeconds=1)
    assert_image(raw, "image/png")


@pytest.mark.requires_gui
def test_capture_images_survive_batch(mcp, require_tools):
    require_tools("CaptureViewport")
    raw = mcp.try_call("CallCapability", calls=[
        {"Capability": "CaptureViewport", "Arguments": {"Target": "Editor", "MaxSize": 128}},
        {"Capability": "CaptureViewport", "Arguments": {"Target": "Editor", "MaxSize": 128}},
    ])
    assert not raw.get("isError"), "Capture batch failed"
    assert len([item for item in raw.get("content", []) if item.get("type") == "image"]) == 2
