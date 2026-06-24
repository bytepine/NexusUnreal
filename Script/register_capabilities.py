#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright byteyang. All Rights Reserved.
"""
register_capabilities.py — 一次性给 Capabilities/**/*.cpp 末尾自动追加
REGISTER_MCP_CAPABILITY(<ClassName>) 调用，并按目录推断 BuildTags()。

幂等：已存在的 REGISTER_MCP_CAPABILITY 不会重复追加；已声明 BuildTags 不会重写。
含条件编译守卫（如 #if WITH_UNLUA）的 cpp 会把追加代码插入守卫内的 #endif 之前。

执行后请运行 build_test.py 验证。
"""

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
NEXUS_UNREAL = SCRIPT_DIR.parent
CAP_ROOT = NEXUS_UNREAL / "Plugins" / "Developer" / "NexusLink" / "Source" / "NexusLink" / "Private" / "Capabilities"

# 目录名（含 Capabilities 下任意层级子目录）→ 默认功能分类（注：访问级别由 cap 名前缀决定）
DIR_TO_CATEGORY = {
    "AI":           "Blueprint",
    "Animation":    "Blueprint",
    "Asset":        "Editor",
    "Blueprint":    "Blueprint",
    "DataAsset":    "Data",
    "Editor":       "Editor",
    "Lua":          "Runtime",
    "Material":     "Material",
    "Property":     "Editor",
    "Runtime":      "Runtime",
    "Struct":       "Struct",
    "Widget":       "Widget",
}

WRITE_PREFIXES = {
    "create", "manage", "set", "spawn", "destroy",
    "compile", "save", "exec", "control", "interact",
    "delete", "rename",
}

CAP_NAME_OVERRIDES = {
    "get_actor_property":      "Runtime",
    "set_actor_property":      "Runtime",
    "get_widget_property":     "Widget",
    "set_widget_property":     "Widget",
    "get_asset_property":      "Editor",
    "set_asset_property":      "Editor",
    "diff_actors":             "Runtime",
    "list_actors":             "Runtime",
    "list_runtime_widgets":    "Runtime",
}

CLASS_NAME_RE = re.compile(r"^FString\s+(F\w+Capability)::GetName\(\)\s+const", re.MULTILINE)
CAP_NAME_RE   = re.compile(r"::GetName\(\)\s+const\s*\{\s*return\s+TEXT\(\"([^\"]+)\"\)", re.MULTILINE)
HAS_REGISTER  = re.compile(r"^REGISTER_MCP_CAPABILITY\(", re.MULTILINE)
HAS_BUILDTAGS = re.compile(r"::BuildTags\(\s*TArray<FString>", re.MULTILINE)

# 条件编译守卫：cpp 末尾形如 `#endif // WITH_UNLUA` 时，新代码插入它之前
GUARD_END_RE = re.compile(r"\n#endif\s*//\s*WITH_\w+\s*\n?\s*\Z", re.MULTILINE)


def access_tag(cap_name: str) -> str:
    head = cap_name.split("_", 1)[0]
    return "Write" if head in WRITE_PREFIXES else "Readonly"


def category_for(cpp_path: Path, cap_name: str) -> str:
    if cap_name in CAP_NAME_OVERRIDES:
        return CAP_NAME_OVERRIDES[cap_name]
    parts = cpp_path.parts
    for i, p in enumerate(parts):
        if p == "Capabilities" and i + 1 < len(parts):
            # 自深向浅匹配（如 Asset/Animation → Animation；Asset/Blueprint → Blueprint；Asset/DataAsset → DataAsset；Asset/Material → Material；Asset/Struct → Struct；Asset/Widget → Widget）
            for seg in reversed(parts[i + 1 : -1]):
                if seg in DIR_TO_CATEGORY:
                    return DIR_TO_CATEGORY[seg]
            return DIR_TO_CATEGORY.get(parts[i + 1], "Editor")
    return "Editor"


def find_cpp_files() -> list[Path]:
    out = []
    seen = set()
    for p in CAP_ROOT.rglob("*.cpp"):
        rp = p.resolve()
        if rp in seen: continue
        seen.add(rp)
        out.append(p)
    return sorted(out)


def patch_cpp(cpp_path: Path) -> tuple[str, str | None]:
    text = cpp_path.read_text(encoding="utf-8")

    if HAS_REGISTER.search(text):
        return ("skipped", None)

    cls_match = CLASS_NAME_RE.search(text)
    name_match = CAP_NAME_RE.search(text)
    if not cls_match or not name_match:
        return ("no_class", None)

    cls_name = cls_match.group(1)
    cap_name = name_match.group(1)

    additions = []

    if not HAS_BUILDTAGS.search(text):
        cat = category_for(cpp_path, cap_name)
        access = access_tag(cap_name)
        build_tags = (
            f"void {cls_name}::BuildTags(TArray<FString>& OutTags) const\n"
            f"{{\n"
            f"\tOutTags.Add(FNexusMcpTags::{access});\n"
            f"\tOutTags.Add(FNexusMcpTags::{cat});\n"
            f"}}\n"
        )
        additions.append(build_tags)

    additions.append(f"REGISTER_MCP_CAPABILITY({cls_name})\n")
    block = "\n" + "\n".join(additions)

    # 若 cpp 末尾有条件编译守卫（如 #endif // WITH_UNLUA），新代码插到它之前
    guard_match = GUARD_END_RE.search(text)
    if guard_match:
        insert_pos = guard_match.start()
        text = text[:insert_pos] + block + text[insert_pos:]
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += block

    cpp_path.write_text(text, encoding="utf-8", newline="\n")
    return ("registered", cap_name)


def patch_header_for_buildtags(cpp_path: Path) -> bool:
    h_path = cpp_path.with_suffix(".h")
    if not h_path.exists():
        return False
    htext = h_path.read_text(encoding="utf-8")
    if "BuildTags(" in htext:
        return False
    decl = "\tvirtual void BuildTags(TArray<FString>& OutTags) const override;\n"
    if "GetExtraSearchKeywords()" in htext:
        new = htext.replace(
            "\tvirtual TArray<FString> GetExtraSearchKeywords() const override;\n",
            "\tvirtual TArray<FString> GetExtraSearchKeywords() const override;\n" + decl,
            1,
        )
    elif "BuildSchema()" in htext:
        new = htext.replace(
            "\tvirtual TSharedPtr<FJsonObject> BuildSchema() const override;\n",
            "\tvirtual TSharedPtr<FJsonObject> BuildSchema() const override;\n" + decl,
            1,
        )
    else:
        return False
    h_path.write_text(new, encoding="utf-8", newline="\n")
    return True


def ensure_includes(cpp_path: Path):
    text = cpp_path.read_text(encoding="utf-8")
    needed = []
    if "#include \"NexusCapabilityRegistry.h\"" not in text:
        needed.append("#include \"NexusCapabilityRegistry.h\"")
    if "#include \"NexusMcpTool.h\"" not in text and "FNexusMcpTags" in text:
        needed.append("#include \"NexusMcpTool.h\"")
    if not needed:
        return False
    lines = text.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("#include"):
            insert_at = i + 1
    for inc in reversed(needed):
        lines.insert(insert_at, inc + "\n")
    cpp_path.write_text("".join(lines), encoding="utf-8", newline="\n")
    return True


def main() -> int:
    files = find_cpp_files()
    print(f"Found {len(files)} cap .cpp files under {CAP_ROOT}")

    cap_names_seen: dict[str, Path] = {}
    stats = {"registered": 0, "skipped": 0, "no_class": 0, "headers_patched": 0, "includes_patched": 0}
    duplicates: list[tuple[str, Path, Path]] = []

    for cpp in files:
        status, cap_name = patch_cpp(cpp)
        stats[status] += 1
        if status == "registered" and cap_name:
            if cap_name in cap_names_seen:
                duplicates.append((cap_name, cap_names_seen[cap_name], cpp))
            else:
                cap_names_seen[cap_name] = cpp

            if patch_header_for_buildtags(cpp):
                stats["headers_patched"] += 1
            if ensure_includes(cpp):
                stats["includes_patched"] += 1

    print(f"\nResults: {stats}")

    if duplicates:
        print(f"\n[WARN] {len(duplicates)} duplicate cap name(s):")
        for n, a, b in duplicates:
            print(f"   '{n}': {a.relative_to(NEXUS_UNREAL)}  ↔  {b.relative_to(NEXUS_UNREAL)}")
        return 1

    print(f"\nAll {len(cap_names_seen)} cap names are unique.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
