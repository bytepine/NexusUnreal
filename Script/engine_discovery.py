#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright byteyang. All Rights Reserved.
"""
engine_discovery.py -- UE 引擎安装目录自动探测

供 build_test.py 和 run_e2e.py 共同复用，避免重复的 sys.path 动态导入。
"""

import json
import os
import platform
import re
from pathlib import Path
from typing import List, Tuple

_SYSTEM = platform.system()  # "Windows" | "Darwin" | "Linux"

_VER_PATTERN = re.compile(r"^UE_(\d+)\.(\d+)$")

_LINUX_COMMON_ROOTS: List[Path] = [
    Path.home() / "UnrealEngine",
    Path("/opt/UnrealEngine"),
    Path("/usr/local/UnrealEngine"),
]


def _launcher_dat_path() -> Path:
    if _SYSTEM == "Windows":
        prog_data = os.environ.get("PROGRAMDATA", "C:/ProgramData")
        return Path(prog_data) / "Epic" / "UnrealEngineLauncher" / "LauncherInstalled.dat"
    if _SYSTEM == "Darwin":
        shared = Path("/Users/Shared/Epic/UnrealEngineLauncher/LauncherInstalled.dat")
        if shared.is_file():
            return shared
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Epic"
            / "UnrealEngineLauncher"
            / "LauncherInstalled.dat"
        )
    return Path.home() / ".config" / "Epic" / "UnrealEngineLauncher" / "LauncherInstalled.dat"


def _version_key(app_name: str) -> Tuple[int, int]:
    m = _VER_PATTERN.match(app_name)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _parse_dat(dat_path: Path) -> List[dict]:
    with open(dat_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    seen: set = set()
    engines: List[dict] = []
    for item in data.get("InstallationList", []):
        name = item.get("AppName", "")
        path = item.get("InstallLocation", "")
        if not _VER_PATTERN.match(name) or path in seen:
            continue
        seen.add(path)
        engines.append({"version": name, "path": path})
    return engines


def discover_engines_from_dat(dat_path: Path) -> List[dict]:
    if not dat_path.is_file():
        raise FileNotFoundError(f"LauncherInstalled.dat not found: {dat_path}")
    engines = _parse_dat(dat_path)
    engines.sort(key=lambda e: _version_key(e["version"]))
    return engines


def discover_engines_from_root(ue_root: str) -> List[dict]:
    root = Path(ue_root)
    if not root.is_dir():
        raise NotADirectoryError(f"Engine root directory not found: {ue_root}")
    engines = [
        {"version": entry.name, "path": str(entry)}
        for entry in root.iterdir()
        if entry.is_dir() and _VER_PATTERN.match(entry.name)
    ]
    engines.sort(key=lambda e: _version_key(e["version"]))
    return engines


def discover_engines_auto() -> List[dict]:
    engines: List[dict] = []

    dat = _launcher_dat_path()
    if dat.is_file():
        try:
            engines = _parse_dat(dat)
        except Exception:
            pass

    if _SYSTEM == "Linux":
        seen = {e["path"] for e in engines}
        for base in _LINUX_COMMON_ROOTS:
            if not base.is_dir():
                continue
            for entry in base.iterdir():
                p = str(entry)
                if entry.is_dir() and _VER_PATTERN.match(entry.name) and p not in seen:
                    engines.append({"version": entry.name, "path": p})
                    seen.add(p)

    engines.sort(key=lambda e: _version_key(e["version"]))
    return engines
