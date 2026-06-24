#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-shot: wrap listed capability .cpp files in #if WITH_EDITOR (skip if already wrapped)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "Plugins/Developer/NexusLink/Source/NexusLink/Private"

FILES = [
    "Capabilities/Editor/NexusControlPieCapability.cpp",
    "Capabilities/Editor/NexusExecCommandCapability.cpp",
    "Capabilities/Editor/NexusGetEditorInfoCapability.cpp",
    "Capabilities/Editor/NexusCaptureViewportCapability.cpp",
    "Capabilities/Editor/NexusGetGameplayTagsCapability.cpp",
    "Capabilities/Editor/NexusGetOutputLogCapability.cpp",
    "Capabilities/Editor/NexusSetLogCaptureFilterCapability.cpp",
    "Capabilities/Editor/NexusSearchConsoleVariablesCapability.cpp",
    "Capabilities/Editor/Context/NexusGetEditorContextCapability.cpp",
    "Capabilities/Asset/NexusDeleteAssetCapability.cpp",
    "Capabilities/Asset/NexusDuplicateAssetCapability.cpp",
    "Capabilities/Asset/NexusRenameAssetCapability.cpp",
    "Capabilities/Asset/NexusReimportAssetCapability.cpp",
    "Capabilities/Asset/NexusExportAssetCapability.cpp",
    "Capabilities/Asset/Material/NexusGetAssetMaterialCapability.cpp",
    "Capabilities/Asset/Material/NexusManageAssetMaterialCapability.cpp",
    "Capabilities/Runtime/Widget/NexusSpawnRuntimeWidgetCapability.cpp",
]


def wrap_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "#if WITH_EDITOR" in text.split("\n", 8)[0:8]:
        # already has early WITH_EDITOR in first lines after header - check full wrap
        if text.rstrip().endswith("#endif // WITH_EDITOR") or text.rstrip().endswith("#endif"):
            if "REGISTER_MCP_CAPABILITY" in text and "#if WITH_EDITOR\n" in text:
                return False
    lines = text.splitlines(keepends=True)
    if len(lines) < 2:
        return False
    # First `#include "....Capability.h"` stays outside the guard
    idx = None
    for i, line in enumerate(lines):
        if '#include "' in line and "Capability.h" in line:
            idx = i + 1
            break
    if idx is None:
        print(f"SKIP (no capability include): {path}")
        return False
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    body = "".join(lines[idx:])
    if body.lstrip().startswith("#if WITH_EDITOR"):
        return False
    header = "".join(lines[:idx])
    wrapped = header + "\n#if WITH_EDITOR\n\n" + body.rstrip() + "\n\n#endif // WITH_EDITOR\n"
    path.write_text(wrapped, encoding="utf-8")
    return True


def main() -> None:
    changed = 0
    for rel in FILES:
        p = ROOT / rel
        if not p.is_file():
            print(f"MISSING: {rel}")
            continue
        if wrap_file(p):
            print(f"WRAPPED: {rel}")
            changed += 1
    print(f"Done. {changed} file(s) updated.")


if __name__ == "__main__":
    main()
