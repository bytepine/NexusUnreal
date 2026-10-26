#!/usr/bin/env python3
"""Validate project-neutral replay in an isolated GameModeBase server; never edits project config."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from gas_network_retest import PROJECT, free_port
from gas_retest.runner import Client, Runner, RunError, write_reports
from gas_retest.template import generic_activation
from gas_retest.compare import compare_reports, write_comparison, save_baseline
from gas_retest.report import collect_evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ue-root", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=PROJECT / "Saved/GenericGasRetest")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    port = free_port()
    endpoint = {"Url": f"http://127.0.0.1:{port}/stream", "bAuthority": True}
    command = [str(args.ue_root / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"), str(PROJECT / "Nexus.uproject"),
               "/Engine/Maps/Entry?game=/Script/Engine.GameModeBase", "-server", "-nullrhi", "-nosound", "-unattended",
               "-nop4", "-nomessaging", "-nosplash", "-stdout", "-FullStdOutLogOutput", "-EnableNexusMcp",
               f"-NexusMcpPort={port}", f"-NexusWsPort={free_port()}"]
    client = None
    with (args.output / "server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            deadline = time.monotonic() + 120
            while True:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RunError("Generic server did not start; inspect server.log")
                try:
                    client = Client(endpoint); break
                except RunError:
                    time.sleep(0.5)

            def call(cap, **arguments):
                result = client.call(cap, arguments)
                if result["IsError"]: raise RunError(f"{cap}: {result['Payload']}")
                return result["Payload"]

            for kind in ("Actor", "Pawn", "StatePawn"):
                spawned = call("SpawnRuntimeActor", ClassName="NexusGenericGasTest" + kind)
                name = spawned.get("ActorName") or spawned["name"]
                directory = args.output / kind
                config = {"Name": "Generic" + kind, "Endpoints": {"Server": endpoint},
                          "Actors": {"Target": {"Bindings": {"Server": name}}},
                          "AbilityPath": "/Script/Nexus.NexusGenericGasTestAbility",
                          "ActivationEndpoint": "Server", "AuthorityEndpoint": "Server", "ExpectedEvent": "Committed",
                          "FailureTagHints": {"Nexus.Diagnostics.Rejected": "Test fixture rejected activation; restore bRejectActivation."}}
                case = generic_activation(config)
                next(step for step in case["Steps"] if step["Id"] == "authority")["Timeout"] = 0.5
                try:
                    preflight = Runner(case).run(preflight=True)
                    write_reports(preflight, directory / "preflight")
                    (directory / "case.json").write_text(json.dumps(case, indent=2), encoding="utf-8")
                    if preflight["ExitCode"]: raise RunError(f"{kind}: preflight failed")
                    context = preflight["Contexts"]["Server"]
                    assert context["bActorInfoReady"] and context["ActorId"] and context["AscId"]
                    assert (context["OwnerId"] != context["AvatarId"]) == (kind == "StatePawn")
                    if kind == "Actor": assert context["PlayerId"] == -1
                    call("SetRuntimeActorProperty", Updates=[{"ActorName": name, "PropertyPath": "bRejectActivation", "Value": "true"}])
                    before = Runner(case).run()
                    write_reports(before, directory / "rejected")
                    assert before["ExitCode"] == 1
                    assert any("Nexus.Diagnostics.Rejected" in e.get("FailureTags", []) for e in collect_evidence(before)[1])
                    call("SetRuntimeActorProperty", Updates=[{"ActorName": name, "PropertyPath": "bRejectActivation", "Value": "false"}])
                    after = Runner(case).run()
                    write_reports(after, directory / "restored")
                    assert after["ExitCode"] == 0
                    comparison = compare_reports(before, after)
                    assert comparison["Counts"]["Recovered"] > 0
                    write_comparison(comparison, before, after, directory / "comparison")
                    save_baseline(after, directory / "baseline.json")
                    again = Runner(case).run()
                    write_reports(again, directory / "again")
                    assert compare_reports(after, again)["ExitCode"] == 0
                    print(f"{kind}: preflight, failure evidence, restoration, repeat and baseline PASS", flush=True)
                finally:
                    call("DestroyRuntimeActor", ActorName=name)
            return 0
        finally:
            if client: client.close()
            process.terminate()
            try: process.wait(timeout=20)
            except subprocess.TimeoutExpired: process.kill(); process.wait()


if __name__ == "__main__":
    sys.exit(main())
