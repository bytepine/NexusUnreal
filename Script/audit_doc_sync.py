#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计：代码 Capability 与 README / tool-reference / ZH_DESCRIPTIONS 对齐。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAP_DIR = REPO / "nexus-unreal/Plugins/Developer/NexusLink/Source/NexusLink/Private/Capabilities"
README = REPO / "nexus-unreal/README.md"
TOOL_REF = REPO / "docs/tool-reference.md"
BUILD_SCRIPT = REPO / "nexus-unreal/Script/build_tool_reference.py"

RE_NAME = re.compile(r'Out\.Name\s*=\s*TEXT\("([^"]+)"\)')
RE_DESC = re.compile(r'Out\.Description\s*=\s*TEXT\("([^"]+)"\)')
RE_README_CAP = re.compile(
    r"`((?:get|manage|create|search|list|set|spawn|destroy|diff|interact|eval|"
    r"dofile|gc|hotreload|compile|export|reimport|rename|duplicate|delete|save|"
    r"call|submit|capture|control|exec)_[a-z0-9_]+)`"
)
RE_TOOL_HEAD = re.compile(r"^### `([^`]+)`", re.M)
RE_ZH_KEY = re.compile(r'^\s+"([a-z][a-z0-9_]+)":', re.M)

META = {"search_capabilities", "call_capability", "submit_feedback"}

# README 行应提及的关键 action/能力（代码 schema 中存在）
README_FEATURE_TOKENS: dict[str, list[str]] = {
    "manage_asset_user_widget": ["set_slot", "set_property"],
    "manage_asset_level": ["spawn_actor", "remove_actor", "set_actor_property"],
    "manage_asset_sound_cue": ["add_node", "remove_node", "connect_nodes"],
    "manage_asset_niagara_system": ["set_user_parameter"],
    "manage_asset_data_asset": ["reset"],
    "manage_asset_behavior_tree": ["move_node", "set_property"],
    "manage_asset_blackboard": ["enum"],
    "interact_runtime_widget": ["ProgressBar", "EditableText"],
    "get_asset_user_widget": ["layout"],
    "save_asset": ["deferred", "SaveDirtyPackage"],
}


def load_caps() -> dict[str, dict]:
    caps: dict[str, dict] = {}
    for cpp in sorted(CAP_DIR.rglob("*Capability.cpp")):
        text = cpp.read_text(encoding="utf-8", errors="ignore")
        m = RE_NAME.search(text)
        if not m:
            continue
        name = m.group(1)
        d = RE_DESC.search(text)
        caps[name] = {
            "file": str(cpp.relative_to(REPO)).replace("\\", "/"),
            "text": text,
            "description": d.group(1) if d else "",
        }
    return caps


def load_zh_descriptions() -> set[str]:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    start = text.index("ZH_DESCRIPTIONS: dict[str, str] = {")
    end = text.index("\nZH_WHEN_TO_USE:", start)
    return set(RE_ZH_KEY.findall(text[start:end]))


def load_readme_caps() -> dict[str, str]:
    text = README.read_text(encoding="utf-8")
    if "## 功能列表" in text:
        text = text.split("## 功能列表", 1)[1]
    lines: dict[str, str] = {}
    for line in text.splitlines():
        if "- [x]" not in line:
            continue
        for m in RE_README_CAP.finditer(line):
            name = m.group(1)
            # 同名 cap 保留更长的描述行（避免简写索引行覆盖详述）
            prev = lines.get(name, "")
            if len(line) > len(prev):
                lines[name] = line
    return lines


def load_tool_ref() -> set[str]:
    return set(RE_TOOL_HEAD.findall(TOOL_REF.read_text(encoding="utf-8")))


def find_readme_stale(readme_lines: dict[str, str], caps: dict[str, dict]) -> list[str]:
    out: list[str] = []
    for cap, tokens in README_FEATURE_TOKENS.items():
        if cap not in caps:
            continue
        line = readme_lines.get(cap, "")
        src = caps[cap]["text"]
        for tok in tokens:
            if tok in src and tok not in line:
                out.append(f"{cap}: 代码含 `{tok}`，README 行未写")
    return sorted(out)


def section(title: str, items: list[str], caps: dict[str, dict] | None = None, limit: int = 80):
    print(f"## {title} ({len(items)})")
    for x in items[:limit]:
        extra = ""
        if caps and x in caps:
            extra = f" — {caps[x]['description'][:70]}"
        print(f"  - {x}{extra}")
    if len(items) > limit:
        print(f"  ... +{len(items) - limit} more")
    print()


def main() -> int:
    caps = load_caps()
    code_names = set(caps)
    readme_lines = load_readme_caps()
    readme = set(readme_lines)
    tool_ref = load_tool_ref()
    zh = load_zh_descriptions()
    tool_ref_caps = tool_ref - META

    print(f"代码 Capability: {len(code_names)}")
    print(f"README 功能点: {len(readme)}")
    print(f"tool-reference: {len(tool_ref)} (cap {len(tool_ref_caps)} + meta {len(tool_ref & META)})")
    print(f"ZH_DESCRIPTIONS: {len(zh)}")
    print()

    section("代码有、README 无", sorted(code_names - readme), caps)
    section("README 有、代码无", sorted(readme - code_names))
    section("代码有、tool-reference 无", sorted(code_names - tool_ref_caps), caps)
    section("tool-reference 有、代码无", sorted(tool_ref_caps - code_names))
    section("代码有、ZH_DESCRIPTIONS 无", sorted(code_names - zh), caps)
    section("ZH_DESCRIPTIONS 无对应代码", sorted(zh - code_names - META))
    section("README 功能描述缺项", find_readme_stale(readme_lines, caps))

    # GAS caps conditional
    gas = sorted(n for n in code_names if "gameplay" in n or "attribute_set" in n)
    section("GAS 相关 Capability（WITH_GAS）", gas, caps)

    # 域目录计数 vs AI_NAVIGATION
    by_dir: dict[str, list[str]] = {}
    for name, info in caps.items():
        rel = Path(info["file"]).relative_to("nexus-unreal/Plugins/Developer/NexusLink/Source/NexusLink/Private/Capabilities")
        parts = rel.parts
        key = parts[0] if len(parts) == 2 else f"{parts[0]}/{parts[1]}"
        by_dir.setdefault(key, []).append(name)
    print("## 域目录 Capability 计数")
    for k in sorted(by_dir):
        print(f"  {len(by_dir[k]):3}  {k}")
    print(f"  SUM {sum(len(v) for v in by_dir.values())}")
    print()

    # ZH_WHEN_TO_USE 覆盖
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    start = text.index("ZH_WHEN_TO_USE: dict[str, str] = {")
    end = text.index("\n\n# ── Regex", start)
    when = set(RE_ZH_KEY.findall(text[start:end]))
    section("代码有、ZH_WHEN_TO_USE 无", sorted(code_names - when), caps)

    return 0


if __name__ == "__main__":
    sys.exit(main())
