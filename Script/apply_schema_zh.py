#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 FNexusSchema 参数描述 TEXT 批量替换为中文（读取 schema_descs_zh.json）。"""
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent.parent
CAP_DIR = REPO / "nexus-unreal/Plugins/Developer/NexusLink/Source/NexusLink/Private"
ZH_MAP: dict[str, str] = json.loads((SCRIPT_DIR / "schema_descs_zh.json").read_text(encoding="utf-8"))

# 仅替换 FNexusSchema:: 调用内的 TEXT("...")
RE_FN_SCHEMA_TEXT = re.compile(
    r'(FNexusSchema::(?:Str|Int|Num|Bool|Enum|StrArr|ArrayOf|AnyObject)\([^)]*?TEXT\(")([^"]+)("\))',
    re.DOTALL,
)


def has_cjk(s: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in s)


def process_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        en = m.group(2)
        if en in ZH_MAP and ZH_MAP[en] != en:
            n += 1
            return m.group(1) + ZH_MAP[en] + m.group(3)
        return m.group(0)

    new_text = RE_FN_SCHEMA_TEXT.sub(repl, text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return n


def main() -> int:
    total = 0
    files = list((CAP_DIR / "Capabilities").rglob("*.cpp")) + list((CAP_DIR / "Tools").glob("NexusMcpTool*.cpp"))
    for f in sorted(files):
        c = process_file(f)
        if c:
            print(f"{f.name}: {c}")
            total += c
    print(f"\nTotal replacements: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
