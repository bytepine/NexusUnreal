# Copyright byteyang. All Rights Reserved.
"""Reusable assertion helpers for MCP tool responses.

Capability 响应形状：
  - 单条 Entries：字段已提升到顶层（无 results 信封）
  - 多条 Entries：{ "results": [ {...}, ... ] }
  - 部分 manage：提升后顶层仍有内嵌 results[]（操作子结果）

测试通过 cap_entries / cap_first 兼容两种形状。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from _framework.mcp_client import cap_entries


def assert_batch_success(result: Dict[str, Any], expected_count: Optional[int] = None,
                         *, context: str = "") -> None:
    """Fail if any capability entry has an error field."""
    ctx = f" ({context})" if context else ""
    results = cap_entries(result)
    assert results, f"missing capability entries{ctx}: {result!r}"
    errors = [r for r in results if isinstance(r, dict) and r.get("error")]
    assert not errors, f"batch had failures{ctx}: {errors!r}"
    if expected_count is not None:
        assert len(results) == expected_count, (
            f"expected {expected_count} results{ctx}, got {len(results)}: {results!r}"
        )
    sc = result.get("successCount")
    if sc is not None and expected_count is not None:
        assert sc == expected_count, (
            f"successCount={sc}, expected {expected_count}{ctx}: {result!r}"
        )


def assert_success_count(result: Dict[str, Any], expected: int, *, context: str = "") -> None:
    ctx = f" ({context})" if context else ""
    sc = result.get("successCount")
    if sc is None:
        # 新版批量 API 不再返回 successCount，回退到统计 entry 中无 error 且未显式 success:false
        results = cap_entries(result)
        sc = sum(
            1
            for r in results
            if isinstance(r, dict) and not r.get("error") and r.get("success") is not False
        )
    assert sc == expected, f"successCount={sc}, expected {expected}{ctx}: {result!r}"


def pluck_errors(result: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for r in cap_entries(result):
        if isinstance(r, dict) and r.get("error"):
            out.append(str(r["error"]))
    return out


def ids_of(result: Dict[str, Any], key: str = "nodeId") -> List[str]:
    """Collect an id field from each capability entry (missing → skipped)."""
    out: List[str] = []
    for r in cap_entries(result):
        if isinstance(r, dict):
            v = r.get(key)
            if isinstance(v, str):
                out.append(v)
    return out


def assert_in(haystack: Iterable[Any], needle: Any, *, context: str = "") -> None:
    items = list(haystack)
    assert needle in items, f"expected {needle!r} in {items!r} ({context})"


def merge_with_defaults(
    items: List[Dict[str, Any]],
    defaults: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Merge `<prefix>_defaults` dict back into list entries.

    Response compaction semantics:
      - defaults holds the majority value per field
      - entries omit a field iff entry.value == defaults.value
      - merge rule: `{**defaults, **entry}` (entry overrides when present)
    """
    merged: List[Dict[str, Any]] = []
    for entry in items:
        if not isinstance(entry, dict):
            merged.append(entry)
            continue
        combined: Dict[str, Any] = dict(defaults) if defaults else {}
        combined.update(entry)
        merged.append(combined)
    return merged


def assert_respecting_defaults(
    result: Dict[str, Any],
    list_key: str,
    defaults_prefix: str,
    *,
    required_fields: Optional[Iterable[str]] = None,
    context: str = "",
) -> List[Dict[str, Any]]:
    """Assert defaults shape and return merged entries.

    Verifies:
      - `<list_key>` is a list of dicts
      - if `<defaults_prefix>_defaults` is present, it is a dict
      - after merging defaults back in, each entry contains every name in
        `required_fields`
    """
    ctx = f" ({context})" if context else ""
    items = result.get(list_key)
    assert isinstance(items, list), f"missing list '{list_key}'{ctx}: {result!r}"

    defaults_key = f"{defaults_prefix}_defaults"
    defaults = result.get(defaults_key) or {}
    if defaults:
        assert isinstance(defaults, dict), f"{defaults_key} must be a dict{ctx}"

    merged = merge_with_defaults(items, defaults)
    if required_fields:
        for i, entry in enumerate(merged):
            missing = [f for f in required_fields if f not in entry]
            assert not missing, (
                f"{list_key}[{i}] missing fields {missing!r} after merge{ctx}: "
                f"entry={items[i]!r} defaults={defaults!r}"
            )
    return merged
