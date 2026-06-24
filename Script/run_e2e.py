#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright byteyang. All Rights Reserved.
"""One-shot pytest wrapper for NexusLink MCP E2E suite.

Typical calls (pick one; zero args = full auto):

    # Auto mode (default) — probe localhost 45000..45009 for a live Editor
    # and reuse it. If none is running, auto-launch the UE version that
    # matches Nexus.uproject's EngineAssociation and shut it down on exit.
    python nexus-unreal/Script/run_e2e.py

    # Dev mode — connect to a specific already-running UE Editor
    python nexus-unreal/Script/run_e2e.py --ue-url http://127.0.0.1:45000/stream

    # Force a specific UE install root (overrides auto-detection)
    python nexus-unreal/Script/run_e2e.py --ue-root "C:/Program Files/Epic Games/UE_5.4"

    # Disable auto-launch fallback (only reuse a live Editor, or exit)
    python nexus-unreal/Script/run_e2e.py --no-launch

    # Skip PIE-dependent cases (no live game session)
    python nexus-unreal/Script/run_e2e.py --no-pie

All extra args after a bare `--` are forwarded verbatim to pytest.
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

# NexusLink auto-picks the first free port in this range when the Editor boots.
_PROBE_PORT_RANGE = range(45000, 45010)
_PROBE_TIMEOUT_SEC = 2.0


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


def _probe_live_editor() -> Optional[str]:
    """Return the first http://127.0.0.1:<port>/stream that responds to MCP
    `initialize`, or None when no live NexusLink Editor is reachable."""
    import httpx  # imported here so --help still works without deps
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "run_e2e.probe", "version": "0"},
        },
    }
    for port in _PROBE_PORT_RANGE:
        url = f"http://127.0.0.1:{port}/stream"
        try:
            with httpx.Client(timeout=_PROBE_TIMEOUT_SEC) as c:
                r = c.post(url, json=payload)
            if r.status_code == 200 and "serverInfo" in r.text:
                return url
        except Exception:  # noqa: BLE001
            continue
    return None


_HOST_UPROJECT = NEXUS_UNREAL_DIR / "Nexus.uproject"
_VER_LABEL_RE = re.compile(r"^UE_?(\d+)\.(\d+)$", re.IGNORECASE)


def _has_editor_cmd(ue_root: Path) -> bool:
    candidates = [
        ue_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe",
        ue_root / "Engine" / "Binaries" / "Win64" / "UE4Editor-Cmd.exe",
        ue_root / "Engine" / "Binaries" / "Mac" / "UnrealEditor-Cmd",
        ue_root / "Engine" / "Binaries" / "Mac" / "UE4Editor-Cmd",
        ue_root / "Engine" / "Binaries" / "Linux" / "UnrealEditor-Cmd",
        ue_root / "Engine" / "Binaries" / "Linux" / "UE4Editor-Cmd",
    ]
    return any(p.exists() for p in candidates)


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


def _autodetect_ue_root(preferred_label: Optional[str]) -> Optional[Tuple[str, str]]:
    """Return (version_label, install_path) for the best UE candidate.

    Selection order:
      1. UE matching `preferred_label` (e.g. the uproject EngineAssociation).
      2. Newest installed UE with a usable Editor-Cmd binary.
    """
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
    if not engines:
        return None

    if preferred_label:
        for entry in engines:
            if entry["version"].lower() == preferred_label.lower() \
                    and _has_editor_cmd(Path(entry["path"])):
                return entry["version"], entry["path"]

    # `discover_engines_auto` already sorts ascending by (major, minor);
    # pick the highest version that has a usable Editor-Cmd binary.
    for entry in reversed(engines):
        if _has_editor_cmd(Path(entry["path"])):
            return entry["version"], entry["path"]
    return None


def _resolve_connection(args: argparse.Namespace) -> Tuple[List[str], str]:
    """Resolve how the pytest run should reach UE. Returns (extra_pytest_args,
    human_readable_mode_label)."""
    # 1. Explicit --ue-url wins.
    if args.ue_url:
        return ["--ue-url", args.ue_url], f"explicit --ue-url {args.ue_url}"

    # 2. Explicit --ue-root wins (force launch a specific UE version).
    if args.ue_root:
        out = ["--ue-root", args.ue_root]
        if args.uproject:
            out.extend(["--uproject", args.uproject])
        return out, f"explicit --ue-root {args.ue_root}"

    # 3. Auto mode: probe for an existing Editor first.
    live = _probe_live_editor()
    if live:
        return ["--ue-url", live], f"auto: reusing live Editor at {live}"

    # 4. Auto-launch fallback. Pass --no-launch to skip and surface a hint
    #    instead (useful for CI that wants a hard fail when the Editor is
    #    missing rather than a 5-10 minute UBT build + cold start).
    if args.no_launch:
        return [], "no live Editor on 127.0.0.1:45000..45009 (--no-launch set)"

    uproject_hint = Path(args.uproject) if args.uproject else _HOST_UPROJECT
    preferred = _uproject_engine_association(uproject_hint) if uproject_hint.exists() else None
    found = _autodetect_ue_root(preferred)
    if not found:
        return [], "no live Editor and no installed UE detected"
    ver, path = found
    matched_note = (
        f" (matched uproject EngineAssociation={preferred})"
        if preferred and ver.lower() == preferred.lower()
        else f" (preferred {preferred}, using latest instead)"
        if preferred else ""
    )
    out = ["--ue-root", path]
    if args.uproject:
        out.extend(["--uproject", args.uproject])
    return out, f"auto: launching {ver} from {path}{matched_note}"


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
        help="Keep /Game/_McpTest/<ts>/ assets after the run.",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Auto-launch UEEditor-Cmd with -nullrhi (no window). Default is "
             "GUI mode so you can watch pytest drive the editor.",
    )
    parser.add_argument(
        "--junitxml", default=None,
        help="Write a JUnit XML report; defaults to Saved/Logs/TestReport.xml.",
    )
    args, forwarded = parser.parse_known_args()

    _ensure_deps()

    audit_script = SCRIPT_DIR / "audit_capability_naming.py"
    if audit_script.is_file():
        print(f"[audit] {audit_script}", flush=True)
        audit_rc = subprocess.call([sys.executable, str(audit_script)])
        if audit_rc != 0:
            return audit_rc

    conn_args, mode = _resolve_connection(args)
    if not conn_args:
        eng = _uproject_engine_association(_HOST_UPROJECT) if _HOST_UPROJECT.exists() else None
        hint = f" (EngineAssociation={eng})" if eng else ""
        print(
            "[error] no live NexusLink Editor detected on "
            "127.0.0.1:45000..45009\n"
            "        and --no-launch was supplied (or no UE install found"
            + hint + ").\n"
            "        Either drop --no-launch to let the runner UBT-build "
            "and headless-launch,\n"
            "        or open Nexus.uproject manually and re-run.",
            file=sys.stderr,
        )
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
    if args.headless:
        cmd.append("--headless")

    cmd.extend(forwarded)

    print(f"[run] {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd, cwd=str(NEXUS_UNREAL_DIR))


if __name__ == "__main__":
    sys.exit(main())
