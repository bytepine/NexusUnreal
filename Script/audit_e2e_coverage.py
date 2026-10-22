#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright byteyang. All Rights Reserved.
"""对照 C++ RegisterActions / GetSectionNames 与 pytest 是否点到每个 action / named section。

不启动 UE。缺项 exit 1。

用法（在 nexus-unreal 下）:
  py Script/audit_e2e_coverage.py
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAP_ROOTS = tuple(
    ROOT / "Plugins" / plugin / "Source" / module / "Private" / "Capabilities"
    for plugin in ("NexusLink", "NexusLinkExt")
    for module in (plugin, plugin + "Editor")
)
TESTS = ROOT / "Tests"

NAME_RE = re.compile(r'Out\.Name\s*=\s*TEXT\(\s*"([^"]+)"\s*\)')
HANDLER_RE = re.compile(r'OutHandlers\.Add\(\s*TEXT\(\s*"([^"]+)"\s*\)')
SECTION_RE = re.compile(r'GetSectionNames\(\)[^{]*\{([^}]+)\}', re.S)
TEXT_RE = re.compile(r'TEXT\(\s*"([^"]+)"\s*\)')
ENUM_BLOCK_RE = re.compile(
    r'FNexusSchema::Enum\(\s*(?:TEXT\("[^"]*"\)\s*,\s*)?\{\s*((?:TEXT\("[^"]+"\)\s*,?\s*)+)\}',
    re.S,
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def collect_cpp(roots=CAP_ROOTS) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    manage: dict[str, list[str]] = {}
    sections: dict[str, list[str]] = {}
    for p in sorted(p for root in roots for p in root.rglob("*.cpp")):
        txt = _read(p)
        names = NAME_RE.findall(txt)
        if not names:
            continue
        if len(set(names)) != 1:
            raise ValueError(f"{p}: expected one capability definition, found {names}")
        cap = names[0]
        # 部分能力将 section 列表内联在同名头文件里。
        if p.with_suffix(".h").is_file():
            txt += "\n" + _read(p.with_suffix(".h"))
        if cap.startswith("Manage"):
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
        if cap.startswith("Get") or cap == "GetEditorContext" or cap == "GetGameplayTags":
            m = SECTION_RE.search(txt)
            if m:
                secs = [s for s in TEXT_RE.findall(m.group(1)) if s and s != "All"]
                if secs:
                    sections[cap] = secs
    return manage, sections


def _expand(node, bindings, seen=frozenset()):
    """只解析源码中的静态值，不导入测试模块或执行测试代码。"""
    if isinstance(node, ast.Name) and node.id in bindings and node.id not in seen:
        yield from _expand(bindings[node.id], bindings, seen | {node.id})
    elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for item in node.elts:
            yield from _expand(item, bindings, seen)
    else:
        yield node


def _strings(node, bindings):
    return {
        value.value for value in _expand(node, bindings)
        if isinstance(value, ast.Constant) and isinstance(value.value, str)
    }


def _freeze(node, bindings, seen=frozenset()):
    """保存当前静态值，避免后续循环变量变化重写已经追加的操作。"""
    if isinstance(node, ast.Name) and node.id in bindings and node.id not in seen:
        return _freeze(bindings[node.id], bindings, seen | {node.id})
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return type(node)(elts=[_freeze(item, bindings, seen) for item in node.elts])
    if isinstance(node, ast.Dict):
        return ast.Dict(
            keys=[_freeze(key, bindings, seen) if key is not None else None for key in node.keys],
            values=[_freeze(value, bindings, seen) for value in node.values],
        )
    return node


def _fields(node, key, bindings):
    for value in _expand(node, bindings):
        if isinstance(value, ast.Dict):
            for k, v in zip(value.keys, value.values):
                if k is None:
                    yield from _fields(v, key, bindings)
                elif isinstance(k, ast.Constant) and k.value == key:
                    yield v


class CoverageVisitor(ast.NodeVisitor):
    def __init__(self, aliases):
        self.aliases = aliases
        self.bindings = {}
        self.actions = defaultdict(set)
        self.sections = defaultdict(set)
        self.mentioned = set()

    def visit_FunctionDef(self, node):
        previous = self.bindings
        contexts = [dict(previous)]
        for decorator in node.decorator_list:
            if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "parametrize" and len(decorator.args) >= 2):
                names_node = _freeze(decorator.args[0], previous)
                if isinstance(names_node, ast.Constant) and isinstance(names_node.value, str):
                    names = [name.strip() for name in names_node.value.split(",")]
                elif isinstance(names_node, (ast.List, ast.Tuple)) and all(
                        isinstance(name, ast.Constant) and isinstance(name.value, str) for name in names_node.elts):
                    names = [name.value for name in names_node.elts]
                else:
                    continue
                expanded = []
                for context in contexts:
                    self.bindings = context
                    expanded.extend(context | row for row in self._parameter_rows(names, decorator.args[1]))
                contexts = expanded
        for context in contexts:
            self.bindings = context
            for stmt in node.body:
                self.visit(stmt)
        self.bindings = previous

    visit_AsyncFunctionDef = visit_FunctionDef

    def _parameter_rows(self, names, values):
        values = _freeze(values, self.bindings)
        if not names or not isinstance(values, (ast.List, ast.Tuple, ast.Set)):
            # 动态迭代器无法静态展开，仍检查循环体内不依赖迭代值的调用。
            return [{name: ast.Name(id=name) for name in names}]
        rows = []
        for row in values.elts:
            if len(names) == 1:
                rows.append({names[0]: row})
            elif isinstance(row, (ast.List, ast.Tuple)) and len(row.elts) == len(names):
                rows.append(dict(zip(names, row.elts)))
        return rows

    def visit_Assign(self, node):
        self.visit(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.bindings[target.id] = _freeze(node.value, self.bindings)

    def visit_AnnAssign(self, node):
        if node.value is not None:
            self.visit(node.value)
            if isinstance(node.target, ast.Name):
                self.bindings[node.target.id] = _freeze(node.value, self.bindings)

    def visit_AugAssign(self, node):
        self.visit(node.value)
        if isinstance(node.target, ast.Name) and isinstance(node.op, ast.Add):
            previous = self.bindings.get(node.target.id, ast.List(elts=[]))
            self.bindings[node.target.id] = ast.List(elts=[previous, _freeze(node.value, self.bindings)])

    def visit_For(self, node):
        if isinstance(node.target, ast.Name):
            names = [node.target.id]
        elif isinstance(node.target, (ast.Tuple, ast.List)) and all(isinstance(n, ast.Name) for n in node.target.elts):
            names = [n.id for n in node.target.elts]
        else:
            names = []
        for row in self._parameter_rows(names, node.iter):
            self.bindings.update(row)
            for stmt in node.body:
                self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_Call(self, node):
        # Operations 常先建列表，再按可用资产 append / extend / insert。
        if (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                and node.func.value.id in self.bindings and node.args
                and node.func.attr in {"append", "extend", "insert"}):
            name = node.func.value.id
            self.bindings[name] = ast.List(elts=[self.bindings[name], _freeze(node.args[-1], self.bindings)])
        if (isinstance(node.func, ast.Attribute)
                and node.func.attr in {"call", "call_capability", "try_call"} and node.args):
            params = ast.Dict(
                keys=[ast.Constant(k.arg) if k.arg else None for k in node.keywords],
                values=[k.value for k in node.keywords],
            )
            if len(node.args) > 1:
                params.keys.append(None)
                params.values.append(node.args[1])
            for cap in _strings(node.args[0], self.bindings):
                cap = self.aliases.get(cap, cap)
                if cap == "CallCapability":
                    for name in _fields(params, "Capability", self.bindings):
                        for nested_cap in _strings(name, self.bindings):
                            for arguments in _fields(params, "Arguments", self.bindings):
                                self._record(nested_cap, arguments)
                else:
                    self._record(cap, params)
        self.generic_visit(node)

    def _record(self, cap, params):
        self.mentioned.add(cap)
        for operations in _fields(params, "Operations", self.bindings):
            for action in _fields(operations, "Action", self.bindings):
                self.actions[cap].update(_strings(action, self.bindings))
        for sections in _fields(params, "Sections", self.bindings):
            self.sections[cap].update(_strings(sections, self.bindings))


def collect_tests(tests=TESTS) -> tuple[dict[str, set[str]], dict[str, set[str]], set[str]]:
    aliases_path = ROOT / "Plugins/NexusLink/Resources/legacy_capability_names.json"
    aliases = json.loads(_read(aliases_path)) if aliases_path.is_file() else {}
    actions, sections, mentioned = defaultdict(set), defaultdict(set), set()
    for p in sorted(tests.rglob("test_*.py")):
        visitor = CoverageVisitor(aliases)
        visitor.visit(ast.parse(_read(p), filename=str(p)))
        for cap, values in visitor.actions.items():
            actions[cap].update(values)
        for cap, values in visitor.sections.items():
            sections[cap].update(values)
        mentioned.update(visitor.mentioned)
    return actions, sections, mentioned


def main() -> int:
    manage, sections = collect_cpp()
    file_actions, file_sections, mentioned = collect_tests()
    if not manage or not sections or not mentioned:
        print("[ERROR] capability or test discovery is empty; coverage audit cannot pass")
        return 1

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
            if s not in tested and "All" not in tested:
                missing_sections.append(f"{cap}  {s}")

    print("Static call coverage only; does not prove execution or assertions.")
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
