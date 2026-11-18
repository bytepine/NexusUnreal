# Copyright byteyang. All Rights Reserved.
"""UEEditor launcher for pytest auto-launch mode.

Used when pytest is invoked without --ue-url. Launches an editor process
against the nexus-unreal host project, polls GET /status until the MCP server
reports ready, and tears the process down at session end.

Design notes:
- **Default is headless** (`UnrealEditor-Cmd` + `-unattended -nullrhi -NoSplash
  -NoSound`) so auto-launch never pops windows or blocks on dialogs.
- **GUI mode** (`UELauncher(headless=False)` / pytest `--gui`) uses
  `UnrealEditor.exe` when you want to watch asset ops / PIE during tests.
  The MCP server still listens on 45000..45009 exactly the same way.
- We rely on NexusLink auto-starting its MCP server on OnPostEngineInit with
  a stable default port (45000). If the port is taken, NexusLink picks the
  next free port in 45000..45009 and /status exposes it, so the launcher
  probes a small range.
- `-skipcompile` skips the "modules out of date, rebuild?" prompt — our UBT
  pre-build step in `_ensure_editor_target_built` has already produced the
  DLLs so loading is safe.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import shutil
import socket
import subprocess
import tempfile
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import urlsplit

import httpx
import psutil

log = logging.getLogger(__name__)

_STATUS_ENDPOINT = "/status"
_STREAM_ENDPOINT = "/stream"
_DEFAULT_PORT_RANGE = range(45000, 45010)
_READY_TIMEOUT_SEC = 180.0


def _process_project(process: psutil.Process, engine_version: str) -> Optional[Path]:
    # UE 使用首个位置参数，5.2+ 的 -project= 优先。其他参数可能是导入或比较对象。
    args = process.cmdline()[1:]
    arg = args[0] if args else ""
    options = [value.split("=", 1)[1] for value in args if value.casefold().startswith("-project=")]
    if options:
        version = re.match(r"^(\d+)\.(\d+)", engine_version)
        if not version or len(options) != 1:
            return None
        if tuple(map(int, version.groups())) >= (5, 2):
            arg = options[0]
    # 相对路径可能基于 UE 启动时的工作目录，不能按当前目录补全。
    path = Path(arg.strip('"'))
    return path.resolve() if path.suffix.casefold() == ".uproject" and path.is_absolute() else None


def _owns_listener(process: psutil.Process, port: int, ipv6: bool) -> bool:
    # psutil 5.9 使用 connections，6.x 起更名为 net_connections。
    connections = getattr(process, "net_connections", None) or process.connections
    family = socket.AF_INET6 if ipv6 else socket.AF_INET
    addresses = ("::1", "::") if ipv6 else ("127.0.0.1", "0.0.0.0")
    return any(c.status == psutil.CONN_LISTEN and c.family == family and
               c.laddr.port == port and c.laddr.ip in addresses for c in connections(kind="tcp"))


def matching_editor_urls(project: Path, url: Optional[str] = None, *, launched_pid: Optional[int] = None) -> List[str]:
    """按目标工程、监听进程、具体回环地址与 Editor 状态匹配；自启动时仅核验已知子进程。"""
    project = project.resolve()
    requested = urlsplit(url) if url else None
    if requested and (requested.scheme != "http" or requested.hostname not in ("localhost", "127.0.0.1", "::1")
                      or requested.path.rstrip("/") not in ("", "/stream") or requested.username is not None
                      or requested.query or requested.fragment):
        return []
    ipv6 = bool(requested and requested.hostname == "::1")
    host = "[::1]" if ipv6 else "127.0.0.1"
    matches = []
    registry = Path(tempfile.gettempdir()) / "NexusLink"
    manifests = (registry / f"{launched_pid}.json",) if launched_pid is not None else registry.glob("*.json")
    with httpx.Client(timeout=2, trust_env=False) as client:
        for manifest in manifests:
            if not manifest.stem.isdecimal():
                continue
            try:
                data = json.loads(manifest.read_text(encoding="utf-8-sig"))
                if not isinstance(data, dict) or data.get("pid") != int(manifest.stem):
                    continue
                port = data.get("mcpPort")
                if type(port) is not int or not 0 < port < 65536 or (requested and port != (requested.port or 80)):
                    continue
                if str(data.get("projectName", "")).casefold() != project.stem.casefold():
                    continue
                base = f"http://{host}:{port}"
                process = psutil.Process(data["pid"])
                try:
                    if not _owns_listener(process, port, ipv6):
                        continue
                    process_project = project if launched_pid is not None else _process_project(
                        process, str(data.get("engineVersion", "")))
                except psutil.AccessDenied:
                    process_project = None
                if process_project is not None and process_project != project:
                    continue
                response = client.get(base + _STATUS_ENDPOINT)
                response.raise_for_status()
                status = response.json()
                if (not isinstance(status, dict) or status.get("server") != "Nexus-Unreal"
                        or status.get("hostKind") != "Editor"
                        or str(status.get("projectName", "")).casefold() != project.stem.casefold()
                        or type(data.get("wsPort")) is not int or status.get("wsPort") != data["wsPort"]):
                    continue
            except (OSError, ValueError, psutil.Error, httpx.HTTPError):
                continue
            if process_project is None:
                raise RuntimeError(f"Cannot verify the process and .uproject for {base} ({project.name})")
            matches.append(base + _STREAM_ENDPOINT)
    return matches


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def resolve_editor_exe(ue_root: Path, headless: bool = True) -> Path:
    """Resolve the editor binary inside a given UE_X.Y install root.

    When `headless` is True (default), prefer the `-Cmd` variant (console-only).
    Otherwise prefer the GUI variant so users can watch the editor while pytest
    drives it."""
    if _is_windows():
        gui = [
            ue_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe",
            ue_root / "Engine" / "Binaries" / "Win64" / "UE4Editor.exe",
        ]
        cmd = [
            ue_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe",
            ue_root / "Engine" / "Binaries" / "Win64" / "UE4Editor-Cmd.exe",
        ]
    elif _is_macos():
        gui = [
            ue_root / "Engine" / "Binaries" / "Mac" / "UnrealEditor",
            ue_root / "Engine" / "Binaries" / "Mac" / "UE4Editor",
        ]
        cmd = [
            ue_root / "Engine" / "Binaries" / "Mac" / "UnrealEditor-Cmd",
            ue_root / "Engine" / "Binaries" / "Mac" / "UE4Editor-Cmd",
        ]
    else:
        gui = [
            ue_root / "Engine" / "Binaries" / "Linux" / "UnrealEditor",
            ue_root / "Engine" / "Binaries" / "Linux" / "UE4Editor",
        ]
        cmd = [
            ue_root / "Engine" / "Binaries" / "Linux" / "UnrealEditor-Cmd",
            ue_root / "Engine" / "Binaries" / "Linux" / "UE4Editor-Cmd",
        ]
    candidates = (cmd + gui) if headless else (gui + cmd)
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"UE Editor binary not found under {ue_root}; looked for: "
        f"{', '.join(str(c) for c in candidates)}"
    )


@dataclass
class UELauncher:
    uproject: Path
    ue_root: Path
    port_range: Iterable[int] = _DEFAULT_PORT_RANGE
    extra_args: Optional[List[str]] = None
    ready_timeout: float = _READY_TIMEOUT_SEC
    headless: bool = True

    _proc: Optional[subprocess.Popen] = None
    _resolved_port: Optional[int] = None
    _stdout_log_path: Optional[Path] = None
    _stdout_log_fh: Optional[object] = None

    def __post_init__(self) -> None:
        self.uproject = Path(self.uproject).resolve()
        self.ue_root = Path(self.ue_root).resolve()
        if not self.uproject.exists():
            raise FileNotFoundError(f"uproject not found: {self.uproject}")
        if not self.ue_root.exists():
            raise FileNotFoundError(f"ue_root not found: {self.ue_root}")

    @property
    def url(self) -> str:
        if not self._resolved_port:
            raise RuntimeError("UE not ready yet")
        return f"http://127.0.0.1:{self._resolved_port}{_STREAM_ENDPOINT}"

    def __enter__(self) -> "UELauncher":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def start(self) -> None:
        # 宿主工程测试须编进 GAS / Niagara capability
        os.environ["WITH_GAS"] = "1"
        os.environ["WITH_NIAGARA"] = "1"

        # Pre-build the host project's Editor module when its DLL is missing
        # — UEEditor-Cmd with -unattended will NOT prompt "modules out of date,
        # rebuild?" and instead silently exits with code 1. We compile via UBT
        # first so the Editor can simply load the DLL.
        self._ensure_editor_target_built()

        exe = resolve_editor_exe(self.ue_root, headless=self.headless)
        args: List[str] = [str(exe), str(self.uproject)]
        if self.headless:
            # Quiet CI-style launch: no window, no RHI, no splash, no prompts.
            args += [
                "-unattended",
                "-NoSound",
                "-NoSplash",
                "-nullrhi",
                "-stdout",
                "-FullStdOutLogOutput",
            ]
        else:
            # GUI mode: keep splash + full editor windows so the user can watch
            # pytest driving the editor. `-stdout`/`-FullStdOutLogOutput` still
            # mirror the engine log to our capture file for early-exit triage.
            args += ["-stdout", "-FullStdOutLogOutput"]
        args.append("-skipcompile")
        # GUI 编辑器默认会自动开 Live Coding，SavePackage 会被插件降级为 deferred
        args.append("-LiveCoding=false")
        # 会话级强制开 MCP（不依赖 Preferences / Config 目录）
        args.append("-EnableNexusMcp")
        # 会话级打开危险 Capability，供 exec_command / Lua eval/dofile 用例；不写盘
        args.append("-NexusEnableDangerousCaps")
        if self.extra_args:
            args.extend(self.extra_args)
        # Persist stdout/stderr so we can surface real reasons for early-exit
        # (missing platform SDK, stale Editor module, etc.) instead of a bare
        # "exited early with code 1".
        log_dir = self.uproject.parent / "Saved" / "Logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._stdout_log_path = log_dir / "UE-auto-launch.stdout.log"
        self._stdout_log_fh = open(self._stdout_log_path, "w", encoding="utf-8",
                                   errors="replace", buffering=1)

        log.info("launching UE: %s", " ".join(args))
        log.info("UE stdout -> %s", self._stdout_log_path)
        try:
            self._proc = subprocess.Popen(
                args,
                stdout=self._stdout_log_fh,
                stderr=subprocess.STDOUT,
                cwd=str(self.uproject.parent),
            )
            self._wait_until_ready()
        except BaseException:
            self.stop()
            raise

    def _detect_ue_version_label(self) -> Optional[str]:
        """Return `UE_X.Y` for the resolved engine root (or None when unknown)."""
        m = re.match(r"^UE[_\-]?(\d+)\.(\d+)", self.ue_root.name)
        if m:
            return f"UE_{m.group(1)}.{m.group(2)}"
        bv = self.ue_root / "Engine" / "Build" / "Build.version"
        if bv.is_file():
            try:
                data = json.loads(bv.read_text(encoding="utf-8"))
                return f"UE_{data['MajorVersion']}.{data['MinorVersion']}"
            except Exception:  # noqa: BLE001
                pass
        return None

    def _detect_editor_target_name(self) -> str:
        """Read the uproject's primary Runtime module and append `Editor` —
        matches how UBT names the Editor target for host projects."""
        try:
            data = json.loads(self.uproject.read_text(encoding="utf-8"))
            modules = data.get("Modules") or []
            if modules:
                primary = str(modules[0].get("Name", "")).strip()
                if primary:
                    return f"{primary}Editor"
        except Exception:  # noqa: BLE001
            pass
        return f"{self.uproject.stem}Editor"

    def _editor_module_dll_exists(self, module_name: str) -> bool:
        bin_dir = self.uproject.parent / "Binaries" / "Win64"
        if _is_windows():
            candidates = [
                bin_dir / f"UnrealEditor-{module_name}.dll",
                bin_dir / f"UE4Editor-{module_name}.dll",
            ]
        elif _is_macos():
            mac_dir = self.uproject.parent / "Binaries" / "Mac"
            candidates = [
                mac_dir / f"UnrealEditor-{module_name}.dylib",
                mac_dir / f"UE4Editor-{module_name}.dylib",
            ]
        else:
            lin_dir = self.uproject.parent / "Binaries" / "Linux"
            candidates = [
                lin_dir / f"libUnrealEditor-{module_name}.so",
                lin_dir / f"libUE4Editor-{module_name}.so",
            ]
        return any(p.exists() for p in candidates)

    def _ensure_editor_target_built(self) -> None:
        target_name = self._detect_editor_target_name()
        # Heuristic: if the primary runtime module's Editor DLL is already on
        # disk we assume the whole Editor target is up to date. UBT will
        # fast-path no-op when the user happens to rebuild via IDE; we only
        # need to cover the clean-checkout case.
        primary_module = target_name[:-len("Editor")] if target_name.endswith("Editor") else target_name
        force_rebuild = os.environ.get("WITH_GAS") == "1"
        if self._editor_module_dll_exists(primary_module) and not force_rebuild:
            log.info("%s module DLL present; skipping UBT pre-build",
                     primary_module)
            return

        if _is_windows():
            build_script = self.ue_root / "Engine" / "Build" / "BatchFiles" / "Build.bat"
        elif _is_macos():
            build_script = self.ue_root / "Engine" / "Build" / "BatchFiles" / "Mac" / "Build.sh"
        else:
            build_script = self.ue_root / "Engine" / "Build" / "BatchFiles" / "Linux" / "Build.sh"
        if not build_script.exists():
            raise FileNotFoundError(f"UBT Build script not found: {build_script}")

        platform_name = "Win64" if _is_windows() else ("Mac" if _is_macos() else "Linux")
        cmd: List[str] = [
            str(build_script), target_name, platform_name, "Development",
            f"-Project={self.uproject}", "-WaitMutex",
        ]
        # Mirror build_test.py: UE 4.26 / 4.27 UBT defaults to VS2017, but most
        # modern hosts only ship VS2019/VS2022. Fall back to -VS2019 so UBT
        # can actually locate a toolchain.
        ver_label = self._detect_ue_version_label()
        if ver_label in {"UE_4.26", "UE_4.27"}:
            cmd.append("-VS2019")

        log_dir = self.uproject.parent / "Saved" / "Logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        build_log_path = log_dir / "UE-auto-launch-build.log"

        log.info("pre-building %s via UBT (%s): %s",
                 target_name, ver_label or "unknown", " ".join(cmd))
        log.info("UBT log -> %s", build_log_path)

        with open(build_log_path, "w", encoding="utf-8",
                  errors="replace", buffering=1) as fh:
            proc = subprocess.run(
                cmd,
                stdout=fh,
                stderr=subprocess.STDOUT,
                cwd=str(self.uproject.parent),
            )
        if proc.returncode != 0:
            tail = self._read_tail_file(build_log_path, 40)
            raise RuntimeError(
                f"UBT pre-build failed (exit {proc.returncode}) for "
                f"{target_name}. Full log: {build_log_path}\n"
                f"--- tail ---\n{tail}\n--- end tail ---"
            )
        log.info("UBT pre-build OK (%s)", target_name)

    @staticmethod
    def _read_tail_file(path: Path, max_lines: int) -> str:
        if not path.exists():
            return ""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:  # noqa: BLE001
            return f"<failed to read {path}: {e}>"
        tail = lines[-max_lines:] if len(lines) > max_lines else lines
        return "".join(tail).rstrip()

    def _flush_stdout_log(self) -> None:
        try:
            if self._stdout_log_fh is not None:
                self._stdout_log_fh.flush()
        except Exception:  # noqa: BLE001
            pass

    def stop(self) -> None:
        self._flush_stdout_log()
        if self._stdout_log_fh is not None:
            try:
                self._stdout_log_fh.close()
            except Exception:  # noqa: BLE001
                pass
            self._stdout_log_fh = None
        if self._proc is None or self._proc.poll() is not None:
            self._proc = None
            return
        try:
            parent = psutil.Process(self._proc.pid)
            children = parent.children(recursive=True)
            for c in children:
                try:
                    c.terminate()
                except psutil.Error:
                    pass
            parent.terminate()
            gone, alive = psutil.wait_procs([parent, *children], timeout=10)
            for p in alive:
                try:
                    p.kill()
                except psutil.Error:
                    pass
        except psutil.Error:
            # Fallback
            try:
                self._proc.terminate()
                self._proc.wait(timeout=10)
            except Exception:  # noqa: BLE001
                try:
                    self._proc.kill()
                except Exception:  # noqa: BLE001
                    pass
        self._proc = None

    def _tail_stdout_log(self, max_lines: int = 40) -> str:
        if not self._stdout_log_path or not self._stdout_log_path.exists():
            return ""
        try:
            self._flush_stdout_log()
            with open(self._stdout_log_path, "r", encoding="utf-8",
                      errors="replace") as f:
                lines = f.readlines()
        except Exception as e:  # noqa: BLE001
            return f"<failed to read stdout log: {e}>"
        tail = lines[-max_lines:] if len(lines) > max_lines else lines
        return "".join(tail).rstrip()

    @property
    def pid(self) -> int:
        if self._proc is None:
            raise RuntimeError("Editor process has not started")
        return self._proc.pid

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + self.ready_timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError(
                    f"UEEditor-Cmd exited early with code {self._proc.returncode}. "
                    f"Full log: {self._stdout_log_path}\n--- tail ---\n{self._tail_stdout_log()}"
                )
            urls = matching_editor_urls(self.uproject, launched_pid=self.pid)
            if len(urls) == 1:
                port = urlsplit(urls[0]).port
                if port in self.port_range:
                    self._resolved_port = port
                    log.info("UE ready on port %d (PID %d)", port, self.pid)
                    return
            time.sleep(1.0)
        raise RuntimeError(f"UE PID {self.pid} did not become ready within {self.ready_timeout}s")


def autodetect_uproject(default_subpath: str = "nexus-unreal/Nexus.uproject") -> Optional[Path]:
    """Best-effort detection of the host uproject under the repo."""
    here = Path(__file__).resolve()
    local = here.parents[2] / "Nexus.uproject"
    if default_subpath == "nexus-unreal/Nexus.uproject" and local.is_file():
        return local
    for parent in [here.parent, *here.parents]:
        candidate = parent / default_subpath
        if candidate.exists():
            return candidate
        for u in parent.glob("nexus-unreal/*.uproject"):
            return u
    return None
