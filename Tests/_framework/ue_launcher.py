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
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import httpx
import psutil

log = logging.getLogger(__name__)

_STATUS_ENDPOINT = "/status"
_STREAM_ENDPOINT = "/stream"
_DEFAULT_PORT_RANGE = range(45000, 45010)
_READY_TIMEOUT_SEC = 180.0
_MCP_SETTINGS_SECTION = "[/Script/NexusLink.NexusLinkSettings]"
_MCP_ENABLE_INI_LINE = "bEnableMcpServer=True"


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
        self._ensure_mcp_server_enabled()

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
        # headless 下 DefaultEditorPerProjectUserSettings 可能尚未落盘，命令行再强制一次
        args.append(
            "-ini:EditorPerProjectUserSettings:"
            "[/Script/NexusLink.NexusLinkSettings]:bEnableMcpServer=True"
        )
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
        self._proc = subprocess.Popen(
            args,
            stdout=self._stdout_log_fh,
            stderr=subprocess.STDOUT,
            cwd=str(self.uproject.parent),
        )
        try:
            self._wait_until_ready()
        except RuntimeError:
            self._flush_stdout_log()
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

    def _ensure_mcp_server_enabled(self) -> None:
        """pytest 自动拉起须开启 MCP；写入 Saved 配置供 UE4Editor-Cmd 读取。"""
        if _is_windows():
            config_dir = self.uproject.parent / "Saved" / "Config" / "Windows"
        elif _is_macos():
            config_dir = self.uproject.parent / "Saved" / "Config" / "Mac"
        else:
            config_dir = self.uproject.parent / "Saved" / "Config" / "Linux"
        config_dir.mkdir(parents=True, exist_ok=True)
        ini_path = config_dir / "EditorPerProjectUserSettings.ini"
        block = f"{_MCP_SETTINGS_SECTION}\r\n{_MCP_ENABLE_INI_LINE}\r\n"
        if ini_path.is_file():
            text = ini_path.read_text(encoding="utf-8", errors="replace")
            if _MCP_ENABLE_INI_LINE in text:
                return
            if _MCP_SETTINGS_SECTION in text:
                text = text.replace(
                    "bEnableMcpServer=False",
                    _MCP_ENABLE_INI_LINE,
                )
                if _MCP_ENABLE_INI_LINE not in text:
                    text = text.rstrip() + f"\r\n{_MCP_ENABLE_INI_LINE}\r\n"
            else:
                text = text.rstrip() + f"\r\n\r\n{block}"
            ini_path.write_text(text, encoding="utf-8")
        else:
            ini_path.write_text(block, encoding="utf-8")
        log.info("ensured MCP enabled in %s", ini_path)

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
        if self._proc is None:
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

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + self.ready_timeout
        last_err: Optional[BaseException] = None
        with httpx.Client(timeout=2.0) as client:
            while time.monotonic() < deadline:
                if self._proc is not None and self._proc.poll() is not None:
                    tail = self._tail_stdout_log()
                    raise RuntimeError(
                        f"UEEditor-Cmd exited early with code "
                        f"{self._proc.returncode}. "
                        f"Full log: {self._stdout_log_path}\n"
                        f"--- tail ---\n{tail}\n--- end tail ---"
                    )
                for port in self.port_range:
                    try:
                        r = client.get(f"http://127.0.0.1:{port}{_STATUS_ENDPOINT}")
                        if r.status_code == 200 and "wsPort" in r.text:
                            self._resolved_port = port
                            log.info("UE ready on port %d (%s)", port, r.text.strip())
                            return
                    except Exception as e:  # noqa: BLE001
                        last_err = e
                time.sleep(1.0)
        raise RuntimeError(
            f"UE did not become ready within {self.ready_timeout}s; "
            f"last probe error: {last_err}"
        )


def autodetect_uproject(default_subpath: str = "nexus-unreal/Nexus.uproject") -> Optional[Path]:
    """Best-effort detection of the host uproject under the repo."""
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / default_subpath
        if candidate.exists():
            return candidate
        for u in parent.glob("nexus-unreal/*.uproject"):
            return u
    return None
