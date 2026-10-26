#!/usr/bin/env python3
"""Launch an isolated server and two clients; verify GAS evidence and repair/retest.

py Script/gas_network_retest.py --ue-root E:/EpicGames/UE_5.7 --uproject <built-project> --repeat 10
The provided project must have the diagnostic C++ classes compiled. Never changes its config.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "Plugins/NexusLink/tools"))
from gas_retest.runner import Client, Runner, RunError, write_reports
from gas_retest.report import write_index

ABILITY = "/Script/Nexus.NexusDiagnosticAbility"
SERVER_ABILITY = "/Script/Nexus.NexusDiagnosticServerAbility"
GET = "GetRuntimeActorAbilitySystem"
INTERACT = "InteractRuntimeActorAbilitySystem"
QUICKSTART_SCENARIOS = ("PredictionRejected", "Success")


def actor(endpoint):
    return {"Ref": f"/Actors/Hero/{endpoint}"}


def call(identifier, endpoint, action, **args):
    return {"Id": identifier, "Type": "Call", "Endpoint": endpoint, "Capability": INTERACT,
            "Arguments": {"ActorName": actor(endpoint), "Action": action, **args}}


def read(identifier, endpoint, sections, **args):
    return {"Id": identifier, "Type": "Call", "Endpoint": endpoint, "Capability": GET,
            "Arguments": {"ActorName": actor(endpoint), "Sections": sections, **args}}


def assertion(identifier, reference, value, op="Equal"):
    return {"Id": identifier, "Type": "Assert", "Actual": {"Ref": reference}, "Value": value, "Op": op}


def await_event(identifier, endpoint, capture, event):
    step = read(identifier, endpoint, ["ActivationEvents"], CaptureId={"Ref": f"/Steps/{capture}/Payload/CaptureId"})
    step.update(Type="Await", Check={"Path": "/Payload/EventTypes", "Op": "Contains", "Value": event})
    return step


def build_case(endpoints, scenario, ability=ABILITY):
    if scenario in ("MissingRequired", "Blocked", "Cost", "Cooldown"):
        ability = SERVER_ABILITY
    case = {"SchemaVersion": 1, "Name": scenario, "Endpoints": endpoints,
            "Actors": {"Hero": {"ClassFilter": "NexusDiagnosticCharacter", "OwnerEndpoint": "Owner"}},
            "RequiredAbilities": [{"Actor": "Hero", "Endpoint": role, "AbilityPath": ability} for role in ("Server", "Owner")],
            "Setup": [], "Steps": [], "Teardown": []}
    setup, steps, cleanup = case["Setup"], case["Steps"], case["Teardown"]
    for role in ("Server", "Owner"):
        setup.extend([
            call(f"clearCooldown{role}", role, "RemoveEffect", EffectPath="NexusDiagnosticCooldown"),
            call(f"setMana{role}", role, "SetAttribute", AttributeName="NexusDiagnosticAttributes.Mana", Value=100),
        ])
    # 不重复添加 Blocked，使用明确的一次添加/一次移除。
    if scenario in ("MissingRequired", "Blocked", "Cost", "Cooldown", "PredictionRejected"):
        if scenario == "MissingRequired":
            setup.append(call("break", "Server", "RemoveLooseTag", Tag="Nexus.Diagnostics.Required"))
            cleanup.append(call("restoreRequired", "Server", "AddLooseTag", Tag="Nexus.Diagnostics.Required"))
        elif scenario == "Blocked":
            setup.append(call("break", "Server", "AddLooseTag", Tag="Nexus.Diagnostics.Blocked"))
            cleanup.append(call("restoreBlocked", "Server", "RemoveLooseTag", Tag="Nexus.Diagnostics.Blocked"))
        elif scenario == "Cost":
            setup.append(call("break", "Server", "SetAttribute", AttributeName="NexusDiagnosticAttributes.Mana", Value=0))
            cleanup.append(call("restoreMana", "Server", "SetAttribute", AttributeName="NexusDiagnosticAttributes.Mana", Value=100))
        elif scenario == "Cooldown":
            setup.append(call("break", "Server", "ApplyEffect", EffectPath="/Script/Nexus.NexusDiagnosticCooldown"))
            cleanup.append(call("restoreCooldown", "Server", "RemoveEffect", EffectPath="NexusDiagnosticCooldown"))
        else:
            setup.append({"Id": "break", "Type": "Call", "Endpoint": "Server", "Capability": "SetRuntimeActorProperty",
                          "Arguments": {"Updates": [{"ActorName": actor("Server"), "PropertyPath": "bRejectActivation", "Value": "true"}]}})
            cleanup.append({"Id": "restoreReject", "Type": "Call", "Endpoint": "Server", "Capability": "SetRuntimeActorProperty",
                            "Arguments": {"Updates": [{"ActorName": actor("Server"), "PropertyPath": "bRejectActivation", "Value": "false"}]}})
    if scenario == "NotGranted":
        steps.extend([read("before", "Server", ["Abilities"]),
                      read("diagnose", "Server", ["ActivationDiagnostics"], AbilityPath="/Script/GameplayAbilities.GameplayAbility"),
                      assertion("notGranted", "/Steps/diagnose/Payload/ActivationDiagnostics/bGranted", False),
                      call("attempt", "Server", "TryActivateGrantedAbility", AbilityPath="/Script/GameplayAbilities.GameplayAbility"),
                      read("after", "Server", ["Abilities"]),
                      {"Id": "noImplicitGrant", "Type": "Assert", "Actual": {"Ref": "/Steps/after/Payload/Abilities"},
                       "Value": {"Ref": "/Steps/before/Payload/Abilities"}}])
        steps[3]["ExpectError"] = True
        return case
    for role in ("Server", "Owner"):
        setup.append(call(f"capture{role}", role, "StartActivationCapture"))
    steps.append(read("diagnose", "Server", ["Context", "Tags", "ActivationDiagnostics", "Attributes", "Effects"], AbilityPath=ability))
    if scenario == "MissingRequired":
        steps.append(assertion("reason", "/Steps/diagnose/Payload/ActivationDiagnostics/MissingRequiredTags", "Nexus.Diagnostics.Required", "Contains"))
    if scenario == "Blocked":
        steps.append(assertion("reason", "/Steps/diagnose/Payload/ActivationDiagnostics/BlockingOwnedTags", "Nexus.Diagnostics.Blocked", "Contains"))
    # 前四个场景在权威端主动复现；网络预测拒绝及成功由所属客户端发起。
    sender = "Owner" if scenario in ("PredictionRejected", "Success", "ServerOnly") else "Server"
    steps.append(call("attempt", sender, "TryActivateGrantedAbility", AbilityPath=ability))
    failure = scenario not in ("Success", "ServerOnly")
    steps.append(await_event("authority", "Server", "captureServer", "Failed" if failure else "Committed"))
    steps.append({"Id": "authoritySkill", "Type": "Assert", "Actual": {"Ref": "/Steps/authority/Payload/Events/0/SpecHandle"},
                  "Value": {"Ref": "/Steps/diagnose/Payload/ActivationDiagnostics/SpecHandle"}})
    steps.append(assertion("authorityClass", "/Steps/authority/Payload/Events/0/AbilityPath", ability))
    if scenario in ("Cost", "Cooldown", "PredictionRejected"):
        tag = {"Cost": "Cost", "Cooldown": "Cooldown", "PredictionRejected": "Rejected"}[scenario]
        steps.append(assertion("failureTag", "/Steps/authority/Payload/FailureTags", f"Nexus.Diagnostics.{tag}", "Contains"))
    if scenario == "PredictionRejected":
        steps.append(await_event("prediction", "Owner", "captureOwner", "Activated"))
        steps.append(assertion("requestAccepted", "/Steps/attempt/Payload/bRequestAccepted", True))
        steps.append({"Id": "predictionSkill", "Type": "Assert", "Actual": {"Ref": "/Steps/prediction/Payload/Events/0/SpecHandle"},
                      "Value": {"Ref": "/Steps/attempt/Payload/SpecHandle"}})
    if not failure:
        steps.append({"Id": "observer", "Type": "Await", "Endpoint": "Observer", "Capability": "GetRuntimeActorProperty",
                      "Arguments": {"ActorName": actor("Observer"), "PropertyPaths": ["CommitCount"]},
                      "Check": {"Path": "/Payload/Results/0/Value", "Op": "Equal", "Value": {"Ref": "/Steps/commitCount/Payload/Results/0/Value"}}})
        # 提交事件证明技能执行；观察端再等待复制的计数与权威端一致。
        steps.insert(-1, {"Id": "commitCount", "Type": "Call", "Endpoint": "Server", "Capability": "GetRuntimeActorProperty",
                          "Arguments": {"ActorName": actor("Server"), "PropertyPaths": ["CommitCount"]}})
    for role in ("Server", "Owner"):
        cleanup.append(call(f"stop{role}", role, "StopActivationCapture", CaptureId={"Ref": f"/Steps/capture{role}/Payload/CaptureId"}))
    return case


def free_port(kind=socket.SOCK_STREAM):
    with socket.socket(socket.AF_INET, kind) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ue-root", required=True, type=Path)
    parser.add_argument("--uproject", type=Path, default=PROJECT / "Nexus.uproject")
    parser.add_argument("--repeat", type=int, default=10)
    parser.add_argument("--output", type=Path, default=PROJECT / "Saved/GasRetest")
    parser.add_argument("--quickstart", action="store_true", help="One round: prediction rejection, condition restore, successful activation; generates index.html")
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    if args.quickstart:
        args.repeat = 1
    binary = args.ue_root / "Engine/Binaries/Win64/UnrealEditor.exe"
    if not binary.exists():
        parser.error("Win64 UnrealEditor.exe not found")
    args.output.mkdir(parents=True, exist_ok=True)
    processes, logs, endpoints, reports = [], [], {}, []
    game_port = free_port(socket.SOCK_DGRAM)
    try:
        for role in ("Server", "Owner", "Observer"):
            port, ws_port = free_port(), free_port()
            endpoints[role] = {"Url": f"http://127.0.0.1:{port}/stream", "bAuthority": role == "Server"}
            travel = "/Engine/Maps/Entry?game=/Script/Nexus.NexusDiagnosticGameMode" if role == "Server" else f"127.0.0.1:{game_port}"
            cmd = [str(binary), str(args.uproject.resolve()), travel, "-server" if role == "Server" else "-game",
                   f"-port={game_port}", "-EnableNexusMcp", f"-NexusMcpPort={port}", f"-NexusWsPort={ws_port}",
                   "-unattended", "-nullrhi", "-nosound", "-nop4", "-nomessaging", "-nosplash", "-stdout", "-FullStdOutLogOutput"]
            log = (args.output / f"{role}.log").open("w", encoding="utf-8")
            logs.append(log)
            processes.append(subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
            deadline = time.monotonic() + 120
            while True:
                if processes[-1].poll() is not None:
                    raise RunError(f"{role} exited; inspect {role}.log")
                try:
                    client = Client(endpoints[role]); client.close(); break
                except RunError:
                    if time.monotonic() > deadline:
                        raise RunError(f"{role} MCP startup timed out")
                    time.sleep(0.5)
        # 等待两个客户端完成登录与 ActorInfo 初始化。
        for attempt in range(100):
            probe = Runner(build_case(endpoints, "Success"))
            report = probe.run(preflight=True)
            report["Name"] = "接入预检"
            if report["ExitCode"] == 0:
                write_reports(report, args.output / "startup")
                reports.append(("startup", report))
                break
            time.sleep(0.2)
        else:
            write_reports(report, args.output / "startup")
            raise RunError("Network actor binding did not become ready")
        scenarios = QUICKSTART_SCENARIOS if args.quickstart else ("NotGranted", "MissingRequired", "Blocked", "Cost", "Cooldown", "PredictionRejected", "Success", "ServerOnly")
        for iteration in range(args.repeat):
            for scenario in scenarios:
                case = build_case(endpoints, scenario, SERVER_ABILITY if scenario == "ServerOnly" else ABILITY)
                directory = args.output / f"{iteration + 1:02d}-{scenario}"
                directory.mkdir(parents=True, exist_ok=True)
                (directory / "case.json").write_text(json.dumps(case, indent=2), encoding="utf-8")
                report = Runner(case).run()
                write_reports(report, directory)
                reports.append((directory.name, report))
                print(f"round={iteration + 1} {scenario}: exit={report['ExitCode']}", flush=True)
                if report["ExitCode"]:
                    return report["ExitCode"]
        return 0
    except RunError as exc:
        print(str(exc), file=sys.stderr)
        report = {"SchemaVersion": 1, "Name": "Startup", "Mode": "Preflight", "ExitCode": 2,
                  "Records": [{"Id": "Startup", "Stage": "Preflight", "Status": "Error", "Message": str(exc)}]}
        write_reports(report, args.output / "startup")
        reports = [(name, item) for name, item in reports if name != "startup"] + [("startup", report)]
        return 2
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
        for log in logs:
            log.close()
        if reports:
            write_index(reports, args.output)
            print(f"Report: {args.output / 'index.html'}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
