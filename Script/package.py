#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright byteyang. All Rights Reserved.
"""
package.py -- NexusUnreal 任意平台打包（RunUAT BuildCookRun）

默认：uproject EngineAssociation 对应引擎 + 本机平台 + Development。
Development 包可用 -EnableNexusMcp 验证 Runtime MCP；Shipping 会编译期剔除 MCP。

Usage:
    py Script/package.py
    py Script/package.py --platform Win64 Linux
    py Script/package.py --platform Android --config Shipping -- -cookflavor=ASTC
    py Script/package.py --dry-run --platform Mac
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
NEXUS_UNREAL_DIR = SCRIPT_DIR.parent
UPROJECT_PATH = NEXUS_UNREAL_DIR / "Nexus.uproject"
DEFAULT_TARGET = "Nexus"
DEFAULT_ARCHIVE = NEXUS_UNREAL_DIR / "Saved" / "Packages"

_SYSTEM = platform.system()

_HOST_PLATFORM = {
    "Windows": "Win64",
    "Darwin": "Mac",
    "Linux": "Linux",
}

# 别名 → UAT -platform；未命中则原样透传（可打主机未列出的目标）
_PLATFORM_ALIASES = {
    "win": "Win64",
    "win64": "Win64",
    "windows": "Win64",
    "mac": "Mac",
    "macos": "Mac",
    "osx": "Mac",
    "darwin": "Mac",
    "linux": "Linux",
    "linuxarm64": "LinuxArm64",
    "linux-arm64": "LinuxArm64",
    "android": "Android",
    "ios": "IOS",
    "tvos": "TVOS",
}

_CONFIG_ALIASES = {
    "debug": "DebugGame",
    "debuggame": "DebugGame",
    "dev": "Development",
    "development": "Development",
    "test": "Test",
    "shipping": "Shipping",
}

sys.path.insert(0, str(SCRIPT_DIR))
from engine_discovery import discover_engines_auto  # noqa: E402


def _runuat_path(ue_root: Path) -> Path:
    batch = ue_root / "Engine" / "Build" / "BatchFiles"
    if _SYSTEM == "Windows":
        return batch / "RunUAT.bat"
    for candidate in (batch / "RunUAT.sh", batch / "RunUAT.command"):
        if candidate.is_file():
            return candidate
    return batch / "RunUAT.sh"


def _uproject_engine_association(uproject: Path) -> Optional[str]:
    try:
        with open(uproject, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    label = str(data.get("EngineAssociation") or "").strip()
    if not label:
        return None
    label = label.replace("UE_", "").replace("UE", "")
    m = re.match(r"^(\d+)\.(\d+)$", label)
    return f"UE_{m.group(1)}.{m.group(2)}" if m else None


def _normalize_version(label: str) -> str:
    text = label.strip()
    if re.match(r"^UE_\d+\.\d+$", text, re.IGNORECASE):
        return "UE_" + text.split("_", 1)[1]
    m = re.match(r"^(\d+)\.(\d+)$", text)
    if m:
        return f"UE_{m.group(1)}.{m.group(2)}"
    return text


def _normalize_platform(name: str) -> str:
    key = name.strip().replace(" ", "").lower()
    return _PLATFORM_ALIASES.get(key, name.strip())


def _normalize_config(name: str) -> str:
    key = name.strip().replace(" ", "").lower()
    mapped = _CONFIG_ALIASES.get(key)
    if not mapped:
        sys.exit(
            f"未知配置 {name!r}。可用：Development / DebugGame / Test / Shipping"
        )
    return mapped


def _split_platforms(values: Optional[List[str]]) -> List[str]:
    if not values:
        host = _HOST_PLATFORM.get(_SYSTEM)
        if not host:
            sys.exit(f"无法推断本机平台（system={_SYSTEM}），请显式传 --platform")
        return [host]
    out: List[str] = []
    seen = set()
    for raw in values:
        for part in raw.replace(";", ",").split(","):
            part = part.strip()
            if not part:
                continue
            plat = _normalize_platform(part)
            if plat not in seen:
                seen.add(plat)
                out.append(plat)
    return out


def _resolve_engine(ue_root: Optional[str], version: Optional[str]) -> Tuple[str, Path]:
    if ue_root:
        root = Path(ue_root)
        uat = _runuat_path(root)
        if not uat.is_file():
            sys.exit(f"RunUAT 不存在：{uat}")
        return root.name, root

    try:
        engines = discover_engines_auto()
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"引擎探测失败：{exc}")
    if not engines:
        sys.exit("未发现已安装的 UE。请传 --ue-root 或 --version")

    preferred = (
        _normalize_version(version)
        if version
        else _uproject_engine_association(UPROJECT_PATH)
    )

    def _has_uat(path: str) -> bool:
        return _runuat_path(Path(path)).is_file()

    if preferred:
        for entry in engines:
            if entry["version"].lower() == preferred.lower() and _has_uat(entry["path"]):
                return entry["version"], Path(entry["path"])
        sys.exit(f"未找到引擎 {preferred}（或缺少 RunUAT）。已发现：{[e['version'] for e in engines]}")

    for entry in reversed(engines):
        if _has_uat(entry["path"]):
            return entry["version"], Path(entry["path"])
    sys.exit("已发现引擎但都缺少 RunUAT")


def _uat_command(
    uat: Path,
    *,
    platform_name: str,
    config: str,
    target: str,
    archive_dir: Path,
    iterative: bool,
    maps: Optional[List[str]],
    extra: List[str],
) -> List[str]:
    args = [
        str(uat),
        "BuildCookRun",
        f"-project={UPROJECT_PATH}",
        "-noP4",
        f"-platform={platform_name}",
        f"-clientconfig={config}",
        f"-target={target}",
        "-build",
        "-cook",
        "-stage",
        "-pak",
        "-package",
        "-archive",
        f"-archivedirectory={archive_dir}",
        "-utf8output",
        "-unattended",
    ]
    if iterative:
        args.append("-iterativecooking")
    if maps:
        args.append("-map=" + "+".join(maps))
    args.extend(extra)
    if _SYSTEM == "Windows":
        return ["cmd", "/c"] + args
    return args


def _package_one(cmd: List[str], dry_run: bool) -> int:
    printable = subprocess.list2cmdline(cmd) if _SYSTEM == "Windows" else " ".join(cmd)
    print(f"[package] {printable}", flush=True)
    if dry_run:
        return 0
    env = os.environ.copy()
    # 5.1 等引擎自带 dotnet；不覆盖已有 PATH，只保证 UAT 能找到
    completed = subprocess.run(cmd, cwd=str(NEXUS_UNREAL_DIR), env=env)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="NexusUnreal 任意平台打包（RunUAT BuildCookRun）",
        allow_abbrev=False,
        epilog="`--` 之后的参数原样转给 UAT，例如：--platform Android -- -cookflavor=ASTC",
    )
    parser.add_argument(
        "--platform",
        nargs="+",
        default=None,
        help="目标平台，可多个或逗号分隔。默认本机（Win64 / Mac / Linux）。"
             "别名：win/windows、mac/macos、linux、android、ios、tvos、linuxarm64。"
             "未识别名称原样传给 UAT。",
    )
    parser.add_argument(
        "--config",
        default="Development",
        help="客户端配置：Development（默认，可开 MCP）/ DebugGame / Test / Shipping。",
    )
    parser.add_argument(
        "--target",
        default=DEFAULT_TARGET,
        help=f"UAT -target（默认 {DEFAULT_TARGET}）。",
    )
    parser.add_argument(
        "--ue-root",
        default=os.environ.get("NEXUS_UE_ROOT"),
        help="引擎安装根目录。省略则按 --version / EngineAssociation 自动探测。",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="引擎版本标签，如 UE_5.7 或 5.7。省略则用 uproject EngineAssociation。",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="UAT -archivedirectory（默认 Saved/Packages/<Config>；其下再按平台分子目录）。",
    )
    parser.add_argument(
        "--map",
        action="append",
        dest="maps",
        default=None,
        help="额外要 cook 的关卡（可重复）。省略则用工程 Packaging 设置。",
    )
    parser.add_argument(
        "--iterative",
        action="store_true",
        help="增量 cook（-iterativecooking）。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印 UAT 命令，不执行。",
    )
    args, extra = parser.parse_known_args()
    if extra and extra[0] == "--":
        extra = extra[1:]

    platforms = _split_platforms(args.platform)
    config = _normalize_config(args.config)
    ver_label, ue_root = _resolve_engine(args.ue_root, args.version)
    uat = _runuat_path(ue_root)
    archive_dir = Path(args.output) if args.output else (DEFAULT_ARCHIVE / config)
    archive_dir = archive_dir.resolve()
    if not args.dry_run:
        archive_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"[package] engine={ver_label} ({ue_root})  "
        f"platforms={platforms}  config={config}  target={args.target}",
        flush=True,
    )
    print(f"[package] archive={archive_dir}", flush=True)

    failed: List[str] = []
    for plat in platforms:
        cmd = _uat_command(
            uat,
            platform_name=plat,
            config=config,
            target=args.target,
            archive_dir=archive_dir,
            iterative=args.iterative,
            maps=args.maps,
            extra=extra,
        )
        code = _package_one(cmd, args.dry_run)
        if code != 0:
            print(f"[package] FAIL {plat} exit={code}", flush=True)
            failed.append(plat)
        else:
            print(f"[package] OK {plat}", flush=True)

    if failed:
        print(f"[package] 失败平台：{failed}", flush=True)
        return 1
    if not args.dry_run:
        print(f"[package] 完成。产物目录：{archive_dir}", flush=True)
        if config == "Development":
            print(
                "[package] Runtime MCP：启动加 -EnableNexusMcp，或包内 ~ 控制台 NexusLink.EnableMcp 1"
                "（可选 -NexusMcpPort= / -NexusWsPort= / -NexusAllowLan）",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
