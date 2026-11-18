#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright byteyang. All Rights Reserved.
"""One-shot pytest wrapper for NexusLink MCP E2E suite.

Modes:

  py Script/run_e2e.py              # default: headless UEEditor-Cmd (CI / daily)
  py Script/run_e2e.py --gui|--full # full suite: GUI UnrealEditor.exe (PIE/Lua/viewport)
  py Script/run_e2e.py --ue-url …   # attach to a running Editor

Policy (see Tests/README.md):
- New features → add pytest in Tests/test_*.py; prefer headless-capable cases.
- Mark l4_runtime / lua / requires_gui when CLI cannot cover; verify with --gui.
- Full regression always uses --gui or --full.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
NEXUS_UNREAL_DIR = SCRIPT_DIR.parent
TESTS_DIR = NEXUS_UNREAL_DIR / "Tests"
LOG_DIR = NEXUS_UNREAL_DIR / "Saved" / "Logs"

def _ensure_deps() -> None:
    try:
        import pytest  # noqa: F401
        import httpx   # noqa: F401
        import psutil  # noqa: F401
    except ImportError:
        req = TESTS_DIR / "requirements.txt"
        print(f"[info] installing pytest deps from {req}", flush=True)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(req)]
        )


_HOST_UPROJECT = NEXUS_UNREAL_DIR / "Nexus.uproject"
_VER_LABEL_RE = re.compile(r"^UE_?(\d+)\.(\d+)$", re.IGNORECASE)


def _uproject_engine_association(uproject: Path) -> Optional[str]:
    try:
        with open(uproject, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:  # noqa: BLE001
        return None
    label = str(data.get("EngineAssociation") or "").strip()
    # Accept "4.26", "UE_4.26", "5.4", etc.; strip any UE_ prefix here.
    if not label:
        return None
    label = label.replace("UE_", "").replace("UE", "")
    m = re.match(r"^(\d+)\.(\d+)$", label)
    return f"UE_{m.group(1)}.{m.group(2)}" if m else None


def _autodetect_ue_root(preferred_label: Optional[str], *, headless: bool) -> Optional[Tuple[str, str]]:
    """Return (version_label, install_path) for the best UE candidate.

    Selection order:
      1. UE matching `preferred_label` (e.g. the uproject EngineAssociation).
      2. Newest installed UE with an editor binary usable by the launcher.
    """
    from _framework.ue_launcher import resolve_editor_exe

    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from engine_discovery import discover_engines_auto  # type: ignore
    except Exception as e:  # noqa: BLE001
        print(f"[warn] engine auto-discovery failed to import: {e}",
              file=sys.stderr, flush=True)
        return None
    try:
        engines = discover_engines_auto()
    except Exception as e:  # noqa: BLE001
        print(f"[warn] engine auto-discovery raised: {e}",
              file=sys.stderr, flush=True)
        return None
    preferred = [entry for entry in engines if entry["version"].casefold() == (preferred_label or "").casefold()]
    candidates = preferred + [entry for entry in reversed(engines) if entry not in preferred]
    for entry in candidates:
        try:
            resolve_editor_exe(Path(entry["path"]), headless=headless)
        except FileNotFoundError:
            continue
        return entry["version"], entry["path"]
    return None


def _resolve_connection(args: argparse.Namespace, *, headless: bool = True) -> Tuple[List[str], str]:
    """Resolve how the pytest run should reach UE. Returns (extra_pytest_args,
    human_readable_mode_label)."""
    # 延迟加载 pytest 宿主依赖，保证全新环境也能运行 --help。
    sys.path.insert(0, str(TESTS_DIR))
    from _framework.ue_launcher import matching_editor_urls

    project = Path(args.uproject or _HOST_UPROJECT).resolve()
    if not project.is_file() or project.suffix.casefold() != ".uproject":
        raise ValueError(f"Expected an existing .uproject: {project}")
    project_args = ["--uproject", str(project)]
    if args.ue_url:
        matches = matching_editor_urls(project, args.ue_url)
        if len(matches) != 1:
            raise ValueError(f"Cannot verify local Editor at {args.ue_url} for {project}")
        return ["--ue-url", matches[0], *project_args], f"explicit --ue-url {matches[0]}"

    # 2. Explicit --ue-root wins (force launch a specific UE version).
    if args.ue_root:
        return ["--ue-root", args.ue_root, *project_args], f"explicit --ue-root {args.ue_root}"

    # 3. Auto mode: probe for an existing Editor first.
    live = matching_editor_urls(project)
    if len(live) > 1:
        raise ValueError(f"Multiple Editors match {project}; select one with --ue-url: {', '.join(live)}")
    if live:
        return ["--ue-url", live[0], *project_args], f"auto: reusing Editor for {project} at {live[0]}"

    # 4. Auto-launch fallback. Pass --no-launch to skip and surface a hint
    #    instead (useful for CI that wants a hard fail when the Editor is
    #    missing rather than a 5-10 minute UBT build + cold start).
    if args.no_launch:
        return [], f"No verified local Editor for {project} (--no-launch set)"

    preferred = _uproject_engine_association(project)
    found = _autodetect_ue_root(preferred, headless=headless)
    if not found:
        return [], f"No verified local Editor for {project} and no installed UE detected"
    ver, path = found
    matched_note = (
        f" (matched uproject EngineAssociation={preferred})"
        if preferred and ver.lower() == preferred.lower()
        else f" (preferred {preferred}, using latest instead)"
        if preferred else ""
    )
    return ["--ue-root", path, *project_args], f"auto: launching {ver} from {path}{matched_note}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run NexusLink pytest E2E suite",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--ue-url", default=os.environ.get("NEXUS_UE_URL"),
        help="MCP stream URL of a running UE (skips auto-probe).",
    )
    parser.add_argument(
        "--ue-root", default=os.environ.get("NEXUS_UE_ROOT"),
        help="UE engine install root (skips auto-probe; force-launch this version).",
    )
    parser.add_argument(
        "--no-launch", action="store_true",
        help="Disable auto-launch fallback. When set and no live Editor is "
             "found, the runner exits with a friendly hint instead of "
             "spawning UEEditor-Cmd.",
    )
    parser.add_argument(
        "--uproject", default=os.environ.get("NEXUS_UE_UPROJECT"),
        help="Host .uproject (auto-detected under nexus-unreal/ if omitted).",
    )
    parser.add_argument(
        "--no-pie", action="store_true",
        help="Skip tests marked l4_runtime (requires PIE).",
    )
    parser.add_argument(
        "--no-lua", action="store_true",
        help="Skip tests marked lua.",
    )
    parser.add_argument(
        "-k", "--keyword", default=None,
        help="pytest -k expression (e.g. 'blueprint').",
    )
    parser.add_argument(
        "-m", "--marker", default=None,
        help="pytest -m expression (overrides --no-pie/--no-lua if both set).",
    )
    parser.add_argument(
        "--keep-artifacts", action="store_true",
        help="Keep /Game/_McpTest/<ts>/ and leftover /Game/_NexusTest assets after the run.",
    )
    parser.add_argument(
        "--gui", action="store_true",
        help="全量回归：拉起 UnrealEditor.exe（含 PIE / Lua / requires_gui）。",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="同 --gui（全量 GUI 回归别名）。",
    )
    parser.add_argument(
        "--junitxml", default=None,
        help="Write a JUnit XML report; defaults to Saved/Logs/TestReport.xml.",
    )
    args, forwarded = parser.parse_known_args()
    gui = args.gui or args.full

    _ensure_deps()
    coverage_audit = NEXUS_UNREAL_DIR / "Script/audit_e2e_coverage.py"
    print(f"[audit] {coverage_audit}", flush=True)
    audit_rc = subprocess.call([sys.executable, str(coverage_audit)])
    if audit_rc != 0:
        return audit_rc
    plugin_scripts = NEXUS_UNREAL_DIR / "Plugins/NexusLink/scripts"
    for name in ("audit_capability_naming.py", "audit_capability_params.py"):
        audit_script = plugin_scripts / name
        if not audit_script.is_file():
            continue
        print(f"[audit] {audit_script}", flush=True)
        audit_rc = subprocess.call([sys.executable, str(audit_script)])
        if audit_rc != 0:
            return audit_rc

    try:
        conn_args, mode = _resolve_connection(args, headless=not gui)
    except (ValueError, RuntimeError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    if not conn_args:
        print(f"[error] {mode}", file=sys.stderr)
        return 2
    print(f"[mode] {mode}", flush=True)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    junit = args.junitxml or str(LOG_DIR / "TestReport.xml")

    cmd: list[str] = [sys.executable, "-m", "pytest", str(TESTS_DIR),
                      f"--junitxml={junit}"]

    marker_parts: list[str] = []
    if args.no_pie:
        marker_parts.append("not l4_runtime")
    if args.no_lua:
        marker_parts.append("not lua")
    if args.marker:
        marker_parts = [args.marker]
    if marker_parts:
        cmd.extend(["-m", " and ".join(marker_parts)])

    if args.keyword:
        cmd.extend(["-k", args.keyword])

    cmd.extend(conn_args)
    if args.keep_artifacts:
        cmd.append("--keep-artifacts")
    if gui:
        cmd.append("--gui")
    elif "--ue-root" in conn_args:
        cmd.append("--headless")

    cmd.extend(forwarded)

    print(f"[run] {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd, cwd=str(NEXUS_UNREAL_DIR))


if __name__ == "__main__":
    sys.exit(main())
