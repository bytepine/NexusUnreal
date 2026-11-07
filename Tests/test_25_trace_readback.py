# Copyright byteyang. All Rights Reserved.
"""用已停录的原生夹具验证 Trace 各节经过 MCP 的实际回读。"""
import os
from pathlib import Path
import time
import pytest
from _framework.mcp_client import cap_first


@pytest.mark.skipif_ue_below("5.0")
def test_stopped_trace_sections(mcp, require_tools):
    # 使用已退出生产进程的文件，避免在被测编辑器中停掉用户录制或阻塞帧派发。
    source = os.environ.get("NEXUS_STOPPED_TRACE")
    if not source:
        pytest.skip("Set NEXUS_STOPPED_TRACE to the stopped Automation producer's trace")
    require_tools("GetTrace")
    trace = Path(source).resolve()
    assert trace.is_file(), trace
    deadline = time.monotonic() + 30
    while True:
        summary = cap_first(mcp.call("GetTrace", TracePath=str(trace), Sections=["Summary"]))
        if summary["bAnalysisComplete"]:
            break
        assert time.monotonic() < deadline, summary
        time.sleep(0.1)
    result = cap_first(mcp.call("GetTrace", TracePath=str(trace), Sections=["Summary", "Frames", "Timers", "Bookmarks"], TimerLimit=1))
    assert result["bAnalysisComplete"] and result["GameFrameCount"] >= 1 and result["FrameCount"] >= 1, result
    assert result["Timers"] and result["TotalTimerCount"] >= len(result["Timers"]), result
    assert result["bTimersTruncated"] == (result["TotalTimerCount"] > 1), result
    assert any("NexusLinkTraceProbe" in item["Text"] for item in result["Bookmarks"]), result
