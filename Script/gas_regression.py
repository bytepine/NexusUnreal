#!/usr/bin/env python3
"""运行固定联机用例，核对已审查基线，并归档完整证据。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import zipfile

from gas_network_retest import PROJECT, QUICKSTART_SCENARIOS, build_case
from gas_retest.compare import compare_reports, load_report, write_comparison
from gas_retest.report import collect_evidence, document, text
from gas_retest.runner import RunError, case_signature, write_reports


def load_baselines(directory):
    endpoints = {role: {"Url": f"http://127.0.0.1:{45010 + index}/stream", "bAuthority": role == "Server"}
                 for index, role in enumerate(("Server", "Owner", "Observer"))}
    reports = {}
    for scenario in QUICKSTART_SCENARIOS:
        report = load_report(Path(directory) / (scenario + ".json"))
        if (report["Name"] != scenario or report.get("Mode", "Replay") != "Replay" or report["ExitCode"]
                or collect_evidence(report)[2] or report.get("CaseSignature") != case_signature(build_case(endpoints, scenario))):
            raise RunError(f"Baseline must be a passed, signed replay of the fixed case: {scenario}")
        reports[scenario] = report
    return reports


def archive_reports(output):
    files = sorted(path for path in output.rglob("*") if path.is_file())
    with zipfile.ZipFile(output / "reports.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(output).as_posix())


def write_summary(records, output):
    code = 2 if any(record["Status"] == "Error" for record in records) else int(any(record["Status"] == "Failed" for record in records))
    report = {"SchemaVersion": 1, "Name": "GAS fixed regression", "Mode": "Regression", "ExitCode": code, "Records": records}
    write_reports(report, output)
    body = '<div class="eyebrow">NEXUSLINK · GAS REGRESSION</div><h1>固定用例自动回归</h1>'
    body += f'<p><span class="pill {"Passed" if code == 0 else "Error"}">{"全部通过" if code == 0 else "存在失败或运行错误"}</span></p>'
    body += '<p>逐项核对已保存基线与本次结果。步骤检查与实际技能结果分别展示；事件变化本身不自动判定回归。</p><div class="grid">'
    for record in records:
        body += f'<article class="panel"><span class="pill {text(record["Status"])}">{text(record["Status"])}</span><h2>{text(record["Id"])}</h2><p>{text(record.get("Message", ""))}</p>'
        for label, key in (("本次完整报告", "Report"), ("基线对比", "Comparison")):
            link = record.get("Result", {}).get(key)
            if link:
                body += f'<p><a href="{text(link)}">{label} →</a></p>'
        if record.get("Result", {}).get("bEvidenceChanged"):
            body += '<p class="muted">技能证据有变化，请查看各端事件对比。</p>'
        body += '</article>'
    body += '</div><p><a href="results.json">JSON 汇总</a> · <a href="junit.xml">JUnit 门禁</a> · 完整归档：<code>reports.zip</code></p>'
    if (output / "run.log").exists():
        body += '<p><a href="run.log">执行日志</a></p>'
    if (output / "current/index.html").exists():
        body += '<p><a href="current/index.html">联机运行与接入预检报告</a></p>'
    html = document("GAS 自动回归", body)
    (output / "index.html").write_text(html, encoding="utf-8")
    (output / "report.html").write_text(html, encoding="utf-8")
    archive_reports(output)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ue-root", required=True, type=Path)
    parser.add_argument("--uproject", type=Path, default=PROJECT / "Nexus.uproject")
    parser.add_argument("--baselines", type=Path, default=PROJECT / "Tests/GasRetest/baselines")
    parser.add_argument("--output", type=Path, default=PROJECT / "Saved/GasRegression" / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f"))
    args = parser.parse_args(argv)
    output = args.output.resolve()
    try:
        # 不复用目录，避免旧结果被当成本次通过；在任何 UE 写入前校验全部基线。
        output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print(f"Cannot create a new regression output directory ({type(exc).__name__})", file=sys.stderr)
        return 2
    records = []
    try:
        baselines = load_baselines(args.baselines)
        command = [sys.executable, str(Path(__file__).with_name("gas_network_retest.py")),
                   "--ue-root", str(args.ue_root.resolve()), "--uproject", str(args.uproject.resolve()),
                   "--quickstart", "--output", str(output / "current")]
        with (output / "run.log").open("w", encoding="utf-8") as log:
            completed = subprocess.run(command, cwd=PROJECT, stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for scenario in QUICKSTART_SCENARIOS:
            record = {"Id": scenario, "Stage": "Regression", "Status": "Passed", "Result": {}}
            records.append(record)
            try:
                current_path = output / "current" / ("01-" + scenario) / "results.json"
                if not current_path.is_file():
                    raise RunError(f"Fixed case was not completed (replay exit={completed.returncode}): {scenario}; inspect run.log")
                current = load_report(current_path)
                record["Result"]["Report"] = f"current/01-{scenario}/report.html"
                comparison = compare_reports(baselines[scenario], current)
                if not comparison["bCaseVerified"]:
                    raise RunError("Automatic regression requires signed case definitions on both sides")
                write_comparison(comparison, baselines[scenario], current, output / "comparisons" / scenario)
                record["Result"].update(Comparison=f"comparisons/{scenario}/comparison.html",
                                        Counts=comparison["Counts"], bEvidenceChanged=comparison["bEvidenceChanged"])
                if current["ExitCode"] == 2:
                    record.update(Status="Error", Message="Replay runtime error; original evidence and comparison retained")
                elif comparison["ExitCode"]:
                    record.update(Status="Failed", Message="Case assertions failed or baseline checks are missing")
            except (OSError, ValueError, KeyError, TypeError, RunError) as exc:
                record.update(Status="Error", Message=str(exc) if isinstance(exc, RunError) else type(exc).__name__)
        if completed.returncode and all(record["Status"] == "Passed" for record in records):
            records.append({"Id": "ReplayProcess", "Status": "Error", "Message": f"Replay process failed: exit={completed.returncode}"})
    except (OSError, ValueError, KeyError, TypeError, RunError) as exc:
        records.append({"Id": "Configuration", "Status": "Error", "Message": str(exc) if isinstance(exc, RunError) else type(exc).__name__})
    try:
        code = write_summary(records, output)
    except OSError as exc:
        print(f"Cannot archive regression reports ({type(exc).__name__})", file=sys.stderr)
        return 2
    print(f"GAS regression: exit={code}; report={output / 'index.html'}; archive={output / 'reports.zip'}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
