#!/usr/bin/env python3
"""Export a stopped Automation trace through an isolated editor's explicit endpoint."""
import argparse
import json
import subprocess
import time
from pathlib import Path
from gas_network_retest import PROJECT, free_port
from gas_retest.runner import Client, RunError
from trace_compare.runner import export_snapshot, main as trace_main, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ue-root", required=True, type=Path)
    parser.add_argument("--trace", type=Path, default=PROJECT / "Saved/Profiling/NexusLinkTraceReadTest.utrace")
    parser.add_argument("--output", type=Path, default=PROJECT / "Saved/TraceCompareAcceptance")
    args = parser.parse_args()
    if not args.trace.is_file(): raise RunError("Run NexusLink.Trace.GetTrace.Readback Automation first")
    args.output.mkdir(parents=True, exist_ok=True)
    port = free_port(); url = f"http://127.0.0.1:{port}/stream"
    command = [str(args.ue_root / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"), str(PROJECT / "Nexus.uproject"),
               "-nullrhi", "-nosound", "-unattended", "-nop4", "-nomessaging", "-nosplash", "-EnableNexusMcp",
               "-stdout", "-FullStdOutLogOutput", f"-NexusMcpPort={port}", f"-NexusWsPort={free_port()}"]
    client = None
    with (args.output / "editor.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            deadline = time.monotonic() + 120
            while True:
                if process.poll() is not None or time.monotonic() > deadline: raise RunError("Editor did not start")
                try: client = Client({"Url": url}); break
                except RunError: time.sleep(.5)
            deadline = time.monotonic() + 30
            while True:
                response = client.call("GetTrace", {"TracePath": str(args.trace.resolve()), "Sections": ["Summary"]})
                if response["IsError"]: raise RunError(str(response["Payload"]))
                summary = response["Payload"]
                if summary.get("bAnalysisComplete"): break
                if time.monotonic() > deadline: raise RunError("Analysis did not complete")
                time.sleep(.1)
            conditions = {"Scenario": "Automation stopped trace export", "BuildId": "acceptance",
                          "Engine": args.ue_root.name, "Platform": "Win64", "Hardware": "local acceptance host",
                          "RenderConfig": "NullRHI", "QualityConfig": "not rendered", "WarmupSeconds": 0}
            snapshot = export_snapshot(url, str(args.trace.resolve()), conditions, 0, summary["DurationSeconds"], timer_limit=1)
            write_json(args.output / "snapshot.json", snapshot)
            assert snapshot["Data"]["FrameCount"] > 0
            assert snapshot["Data"]["bTimersTruncated"] == (snapshot["Data"]["TotalTimerCount"] > 1)
            code = trace_main(["compare", "--before", str(args.output / "snapshot.json"), "--after", str(args.output / "snapshot.json"), "--output", str(args.output / "comparison")])
            assert code == 0
            result = json.loads((args.output / "comparison/comparison.json").read_text(encoding="utf-8"))
            assert all(metric["AbsoluteChange"] == 0 for metric in result["Frames"].values())
            print("Stopped trace export, window, CPU truncation, raw evidence and offline report PASS")
        finally:
            if client: client.close()
            process.terminate()
            try: process.wait(timeout=20)
            except subprocess.TimeoutExpired: process.kill(); process.wait()


if __name__ == "__main__": main()
