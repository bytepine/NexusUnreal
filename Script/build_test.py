#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright byteyang. All Rights Reserved.
"""
build_test.py -- NexusUnreal 工程跨版本编译

用本机已装的每套 UE 引擎编整个 `Nexus.uproject`（不只某个插件）：
  Phase 1 — NexusEditor / Development（WITH_EDITOR=1；编进游戏模块 + NexusLink + UnLua 等工程插件）
  Phase 2 — Nexus / Development（Game 目标，WITH_EDITOR=0）

不改仓库工程（不写 Intermediate/Binaries，不改 .uproject / .uplugin）。
每套引擎在系统临时目录建隔离工程：junction Content/Source/Config，
插件根建真实目录（Intermediate 落在临时树），然后对该副本调 UBT。
多引擎可并行（默认 --max-workers 3）。

日志：Saved/Logs/Build.Log（+ Build.Game.Log 对应 phase 2）。

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
import stat
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
UPROJECT_PATH = NEXUS_UNREAL_DIR / "Nexus.uproject"
EDITOR_TARGET = "NexusEditor"
GAME_TARGET = "Nexus"
LOG_DIR = NEXUS_UNREAL_DIR / "Saved" / "Logs"
LOG_FILE = LOG_DIR / "Build.Log"
LOG_FILE_GAME = LOG_DIR / "Build.Game.Log"
TEMP_BASE = Path(tempfile.gettempdir()) / "NexusBuildTest"

_SYSTEM = platform.system()  # "Windows" | "Darwin" | "Linux"

# 插件树里这些目录会由 UBT 写入，不能 junction 回仓库。
_SKIP_DIR_NAMES = frozenset({
    "Intermediate", "Binaries", "Saved", "DerivedDataCache",
    ".git", ".vs", ".idea", "__pycache__",
})

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


def _lexists(path: Path) -> bool:
    try:
        os.lstat(path)
        return True
    except OSError:
        return False


def _is_reparse_or_symlink(path: Path) -> bool:
    """junction / symlink：清理时只删链接，绝不下钻到仓库目标。"""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    attrs = getattr(st, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & reparse)


def _rmtree_nofollow(path: Path) -> None:
    """删除临时树；遇到 junction/symlink 只 unlink/rmdir，不跟随。"""
    if not _lexists(path):
        return
    if _is_reparse_or_symlink(path):
        try:
            os.unlink(path)
        except OSError:
            os.rmdir(path)
        return
    if stat.S_ISREG(os.lstat(path).st_mode):
        os.unlink(path)
        return
    try:
        entries = list(os.scandir(path))
    except OSError:
        return
    for entry in entries:
        _rmtree_nofollow(Path(entry.path))
    try:
        os.rmdir(path)
    except OSError:
        pass


def _cleanup_temp() -> None:
    _rmtree_nofollow(TEMP_BASE)


atexit.register(_cleanup_all)
atexit.register(_cleanup_temp)
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


def _ubt_build_script(engine_path: str) -> Optional[str]:
    """该引擎的 UBT 入口（Build.bat / Build.sh）。找不到则返回 None。"""
    batch = os.path.join(engine_path, "Engine", "Build", "BatchFiles")
    if _SYSTEM == "Windows":
        path = os.path.join(batch, "Build.bat")
    elif _SYSTEM == "Darwin":
        path = os.path.join(batch, "Mac", "Build.sh")
    else:
        path = os.path.join(batch, "Linux", "Build.sh")
    return path if os.path.isfile(path) else None


def _link_dir(src: Path, dst: Path) -> None:
    """目录 junction（Windows）或 symlink（POSIX），不复制内容。"""
    src = src.resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if _lexists(dst):
        return
    if _SYSTEM == "Windows":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"mklink /J 失败: {dst} -> {src}: {err}")
    else:
        os.symlink(src, dst, target_is_directory=True)


def _is_plugin_root(path: Path) -> bool:
    try:
        return any(path.glob("*.uplugin"))
    except OSError:
        return False


def _mirror_plugins_tree(src: Path, dst: Path) -> None:
    """
    复制插件树骨架：插件根为真实目录（UBT 的 Intermediate/Binaries 写在这里），
    Source/Content 等数据目录 junction 回仓库，不改原工程。
    """
    dst.mkdir(parents=True, exist_ok=True)
    plugin = _is_plugin_root(src)
    try:
        children = list(src.iterdir())
    except OSError:
        return
    for item in children:
        if item.name in _SKIP_DIR_NAMES:
            continue
        dest = dst / item.name
        if item.is_symlink() and not item.is_dir():
            shutil.copy2(item, dest, follow_symlinks=True)
            continue
        if not item.is_dir():
            shutil.copy2(item, dest)
            continue
        # 分组目录 / 嵌套 Plugins / 嵌套插件根：继续建真实目录往下走
        if (not plugin) or item.name == "Plugins" or _is_plugin_root(item):
            _mirror_plugins_tree(item, dest)
        else:
            _link_dir(item, dest)


_isolated_lock = Lock()
_isolated_ready: Dict[str, Path] = {}


def _reset_temp_workspace() -> None:
    with _isolated_lock:
        _isolated_ready.clear()
        _rmtree_nofollow(TEMP_BASE)
        TEMP_BASE.mkdir(parents=True, exist_ok=True)


def _prepare_isolated_project(ver: str) -> Path:
    dest = TEMP_BASE / ver / "Project"
    uproject = dest / "Nexus.uproject"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(UPROJECT_PATH, uproject)
    for name in ("Source", "Content", "Config"):
        src = NEXUS_UNREAL_DIR / name
        if src.is_dir():
            _link_dir(src, dest / name)
    plugins_src = NEXUS_UNREAL_DIR / "Plugins"
    if plugins_src.is_dir():
        _mirror_plugins_tree(plugins_src, dest / "Plugins")
    return uproject


def _isolated_uproject(ver: str) -> Path:
    with _isolated_lock:
        cached = _isolated_ready.get(ver)
        if cached is not None and cached.is_file():
            return cached
    path = _prepare_isolated_project(ver)
    with _isolated_lock:
        _isolated_ready[ver] = path
    return path


def _run_project_build(engine_path: str, target: str,
                       vs_version: Optional[str] = None,
                       uproject: Optional[Path] = None) -> Tuple[int, List[str]]:
    """
    用指定引擎编某个 Target（默认编隔离副本，不写仓库 Intermediate）。

    :param vs_version: optional MSVC toolchain selector, one of "2017"/"2019"/"2022"；
        传给 UBT 的 `-VS<ver>`。UE 4.26 / 4.27 在仅装 VS2019/VS2022 的机器上需要。
    :param uproject: 隔离副本的 .uproject；缺省则用仓库内文件（不推荐并行）。
    :return: (exit_code, output_lines)；exit_code=-1 表示找不到 Build 脚本（SKIP）。
    """
    script = _ubt_build_script(engine_path)
    if not script:
        return (-1, [f"UBT Build script not found under: {engine_path}"])

    platform_name = _PLATFORM_TARGET.get(_SYSTEM, "Linux")
    project = str((uproject or UPROJECT_PATH).resolve())
    ubt_args = [
        target,
        platform_name,
        "Development",
        f"-Project={project}",
        "-NoMutex",
    ]
    if vs_version:
        ubt_args.append(f"-VS{vs_version}")

    env = os.environ.copy()
    if _SYSTEM == "Windows":
        env["VSLANG"] = "1033"
        cmd = ["cmd", "/c", script] + ubt_args
        kwargs: dict = {"shell": False}
    else:
        os.chmod(script, 0o755)
        cmd = ["bash", script] + ubt_args
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


def _build_one(engine: dict, target: str, line_idx: int, total: int,
               print_lock: Lock, is_tty: bool,
               vs_version: Optional[str] = None,
               phase_label: str = "Editor") -> Dict:
    ver = engine["version"]
    eng_path = engine["path"]

    _update_status_line(
        f"[{ver}] {phase_label}: building {target}...", line_idx, total, print_lock, is_tty
    )

    try:
        uproject = _isolated_uproject(ver)
    except Exception as exc:
        msg = f"failed to prepare isolated project: {exc}"
        _update_status_line(f"[{ver}] {phase_label}: FAIL ({msg})", line_idx, total, print_lock, is_tty)
        return {
            "ver": ver,
            "eng_path": eng_path,
            "exit_code": 1,
            "output": [msg],
            "error_lines": [msg],
            "warn_lines": [],
        }

    effective_vs = vs_version or ("2019" if ver in _VS2019_FALLBACK_VERSIONS else None)
    exit_code, output = _run_project_build(eng_path, target, effective_vs, uproject=uproject)

    error_lines = _extract_errors(output) if exit_code not in (-1, 0) else []
    warn_lines = _extract_warnings(output) if exit_code != -1 else []

    if exit_code == -1:
        status = f"[{ver}] {phase_label}: SKIP"
    elif exit_code == 0:
        status = f"[{ver}] {phase_label}: PASS{f' ({len(warn_lines)} warnings)' if warn_lines else ''}"
    else:
        status = f"[{ver}] {phase_label}: FAIL (exit={exit_code})"

    _update_status_line(status, line_idx, total, print_lock, is_tty)

    return {
        "ver": ver,
        "eng_path": eng_path,
        "exit_code": exit_code,
        "output": output,
        "error_lines": error_lines,
        "warn_lines": warn_lines,
    }


def _run_phase(engines: List[dict], target: str, max_workers: int,
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
                _build_one, e, target, ver_index[e["version"]], total,
                print_lock, is_tty, vs_version, label,
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


def run_build_test_game(engines: List[dict], max_workers: int = 3,
                        vs_version: Optional[str] = None) -> int:
    """Game-target only (WITH_EDITOR=0). See run_build_test(..., include_game=True)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _reset_temp_workspace()
    print(f"Isolated builds under: {TEMP_BASE}", flush=True)

    platform_name = _PLATFORM_TARGET.get(_SYSTEM, "Linux")
    header = [
        "NexusUnreal Game-Target Build Report (WITH_EDITOR=0)",
        f"Time     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Target   : {GAME_TARGET} {platform_name} Development",
        f"Method   : UBT Build.bat/sh -Project=<isolated temp> -NoMutex",
        f"Project  : {UPROJECT_PATH} (read-only; build dir {TEMP_BASE})",
        f"Versions : {', '.join(e['version'] for e in engines)}",
    ]
    results, pass_count, fail_count, total_warnings = _run_phase(
        engines, GAME_TARGET, max_workers, vs_version, "Game"
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
                   game_max_workers: int = 3) -> int:
    """
    Build all engine versions: Editor phase, then optional Game phase (WITH_EDITOR=0).

    :param max_workers: concurrent Editor-phase engines (isolated temp per version).
    :param include_game: Run Nexus Game target after Editor (default True).
    :param game_max_workers: concurrent Game-phase engines.
    :return: Total failed version slots across phases.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _reset_temp_workspace()
    print(f"Isolated builds under: {TEMP_BASE}", flush=True)

    platform_name = _PLATFORM_TARGET.get(_SYSTEM, "Linux")
    project = str(UPROJECT_PATH)

    print("=== Phase 1: NexusEditor Development (WITH_EDITOR=1) ===", flush=True)
    editor_results, ed_pass, ed_fail, ed_warn = _run_phase(
        engines, EDITOR_TARGET, max_workers, vs_version, "Editor",
    )

    game_results: Dict[str, Dict] = {}
    gm_pass = gm_fail = gm_warn = 0
    if include_game:
        print("\n=== Phase 2: Nexus Development (WITH_EDITOR=0) ===", flush=True)
        game_results, gm_pass, gm_fail, gm_warn = _run_phase(
            engines, GAME_TARGET, game_max_workers, vs_version, "Game"
        )

    sep = "=" * 64
    lines_out: List[str] = [
        "NexusUnreal Cross-Version Build Report",
        f"Time     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Platform : {_SYSTEM}  (UBT Platform={platform_name})",
        f"Project  : {project} (read-only)",
        f"BuildDir : {TEMP_BASE}",
        f"Workers  : Editor={max_workers}"
        + (f" Game={game_max_workers}" if include_game else ""),
        f"Targets  : {EDITOR_TARGET} (Editor) / {GAME_TARGET} (Game)",
        f"Versions : {', '.join(e['version'] for e in engines)}",
        f"Phases   : Editor{' + Game (WITH_EDITOR=0)' if include_game else ''}",
        "",
        "=== Phase 1: NexusEditor Development (WITH_EDITOR=1) ===",
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
            "=== Phase 2: Nexus Development (WITH_EDITOR=0) ===",
            f"Method         : UBT {GAME_TARGET} Development -Project=<isolated temp> -NoMutex",
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
            "NexusUnreal Game-Target Build Report (WITH_EDITOR=0)",
            f"Time     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Target   : {GAME_TARGET} {platform_name} Development",
            f"Method   : UBT Build.bat/sh -Project=<isolated temp> -NoMutex",
            f"Project  : {UPROJECT_PATH} (read-only; build dir {TEMP_BASE})",
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
    parser = argparse.ArgumentParser(
        description="NexusUnreal cross-version project build (all installed engines)"
    )
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
        help="Max concurrent Editor-phase builds (default 3). Each engine uses an isolated temp project.",
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
        help="Skip Game phase (WITH_EDITOR=0); only build NexusEditor",
    )
    phase.add_argument(
        "--game-only",
        action="store_true",
        help="Only build Nexus Game target (WITH_EDITOR=0); writes Build.Game.Log",
    )
    parser.add_argument(
        "--game-max-workers",
        type=int,
        default=None,
        metavar="N",
        help="Max concurrent Game-phase workers (default: same as --max-workers)",
    )
    args = parser.parse_args()

    if not UPROJECT_PATH.is_file():
        print(f"[ERROR] Project file not found: {UPROJECT_PATH}", file=sys.stderr)
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
        bad = [v for v in args.versions if not v.startswith("UE_")]
        if bad:
            print(
                f"[ERROR] --versions must use UE_ prefix (got {bad}), e.g. UE_5.7",
                file=sys.stderr,
            )
            return 1
        allowed = set(args.versions)
        engines = [e for e in engines if e["version"] in allowed]
        if not engines:
            print(f"[ERROR] Specified versions {args.versions} not found in discovered list", file=sys.stderr)
            return 1

    if args.max_workers < 1:
        print("[ERROR] --max-workers must be >= 1", file=sys.stderr)
        return 1
    game_workers = args.game_max_workers if args.game_max_workers is not None else args.max_workers
    if game_workers < 1:
        print("[ERROR] --game-max-workers must be >= 1", file=sys.stderr)
        return 1
    if args.game_only:
        fail_count = run_build_test_game(
            engines,
            max_workers=game_workers,
            vs_version=args.vs,
        )
    else:
        fail_count = run_build_test(
            engines,
            max_workers=args.max_workers,
            vs_version=args.vs,
            include_game=not args.editor_only,
            game_max_workers=game_workers,
        )
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
