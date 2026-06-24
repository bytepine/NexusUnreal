#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""委托 NexusLink 子模块 scripts/build_tool_reference.py。"""
import runpy
from pathlib import Path

_TARGET = (
    Path(__file__).resolve().parent.parent
    / "Plugins/Developer/NexusLink/scripts/build_tool_reference.py"
)
if not _TARGET.is_file():
    raise SystemExit(f"ERROR: {_TARGET} not found（请初始化 NexusLink 子模块）")

runpy.run_path(str(_TARGET), run_name="__main__")
