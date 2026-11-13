#!/usr/bin/env python3
"""验证 UE 基线实际执行；JUnit 缺失、失败或关键用例跳过均不能通过。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


# 这些现有用例没有 GUI 标记；Automation 用例验证真实 C++ 运行结果。
REQUIRED = {
    "test_00_smoke": (
        "test_proxy_discovery_status",
        "test_tools_list_contains_meta_tools",
        "test_call_capability_editor_info",
    ),
    "test_15_editor_operations": (
        "test_editor_operation_unknown_id",
        *(
            f"test_editor_automation_local_run[{name}]"
            for name in (
                "NexusLink.EditorOperations.OwnerAndContract",
                "NexusLink.Review.ScsReattachAndCopy",
                "NexusLink.Review.TransformValidation",
                "NexusLink.Review.DirtyLevelProtection",
                "NexusLink.Runtime.Widget.ExactInteraction",
            )
        ),
    ),
}
GUI_REQUIRED = (
    "test_editor_slate_read_and_capture",
    "test_editor_slate_advanced_interactions",
)


def check_report(path: Path, mode: str = "headless") -> dict:
    cases = list(ET.parse(path).getroot().iter("testcase"))
    errors = []
    failed = [case for case in cases if case.find("failure") is not None or case.find("error") is not None]
    skipped = [case for case in cases if case.find("skipped") is not None]
    if not cases:
        errors.append("JUnit contains no test cases")
    if failed:
        errors.append(f"JUnit contains {len(failed)} failed/error test cases")
    required = {module: list(names) for module, names in REQUIRED.items()}
    if mode == "gui":
        required["test_15_editor_operations"].extend(GUI_REQUIRED)
    for module, names in required.items():
        for name in names:
            matches = [case for case in cases if case.get("name") == name and
                       (case.get("classname") == module or case.get("classname", "").endswith("." + module))]
            if len(matches) != 1:
                errors.append(f"Expected exactly one result: {module}::{name}; found {len(matches)}")
            elif any(matches[0].find(tag) is not None for tag in ("failure", "error", "skipped")):
                errors.append(f"Required case did not pass: {module}::{name}")
    return {"mode": mode, "tests": len(cases), "passed": len(cases) - len(failed) - len(skipped),
            "failed": len(failed), "skipped": len(skipped), "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--mode", choices=("headless", "gui"), default="headless")
    args = parser.parse_args()
    try:
        result = check_report(args.report, args.mode)
    except (OSError, ET.ParseError) as exc:
        result = {"errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(result["errors"]))


if __name__ == "__main__":
    sys.exit(main())
