#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
from pathlib import Path

CAP = Path(__file__).resolve().parent.parent.parent / (
    "nexus-unreal/Plugins/Developer/NexusLink/Source/NexusLink/Private/Capabilities"
)
pat = re.compile(r'TEXT\("((?:[^"\\]|\\.)*)"\)')

def has_cjk(s: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in s)

def main() -> None:
    found: dict[str, int] = {}
    for f in sorted(CAP.rglob("*.cpp")):
        t = f.read_text(encoding="utf-8")
        for m in pat.finditer(t):
            s = m.group(1).replace('\\"', '"')
            if has_cjk(s):
                continue
            if not re.search(r"[A-Za-z]{4,}", s):
                continue
            if s.startswith("/Game") or s.startswith("get_"):
                continue
            found[s] = found.get(s, 0) + 1
    print(len(found))
    for s, n in sorted(found.items(), key=lambda x: (-x[1], x[0])):
        if any(k in s.lower() for k in ("required", "not found", "failed", "hint", "error", "only ", "must ", "invalid", "unsupported", "missing", "cannot")):
            print(f"{n}\t{s}")

if __name__ == "__main__":
    main()
