#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract FNexusSchema description TEXT strings from capability/tool C++ sources."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN_PRIVATE = (
    REPO
    / "nexus-unreal"
    / "Plugins"
    / "Developer"
    / "NexusLink"
    / "Source"
    / "NexusLink"
    / "Private"
)

METHODS = ("Str", "Int", "Num", "Bool", "Enum", "StrArr", "ArrayOf", "AnyObject")
METHOD_ALT = "|".join(METHODS)

# First TEXT("...") after FNexusSchema::<Method>(
DESC_RE = re.compile(
    rf"FNexusSchema::(?:{METHOD_ALT})\s*\(\s*TEXT\s*\(\s*\"((?:\\.|[^\"\\])*)\"",
    re.MULTILINE,
)

OUT_PATH = Path(__file__).resolve().parent / "schema_descs_en.txt"


def decode_c_string(raw: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(raw):
        if raw[i] == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == '"':
                out.append('"')
            elif nxt == "\\":
                out.append("\\")
            else:
                out.append(nxt)
            i += 2
        else:
            out.append(raw[i])
            i += 1
    return "".join(out)


def iter_source_files() -> list[Path]:
    caps = PLUGIN_PRIVATE / "Capabilities"
    tools = PLUGIN_PRIVATE / "Tools"
    files: list[Path] = []
    if caps.is_dir():
        files.extend(sorted(caps.rglob("*.cpp")))
    if tools.is_dir():
        files.extend(sorted(tools.glob("NexusMcpTool*.cpp")))
    return files


def main() -> None:
    counts: Counter[str] = Counter()
    for path in iter_source_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in DESC_RE.finditer(text):
            counts[decode_c_string(m.group(1))] += 1

    lines = [f"{n:4d}\t{s}" for s, n in counts.most_common()]
    OUT_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    unique = len(counts)
    ascii_only = sum(1 for s in counts if s.isascii())
    print(f"unique_strings={unique}")
    print(f"ascii_only={ascii_only}")
    print(f"output={OUT_PATH}")


if __name__ == "__main__":
    main()
