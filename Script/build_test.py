#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright byteyang. All Rights Reserved.
"""
build_test.py -- NexusLink cross-version build test

Runs BuildPlugin against all installed UE versions:
  Phase 1 — DevelopmentEditor (WITH_EDITOR=1, default uplugin Type: Editor)
  Phase 2 — UnrealGame Development (WITH_EDITOR=0, temp copy Type: Runtime)

Writes error logs to Saved/Logs/Build.Log (+ Build.Game.Log for phase 2).

Usage:
    python build_test.py [--ue-root <engine_root>] [--editor-only | --game-only]

Args:
    --ue-root   Optional. Root directory containing UE_X.Y sub-dirs.
                Auto-detected when omitted:
                  Windows/macOS : reads Epic Launcher LauncherInstalled.dat
                  Linux         : reads LauncherInstalled.dat (if present) +
                                  scans ~/UnrealEngine, /opt/UnrealEngine etc.
"""

import argparse
import atexit
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
NEXUS_UNREAL_DIR = SCRIPT_DIR.parent
PLUGIN_PATH = NEXUS_UNREAL_DIR / "Plugins" / "Developer" / "NexusLink" / "NexusLink.uplugin"
LOG_DIR = NEXUS_UNREAL_DIR / "Saved" / "Logs"
LOG_FILE = LOG_DIR / "Build.Log"
LOG_FILE_GAME = LOG_DIR / "Build.Game.Log"
TEMP_BASE = Path(tempfile.gettempdir()) / "NexusBuildTest"
_TEMP_GAME_BASE = TEMP_BASE / "GameTarget"
_EDITOR_TYPE = '"Type": "Editor"'
_RUNTIME_TYPE = '"Type": "Runtime"'
_GAME_TARGET_RE = re.compile(r"UnrealGame", re.IGNORECASE)

_SYSTEM = platform.system()  # "Windows" | "Darwin" | "Linux"

# UE 版本中 UBT 默认查找 VS2017 的版本集——这些版本在仅装 VS2019/VS2022 的
# 机器上会报 `ERROR: Visual Studio 2017 must be installed`。未显式传 --vs 时
# 自动回落到 VS2019（4.26/4.27 官方均支持 VS2019）。
_VS2019_FALLBACK_VERSIONS = frozenset({"UE_4.26", "UE_4.27"})

_PLATFORM_TARGET = {
    "Windows": "Win64",
    "Darwin": "Mac",
    "Linux": "Linux",
}

# 引擎发现逻辑统一由 engine_discovery.py 提供
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_discovery import (  # noqa: E402
    discover_engines_auto,
    discover_engines_from_root,
)

# ---------------------------------------------------------------------------
# Process registry & cleanup
# ---------------------------------------------------------------------------

_active_procs: List[subprocess.Popen] = []
_procs_lock = Lock()


def _kill_proc_tree(proc: subprocess.Popen) -> None:
    pid = proc.pid
    if pid is None:
        return
    try:
        if _SYSTEM == "Windows":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        pass


def _cleanup_all() -> None:
    with _procs_lock:
        procs = list(_active_procs)
    for p in procs:
        if p.poll() is None:
            _kill_proc_tree(p)


def _signal_handler(sig: int, frame) -> None:
    _cleanup_all()
    sys.exit(1)


atexit.register(_cleanup_all)
signal.signal(signal.SIGINT, _signal_handler)
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, _signal_handler)


_ERROR_INCLUDE = re.compile(r"\berror\b", re.IGNORECASE)
_ERROR_EXCLUDE = re.compile(
    r"(^\s*0\s+error|error\(s\)\s*=\s*0|errors\s*:\s*0|^\s*Running\s|\[Adaptive Build\])",
    re.IGNORECASE,
)
_WARN_INCLUDE = re.compile(r"\bwarning\b", re.IGNORECASE)
_WARN_EXCLUDE = re.compile(
    r"(^\s*0\s+warning|warning\(s\)\s*=\s*0|warnings\s*:\s*0|^\s*Running\s)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Build execution
# ---------------------------------------------------------------------------

def _decode_output(raw: bytes) -> str:
    raw = raw.rstrip(b"\r")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk", errors="replace")


def _run_uat_build(engine_path: str, plugin_path: str, package_out: str,
                   vs_version: Optional[str] = None) -> Tuple[int, List[str]]:
    """
    Run RunUAT BuildPlugin for the given engine.

    :param vs_version: optional MSVC toolchain selector, one of "2017"/"2019"/"2022";
        appended as `-VS<ver>` to BuildPlugin. Needed by UE 4.26 / 4.27 on hosts
        that only ship VS2019/VS2022 (both versions' UBT default查找 VS2017).
    :return: (exit_code, output_lines); exit_code=-1 means RunUAT not found (SKIP).
    """
    uat_name = "RunUAT.bat" if _SYSTEM == "Windows" else "RunUAT.sh"
    uat_path = os.path.join(engine_path, "Engine", "Build", "BatchFiles", uat_name)

    if not os.path.isfile(uat_path):
        return (-1, [f"RunUAT not found: {uat_path}"])

    target = _PLATFORM_TARGET.get(_SYSTEM, "Linux")
    uat_args = [
        "BuildPlugin",
        f"-Plugin={plugin_path}",
        f"-Package={package_out}",
        f"-TargetPlatforms={target}",
    ]
    if vs_version:
        uat_args.append(f"-VS{vs_version}")

    env = os.environ.copy()
    if _SYSTEM == "Windows":
        env["VSLANG"] = "1033"
        cmd = ["cmd", "/c", uat_path] + uat_args
        kwargs: dict = {"shell": False}
    else:
        os.chmod(uat_path, 0o755)
        cmd = ["bash", uat_path] + uat_args
        kwargs = {"shell": False, "start_new_session": True}

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        **kwargs,
    )
    with _procs_lock:
        _active_procs.append(proc)
    try:
        stdout, _ = proc.communicate()
    finally:
        with _procs_lock:
            try:
                _active_procs.remove(proc)
            except ValueError:
                pass

    output_lines = [_decode_output(ln) for ln in stdout.split(b"\n")]
    return (proc.returncode, output_lines)


def _extract_errors(lines: List[str]) -> List[str]:
    return [
        ln for ln in lines
        if _ERROR_INCLUDE.search(ln) and not _ERROR_EXCLUDE.search(ln)
    ]


def _extract_warnings(lines: List[str]) -> List[str]:
    return [
        ln for ln in lines
        if _WARN_INCLUDE.search(ln) and not _WARN_EXCLUDE.search(ln)
    ]


def _prepare_runtime_plugin_copy(ver: str) -> Tuple[str, str]:
    """Copy NexusLink to temp and patch module Type Editor→Runtime."""
    src_root = PLUGIN_PATH.parent
    work = _TEMP_GAME_BASE / ver
    plugin_copy = work / "PluginSrc" / "NexusLink"
    package_out = work / "Package"

    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    shutil.copytree(src_root, plugin_copy)
    uplugin = plugin_copy / "NexusLink.uplugin"
    content = uplugin.read_text(encoding="utf-8")
    if _EDITOR_TYPE not in content:
        raise RuntimeError(f"NexusLink module {_EDITOR_TYPE} not found in {uplugin}")
    uplugin.write_text(content.replace(_EDITOR_TYPE, _RUNTIME_TYPE, 1), encoding="utf-8")
    return str(uplugin), str(package_out)


def _game_build_lines(lines: List[str]) -> List[str]:
    game_lines = [ln for ln in lines if _GAME_TARGET_RE.search(ln)]
    return game_lines if game_lines else lines


def _format_result_block(r: Dict, lines_out: List[str], sep: str) -> Tuple[int, int, int]:
    """Append one version block; return (pass_delta, fail_delta, warn_delta)."""
    ver, eng_path = r["ver"], r["eng_path"]
    exit_code = r["exit_code"]
    error_lines, warn_lines = r["error_lines"], r["warn_lines"]

    lines_out.append(sep)
    lines_out.append(f"[{ver}]  {eng_path}")

    if exit_code == -1:
        lines_out.append(f"STATUS : SKIP  ({r['output'][0]})")
        return 0, 0, 0
    if exit_code == 0:
        lines_out.append(
            f"STATUS : PASS  (warnings={len(warn_lines)})" if warn_lines else "STATUS : PASS"
        )
        if warn_lines:
            lines_out.append(f"--- Warnings ({len(warn_lines)} lines) ---")
            lines_out.extend(f"  {ln}" for ln in warn_lines)
        return 1, 0, len(warn_lines)

    lines_out.append(f"STATUS : FAIL  (exit={exit_code})")
    if error_lines:
        lines_out.append(f"--- Errors ({len(error_lines)} lines) ---")
        lines_out.extend(f"  {ln}" for ln in error_lines)
    else:
        lines_out.append("--- No 'error' keyword matched, last 30 lines ---")
        lines_out.extend(f"  {ln}" for ln in r["output"][-30:])
    if warn_lines:
        lines_out.append(f"--- Warnings ({len(warn_lines)} lines) ---")
        lines_out.extend(f"  {ln}" for ln in warn_lines)
    return 0, 1, len(warn_lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _update_status_line(text: str, line_idx: int, total: int,
                        print_lock: Lock, is_tty: bool) -> None:
    with print_lock:
        if is_tty:
            lines_up = total - line_idx
            sys.stdout.write(f"\033[{lines_up}A\r\033[2K{text}\033[{lines_up}B\r")
            sys.stdout.flush()
        else:
            print(text, flush=True)


def _build_one(engine: dict, plugin_path: str, line_idx: int, total: int,
               print_lock: Lock, is_tty: bool,
               vs_version: Optional[str] = None) -> Dict:
    ver = engine["version"]
    eng_path = engine["path"]
    package_out = str(TEMP_BASE / ver)

    _update_status_line(f"[{ver}] Building...", line_idx, total, print_lock, is_tty)

    if os.path.isdir(package_out):
        shutil.rmtree(package_out, ignore_errors=True)

    # UE 4.26 / 4.27 的 UBT 默认查找 VS2017，没装时直接报 "Visual Studio 2017 must be installed"。
    # 现代机器通常只有 VS2019/VS2022，两版官方均支持 VS2019，因此当用户未显式
    # 传 --vs 时对这些版本自动回落到 VS2019；其它版本保持 UBT 默认逻辑不变。
    effective_vs = vs_version or ("2019" if ver in _VS2019_FALLBACK_VERSIONS else None)

    exit_code, output = _run_uat_build(eng_path, plugin_path, package_out, effective_vs)

    error_lines = _extract_errors(output) if exit_code not in (-1, 0) else []
    warn_lines = _extract_warnings(output) if exit_code != -1 else []

    if exit_code == -1:
        status = f"[{ver}] SKIP"
    elif exit_code == 0:
        status = f"[{ver}] PASS{f' ({len(warn_lines)} warnings)' if warn_lines else ''}"
    else:
        status = f"[{ver}] FAIL (exit={exit_code})"

    _update_status_line(status, line_idx, total, print_lock, is_tty)

    return {
        "ver": ver,
        "eng_path": eng_path,
        "exit_code": exit_code,
        "output": output,
        "error_lines": error_lines,
        "warn_lines": warn_lines,
    }


def _build_one_game(engine: dict, line_idx: int, total: int,
                    print_lock: Lock, is_tty: bool,
                    vs_version: Optional[str] = None) -> Dict:
    ver = engine["version"]
    eng_path = engine["path"]

    _update_status_line(f"[{ver}] Game: preparing Runtime copy...", line_idx, total, print_lock, is_tty)

    try:
        plugin_path, package_out = _prepare_runtime_plugin_copy(ver)
    except Exception as exc:
        _update_status_line(f"[{ver}] Game: FAIL (prep)", line_idx, total, print_lock, is_tty)
        return {
            "ver": ver,
            "eng_path": eng_path,
            "exit_code": 1,
            "output": [str(exc)],
            "error_lines": [str(exc)],
            "warn_lines": [],
        }

    _update_status_line(f"[{ver}] Game: building UnrealGame...", line_idx, total, print_lock, is_tty)

    effective_vs = vs_version or ("2019" if ver in _VS2019_FALLBACK_VERSIONS else None)
    exit_code, output = _run_uat_build(eng_path, plugin_path, package_out, effective_vs)

    scoped = _game_build_lines(output)
    error_lines = _extract_errors(scoped) if exit_code not in (-1, 0) else []
    if exit_code not in (-1, 0) and not error_lines:
        error_lines = _extract_errors(output)
    warn_lines = _extract_warnings(scoped) if exit_code != -1 else []
    if exit_code != -1 and not warn_lines:
        warn_lines = _extract_warnings(output)

    if exit_code == -1:
        status = f"[{ver}] Game: SKIP"
    elif exit_code == 0:
        status = f"[{ver}] Game: PASS{f' ({len(warn_lines)} warnings)' if warn_lines else ''}"
    else:
        status = f"[{ver}] Game: FAIL (exit={exit_code})"

    _update_status_line(status, line_idx, total, print_lock, is_tty)

    return {
        "ver": ver,
        "eng_path": eng_path,
        "exit_code": exit_code,
        "output": output,
        "error_lines": error_lines,
        "warn_lines": warn_lines,
    }


def _run_phase(engines: List[dict], build_fn, max_workers: int,
               vs_version: Optional[str], label: str) -> Tuple[Dict[str, Dict], int, int, int]:
    print_lock = Lock()
    is_tty = sys.stdout.isatty()
    total = len(engines)
    ver_index = {e["version"]: i for i, e in enumerate(engines)}

    for e in engines:
        print(f"[{e['version']}] {label} Pending...", flush=True)

    results: Dict[str, Dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                build_fn, e, ver_index[e["version"]], total, print_lock, is_tty, vs_version
            ): e["version"]
            for e in engines
        }
        for fut in as_completed(futures):
            r = fut.result()
            results[r["ver"]] = r

    pass_count = fail_count = total_warnings = 0
    for engine in engines:
        r = results[engine["version"]]
        if r["exit_code"] == 0:
            pass_count += 1
            total_warnings += len(r["warn_lines"])
        elif r["exit_code"] != -1:
            fail_count += 1
            total_warnings += len(r["warn_lines"])
    return results, pass_count, fail_count, total_warnings


def _write_phase_log(path: Path, header: List[str], engines: List[dict],
                     results: Dict[str, Dict], summary_line: str) -> None:
    sep = "=" * 64
    lines_out = header + [""]
    pass_count = fail_count = total_warnings = 0

    for engine in engines:
        r = results[engine["version"]]
        p, f, w = _format_result_block(r, lines_out, sep)
        pass_count += p
        fail_count += f
        total_warnings += w
        lines_out.append("")

    lines_out.append(sep)
    lines_out.append(summary_line.format(pass_count, fail_count, total_warnings))
    lines_out.append(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out) + "\n")


def run_build_test_game(engines: List[dict], max_workers: int = 2,
                        vs_version: Optional[str] = None) -> int:
    """Game-target only (WITH_EDITOR=0). See run_build_test(..., include_game=True)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _TEMP_GAME_BASE.mkdir(parents=True, exist_ok=True)

    target = _PLATFORM_TARGET.get(_SYSTEM, "Linux")
    header = [
        "NexusLink Game-Target Build Report (WITH_EDITOR=0)",
        f"Time     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Target   : UnrealGame {target} Development",
        f"Method   : temp copy + uplugin Type Editor→Runtime + BuildPlugin",
        f"Plugin   : {PLUGIN_PATH}",
        f"Versions : {', '.join(e['version'] for e in engines)}",
    ]
    results, pass_count, fail_count, total_warnings = _run_phase(
        engines, _build_one_game, max_workers, vs_version, "Game"
    )
    _write_phase_log(
        LOG_FILE_GAME, header, engines, results,
        "Summary : PASS={}  FAIL={}  WARNINGS={}",
    )
    print(f"\nLog written to: {LOG_FILE_GAME}")
    print(f"Game summary: PASS={pass_count}  FAIL={fail_count}  WARNINGS={total_warnings}")
    return fail_count


def run_build_test(engines: List[dict], max_workers: int = 3,
                   vs_version: Optional[str] = None,
                   include_game: bool = True,
                   game_max_workers: int = 2) -> int:
    """
    Build all engine versions: Editor phase, then optional Game phase (WITH_EDITOR=0).

    :param max_workers: Max concurrent Editor builds.
    :param include_game: Run UnrealGame Development phase after Editor (default True).
    :param game_max_workers: Max concurrent Game builds (default 2).
    :return: Total failed version slots across phases.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_BASE.mkdir(parents=True, exist_ok=True)
    if include_game:
        _TEMP_GAME_BASE.mkdir(parents=True, exist_ok=True)

    plugin_path = str(PLUGIN_PATH)
    target = _PLATFORM_TARGET.get(_SYSTEM, "Linux")

    print("=== Phase 1: DevelopmentEditor (WITH_EDITOR=1) ===", flush=True)
    editor_results, ed_pass, ed_fail, ed_warn = _run_phase(
        engines,
        lambda e, idx, tot, pl, tty, vs: _build_one(e, plugin_path, idx, tot, pl, tty, vs),
        max_workers,
        vs_version,
        "Editor",
    )

    game_results: Dict[str, Dict] = {}
    gm_pass = gm_fail = gm_warn = 0
    if include_game:
        print("\n=== Phase 2: UnrealGame Development (WITH_EDITOR=0) ===", flush=True)
        game_results, gm_pass, gm_fail, gm_warn = _run_phase(
            engines, _build_one_game, game_max_workers, vs_version, "Game"
        )

    sep = "=" * 64
    lines_out: List[str] = [
        "NexusLink Cross-Version Build Report",
        f"Time     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Platform : {_SYSTEM}  (TargetPlatforms={target})",
        f"Plugin   : {plugin_path}",
        f"Versions : {', '.join(e['version'] for e in engines)}",
        f"Phases   : Editor{' + Game (WITH_EDITOR=0)' if include_game else ''}",
        "",
        "=== Phase 1: DevelopmentEditor (WITH_EDITOR=1) ===",
        "",
    ]

    for engine in engines:
        _format_result_block(editor_results[engine["version"]], lines_out, sep)
        lines_out.append("")

    lines_out.append(sep)
    lines_out.append(f"Editor Summary : PASS={ed_pass}  FAIL={ed_fail}  WARNINGS={ed_warn}")

    if include_game:
        lines_out.extend([
            "",
            "=== Phase 2: UnrealGame Development (WITH_EDITOR=0) ===",
            f"Method         : temp copy + uplugin Type Editor→Runtime + BuildPlugin",
            "",
        ])
        for engine in engines:
            _format_result_block(game_results[engine["version"]], lines_out, sep)
            lines_out.append("")
        lines_out.append(sep)
        lines_out.append(f"Game Summary   : PASS={gm_pass}  FAIL={gm_fail}  WARNINGS={gm_warn}")

    total_fail = ed_fail + gm_fail
    lines_out.extend([
        sep,
        f"Total Summary  : PASS={ed_pass + gm_pass}  FAIL={total_fail}  WARNINGS={ed_warn + gm_warn}",
        f"Finished       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ])

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out) + "\n")

    if include_game:
        game_header = [
            "NexusLink Game-Target Build Report (WITH_EDITOR=0)",
            f"Time     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Target   : UnrealGame {target} Development",
            f"Method   : temp copy + uplugin Type Editor→Runtime + BuildPlugin",
            f"Plugin   : {PLUGIN_PATH}",
            f"Versions : {', '.join(e['version'] for e in engines)}",
            "(extracted from build_test.py phase 2 — see also Build.Log)",
        ]
        _write_phase_log(
            LOG_FILE_GAME, game_header, engines, game_results,
            "Summary : PASS={}  FAIL={}  WARNINGS={}",
        )

    print(f"\nLog written to: {LOG_FILE}")
    if include_game:
        print(f"Game log     : {LOG_FILE_GAME}")
    print(
        f"Editor: PASS={ed_pass} FAIL={ed_fail} WARNINGS={ed_warn}"
        + (f" | Game: PASS={gm_pass} FAIL={gm_fail} WARNINGS={gm_warn}" if include_game else "")
    )
    return total_fail



def main() -> int:
    parser = argparse.ArgumentParser(description="NexusLink cross-version build test")
    parser.add_argument(
        "--ue-root",
        default=None,
        help="Root directory containing UE_X.Y sub-dirs; auto-detected when omitted",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        metavar="N",
        help="Max concurrent build workers (default 3); too many cause MSVC PCH OOM C3859",
    )
    parser.add_argument(
        "--versions",
        default=None,
        metavar="VER",
        nargs="+",
        help="Only test specified versions, e.g. --versions UE_5.2 UE_5.3",
    )
    parser.add_argument(
        "--vs",
        default=None,
        choices=["2017", "2019", "2022"],
        metavar="VER",
        help="Force MSVC toolchain (-VS<ver>) for all versions. "
             "Omit = UBT default; UE_4.26 / UE_4.27 auto-fall-back to -VS2019.",
    )
    phase = parser.add_mutually_exclusive_group()
    phase.add_argument(
        "--editor-only",
        action="store_true",
        help="Skip Game phase (WITH_EDITOR=0); only run DevelopmentEditor",
    )
    phase.add_argument(
        "--game-only",
        action="store_true",
        help="Only run UnrealGame Development (WITH_EDITOR=0); writes Build.Game.Log",
    )
    parser.add_argument(
        "--game-max-workers",
        type=int,
        default=2,
        metavar="N",
        help="Max concurrent Game-phase workers (default 2)",
    )
    args = parser.parse_args()

    if not PLUGIN_PATH.is_file():
        print(f"[ERROR] Plugin file not found: {PLUGIN_PATH}", file=sys.stderr)
        return 1

    try:
        engines = (
            discover_engines_from_root(args.ue_root)
            if args.ue_root
            else discover_engines_auto()
        )
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    if not engines:
        hint = (
            "Use --ue-root to specify engine root directory"
            if _SYSTEM == "Linux"
            else "Make sure Epic Games Launcher is installed"
        )
        print(f"[ERROR] No UE engine installations found. {hint}", file=sys.stderr)
        return 1

    print(f"Found {len(engines)} UE engine version(s):")
    for e in engines:
        print(f"  {e['version']} -> {e['path']}")
    print()

    if args.versions:
        allowed = set(args.versions)
        engines = [e for e in engines if e["version"] in allowed]
        if not engines:
            print(f"[ERROR] Specified versions {args.versions} not found in discovered list", file=sys.stderr)
            return 1

    if args.game_only:
        fail_count = run_build_test_game(
            engines,
            max_workers=args.game_max_workers,
            vs_version=args.vs,
        )
    else:
        fail_count = run_build_test(
            engines,
            max_workers=args.max_workers,
            vs_version=args.vs,
            include_game=not args.editor_only,
            game_max_workers=args.game_max_workers,
        )
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
