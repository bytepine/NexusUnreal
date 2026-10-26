#!/usr/bin/env python3
"""Run a real inherited-Blackboard retest in an isolated GameModeBase server."""
import argparse
import json
from pathlib import Path
import subprocess
import time
from gas_network_retest import PROJECT, free_port
from retest.runner import Client, RunError, write_reports
from retest.compare import compare_reports, write_comparison, save_baseline
from bt_retest.runner import Runner
from bt_retest.template import blackboard_condition


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ue-root", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=PROJECT / "Saved/BtRetestAcceptance")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    port = free_port(); endpoint = {"Url": f"http://127.0.0.1:{port}/stream", "bAuthority": True}
    command = [str(args.ue_root / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"), str(PROJECT / "Nexus.uproject"),
               "/Engine/Maps/Entry?game=/Script/Engine.GameModeBase", "-server", "-nullrhi", "-nosound", "-unattended",
               "-nop4", "-nomessaging", "-nosplash", "-EnableNexusMcp", "-stdout", "-FullStdOutLogOutput",
               f"-NexusMcpPort={port}", f"-NexusWsPort={free_port()}"]
    client = None
    with (args.output / "server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            deadline = time.monotonic() + 120
            while True:
                if process.poll() is not None or time.monotonic() > deadline: raise RunError("BT server did not start")
                try: client = Client(endpoint); break
                except RunError: time.sleep(.5)
            def call(cap, **arguments):
                response = client.call(cap, arguments)
                if response["IsError"]: raise RunError(f"{cap}: {response['Payload']}")
                return response["Payload"]
            spawned = call("SpawnRuntimeActor", ClassName="NexusBehaviorRetestPawn")
            name = spawned.get("ActorName") or spawned["name"]
            tree = call("GetRuntimeActorBehaviorTree", ActorName=name)
            condition = next(key for key in tree["BlackboardKeys"] if key["name"] == "CanRun")
            assert condition["bInherited"] and condition["TypeName"] == "Bool" and condition["TypedValue"] is False
            invalid = client.call("InteractRuntimeActorBehaviorTree", {"ActorName": name, "Action": "SetBlackboard", "KeyName": "CanRun", "Value": "not-a-bool"})
            assert invalid["IsError"]
            assert next(key for key in call("GetRuntimeActorBehaviorTree", ActorName=name)["BlackboardKeys"] if key["name"] == "CanRun")["TypedValue"] is False
            config = {"Name": "Inherited Blackboard condition", "Endpoint": endpoint, "ActorName": name, "TreePath": tree["TreePath"],
                      "Condition": {"Key": "CanRun", "Type": "Bool", "BlockedValue": False, "ChangedValue": True},
                      "Before": {"Node": "Blocked"}, "Expected": {"Node": "Allowed"}, "Timeout": 1, "Interval": .03}
            case = blackboard_condition(config)
            (args.output / "case.json").write_text(json.dumps(case, indent=2), encoding="utf-8")
            preflight = Runner(case).run(preflight=True); write_reports(preflight, args.output / "preflight")
            assert preflight["ExitCode"] == 0
            call("SetRuntimeActorProperty", Updates=[{"ActorName": name, "PropertyPath": "bHoldBlocked", "Value": "true"}])
            before = Runner(case).run(); write_reports(before, args.output / "blocked")
            assert before["ExitCode"] == 1
            failed = next(record for record in before["Records"] if record["Id"] == "expected")
            assert failed["Result"]["Payload"]["bRunning"] is True
            assert next(key for key in failed["Result"]["Payload"]["BlackboardKeys"] if key["name"] == "CanRun")["TypedValue"] is True
            assert next(record for record in before["Records"] if record["Id"] == "restored")["Status"] == "Passed"
            call("SetRuntimeActorProperty", Updates=[{"ActorName": name, "PropertyPath": "bHoldBlocked", "Value": "false"}])
            after = Runner(case).run(); write_reports(after, args.output / "recovered")
            assert after["ExitCode"] == 0
            observed = next(record for record in after["Records"] if record["Id"] == "expected")["Result"]["Payload"]
            assert observed["TreePath"] != observed["RootTreePath"]
            comparison = compare_reports(before, after)
            assert comparison["Counts"]["Recovered"] > 0
            write_comparison(comparison, before, after, args.output / "comparison")
            save_baseline(after, args.output / "baseline.json")
            again = Runner(case).run(); write_reports(again, args.output / "again")
            assert compare_reports(after, again)["ExitCode"] == 0
            controller_case = blackboard_condition({**config, "Name": "Explicit controller", "ActorName": tree["Controller"]})
            controller = Runner(controller_case).run(); write_reports(controller, args.output / "controller")
            assert controller["ExitCode"] == 0
            call("InteractRuntimeActorBehaviorTree", ActorName=name, Action="StopTree")
            stopped = Runner(case).run(preflight=True); write_reports(stopped, args.output / "stopped")
            assert stopped["ExitCode"] == 2
            call("DestroyRuntimeActor", ActorName=name)
            destroyed = Runner(case).run(preflight=True); write_reports(destroyed, args.output / "destroyed")
            assert destroyed["ExitCode"] == 2
            print("BT inherited keys, invalid type, explicit Pawn/Controller, failure/recovery, timeout evidence, restore, baseline, stopped tree and destroyed target PASS")
        finally:
            if client: client.close()
            process.terminate()
            try: process.wait(timeout=20)
            except subprocess.TimeoutExpired: process.kill(); process.wait()


if __name__ == "__main__": main()
