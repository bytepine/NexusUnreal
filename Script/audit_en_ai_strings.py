#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 Capability 目录中仍含英文、无中文的 AI 可见 error/fatal 字符串。"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CAP = ROOT / "nexus-unreal/Plugins/Developer/NexusLink/Source/NexusLink/Private/Capabilities"

pat = re.compile(r'(?:SetStringField\(TEXT\("error"\)|OutError\s*=|MakeFatal\(|AddEntryError\()\s*(?:FString::Printf\()?TEXT\("([^"]+)"\)')


def has_cjk(s: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in s)


def main() -> None:
    found: dict[str, int] = {}
    for f in sorted(CAP.rglob("*.cpp")):
        t = f.read_text(encoding="utf-8", errors="replace")
        for m in pat.finditer(t):
            s = m.group(1)
            if has_cjk(s):
                continue
            if not re.search(r"[A-Za-z]{3,}", s):
                continue
            found[s] = found.get(s, 0) + 1
    print(f"unique untranslated error templates: {len(found)}")
    for s, n in sorted(found.items(), key=lambda x: (-x[1], x[0])):
        print(f"{n:3d}\t{s}")


if __name__ == "__main__":
    main()
