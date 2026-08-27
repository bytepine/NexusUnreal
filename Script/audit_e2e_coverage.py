#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright byteyang. All Rights Reserved.
"""对照 C++ RegisterActions / GetSectionNames 与 pytest 是否点到每个 action / named section。

不启动 UE。缺项 exit 1。

用法（在 nexus-unreal 下）:
  py Script/audit_e2e_coverage.py
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAP_ROOT = ROOT / "Plugins" / "Developer" / "NexusLink" / "Source" / "NexusLink" / "Private" / "Capabilities"
TESTS = ROOT / "Tests"

NAME_RE = re.compile(r'Out\.Name\s*=\s*TEXT\(\s*"([^"]+)"\s*\)')
HANDLER_RE = re.compile(r'OutHandlers\.Add\(\s*TEXT\(\s*"([^"]+)"\s*\)')
SECTION_RE = re.compile(r'GetSectionNames\(\)[^{]*\{([^}]+)\}', re.S)
TEXT_RE = re.compile(r'TEXT\(\s*"([^"]+)"\s*\)')
ENUM_BLOCK_RE = re.compile(
    r'FNexusSchema::Enum\(\s*(?:TEXT\("[^"]*"\)\s*,\s*)?\{\s*((?:TEXT\("[^"]+"\)\s*,?\s*)+)\}',
    re.S,
)
ACTION_IN_TEST_RE = re.compile(r'["\']action["\']\s*:\s*["\']([^"\']+)["\']')
SECTIONS_IN_TEST_RE = re.compile(r'sections\s*=\s*\[([^\]]+)\]')
CAP_CALL_RE = re.compile(r'["\']((?:manage|get|create|interact)_[a-z0-9_]+)["\']')


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def collect_cpp() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    manage: dict[str, list[str]] = {}
    sections: dict[str, list[str]] = {}
    for p in CAP_ROOT.rglob("*.cpp"):
        txt = _read(p)
        names = NAME_RE.findall(txt)
        if not names:
            continue
        cap = names[0]
        if cap.startswith("manage_"):
            actions = HANDLER_RE.findall(txt)
            if not actions:
                # pose_search 等无 Enum / 仅 handler 名写在 HandlePS_*
                for blk in ENUM_BLOCK_RE.findall(txt):
                    actions.extend(TEXT_RE.findall(blk))
                actions = [a for a in actions if a not in ("Action", "Action type", "Operation type", "Write operation")]
            # 去重保序
            seen = set()
            uniq = []
            for a in actions:
                if a not in seen and a not in ("Action", "Socket operation"):
                    seen.add(a)
                    uniq.append(a)
            if uniq:
                manage[cap] = uniq
        if cap.startswith("get_") or cap == "get_editor_context" or cap == "get_gameplay_tags":
            m = SECTION_RE.search(txt)
            if m:
                secs = [s for s in TEXT_RE.findall(m.group(1)) if s and s != "all"]
                if secs:
                    sections[cap] = secs
    return manage, sections


def collect_tests() -> tuple[dict[str, set[str]], dict[str, set[str]], set[str]]:
    file_actions: dict[str, set[str]] = defaultdict(set)
    file_sections: dict[str, set[str]] = defaultdict(set)
    mentioned_caps: set[str] = set()
    for p in TESTS.rglob("test_*.py"):
        txt = _read(p)
        mentioned_caps.update(CAP_CALL_RE.findall(txt))
        acts = set(ACTION_IN_TEST_RE.findall(txt))
        file_caps = set(CAP_CALL_RE.findall(txt))
        for cap in file_caps:
            file_actions[cap] |= acts
        for blk in SECTIONS_IN_TEST_RE.findall(txt):
            for s in re.findall(r'["\']([^"\']+)["\']', blk):
                for cap in file_caps:
                    if cap.startswith("get_"):
                        file_sections[cap].add(s)
    return file_actions, file_sections, mentioned_caps


def main() -> int:
    manage, sections = collect_cpp()
    file_actions, file_sections, mentioned = collect_tests()

    missing_actions: list[str] = []
    for cap, acts in sorted(manage.items()):
        tested = file_actions.get(cap, set())
        for a in acts:
            if a not in tested:
                missing_actions.append(f"{cap}  {a}")

    missing_sections: list[str] = []
    for cap, secs in sorted(sections.items()):
        tested = file_sections.get(cap, set())
        for s in secs:
            if s not in tested and "all" not in tested:
                missing_sections.append(f"{cap}  {s}")

    print(f"manage caps: {len(manage)}  actions: {sum(len(v) for v in manage.values())}")
    print(f"get MultiSection: {len(sections)}  named sections: {sum(len(v) for v in sections.values())}")
    print(f"missing actions: {len(missing_actions)}")
    print(f"missing sections: {len(missing_sections)}")
    if missing_actions:
        print("\n=== missing manage actions ===")
        print("\n".join(missing_actions))
    if missing_sections:
        print("\n=== missing get sections ===")
        print("\n".join(missing_sections))
    return 1 if missing_actions or missing_sections else 0


if __name__ == "__main__":
    sys.exit(main())
