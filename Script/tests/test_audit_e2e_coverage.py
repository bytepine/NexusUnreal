# Copyright byteyang. All Rights Reserved.
"""覆盖审计回归，不加载 pytest E2E fixture 或启动 UE。"""

import ast
import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "audit_e2e_coverage.py"
spec = importlib.util.spec_from_file_location("audit_e2e_coverage", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class CoverageAuditTests(unittest.TestCase):
    def parse(self, source):
        visitor = audit.CoverageVisitor({})
        visitor.visit(ast.parse(source))
        return visitor

    def test_modules_and_inline_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = []
            for plugin in ("NexusLink", "NexusLinkExt"):
                for suffix in ("", "Editor"):
                    root = Path(tmp) / plugin / (plugin + suffix) / "Private/Capabilities"
                    root.mkdir(parents=True)
                    roots.append(root)
                    cap = "Manage" + plugin + (suffix or "Runtime")
                    (root / "Manage.cpp").write_text(
                        f'Out.Name = TEXT("{cap}"); OutHandlers.Add(TEXT("Update"), &Handler);',
                        encoding="utf-8",
                    )
            (roots[1] / "Get.cpp").write_text('Out.Name = TEXT("GetExample");', encoding="utf-8")
            (roots[1] / "Get.h").write_text(
                'GetSectionNames() const override { return { TEXT("Details") }; }', encoding="utf-8",
            )
            actions, sections = audit.collect_cpp(roots)
            self.assertEqual(len(actions), 4)
            self.assertEqual(sections, {"GetExample": ["Details"]})
        self.assertEqual(len(audit.CAP_ROOTS), 4)

    def test_only_actual_call_arguments_count(self):
        visitor = self.parse('''
def test_example(mcp):
    unused = [{"Action": "Unused"}]
    ops = [{"Action": "Add"}]
    ops.append({"Action": "Remove"})
    ops.insert(0, {"Action": "First"})
    ops.extend([{"Action": "Last"}])
    ops += [{"Action": "Extra"}]
    mcp.call_capability("ManageOne", Operations=ops)
    mcp.call_capability("ManageTwo", Operations=[{"Action": "Other"}])
    mcp.call("GetOne", Sections=["Details"])
    mcp.call("GetTwo", Sections=["All"])
''')
        self.assertEqual(visitor.actions["ManageOne"], {"Add", "Remove", "First", "Last", "Extra"})
        self.assertEqual(visitor.actions["ManageTwo"], {"Other"})
        self.assertEqual(visitor.sections["GetOne"], {"Details"})
        self.assertEqual(visitor.sections["GetTwo"], {"All"})

    def test_loop_parametrize_and_nested_call(self):
        visitor = self.parse('''
@pytest.mark.parametrize("section", ["Summary", "Frames"])
def test_trace(mcp, section):
    mcp.call_capability("GetTrace", Sections=[section])
def test_ops(mcp):
    for op in [{"Action": "Add"}, {"Action": "Remove"}]:
        mcp.call_capability("ManageLoop", Operations=[op])
    for action, value in [("First", "not-an-action"), ("Second", "also-not-an-action")]:
        mcp.call_capability("ManageTuple", Operations=[{"Action": action, "Value": value}])
    mcp.call("CallCapability", Capability="GetNested", Arguments={"Sections": ["Details"]})
''')
        self.assertEqual(visitor.sections["GetTrace"], {"Summary", "Frames"})
        self.assertEqual(visitor.actions["ManageLoop"], {"Add", "Remove"})
        self.assertEqual(visitor.actions["ManageTuple"], {"First", "Second"})
        self.assertEqual(visitor.sections["GetNested"], {"Details"})

    def test_real_gas_sections_are_recognized(self):
        _, sections, _ = audit.collect_tests()
        self.assertTrue({"Abilities", "Effects", "Attributes"} <= sections["GetRuntimeActorAbilitySystem"])

    def test_capability_action_pairs_keep_row_correlation(self):
        for declaration in [
            '''def test_pairs(mcp):
    for cap, action in [("ManageOne", "Add"), ("ManageTwo", "Remove")]:
        mcp.call_capability(cap, Operations=[{"Action": action}])
''',
            '''@pytest.mark.parametrize("cap, action", [("ManageOne", "Add"), ("ManageTwo", "Remove")])
def test_pairs(mcp, cap, action):
    mcp.call_capability(cap, Operations=[{"Action": action}])
''',
            '''@pytest.mark.parametrize(("cap", "action"), [("ManageOne", "Add"), ("ManageTwo", "Remove")])
def test_pairs(mcp, cap, action):
    mcp.call_capability(cap, Operations=[{"Action": action}])
''',
        ]:
            with self.subTest(source=declaration):
                visitor = self.parse(declaration)
                self.assertEqual(dict(visitor.actions), {"ManageOne": {"Add"}, "ManageTwo": {"Remove"}})

    def test_loop_mutations_survive_and_freeze_iteration_values(self):
        visitor = self.parse('''
def test_ops(mcp):
    ops = [{"Action": "Before"}]
    for action in ["Add", "Remove"]:
        ops.append({"Action": action})
    for action in ["First"]:
        ops.insert(0, {"Action": action})
    for action in ["Last"]:
        ops.extend([{"Action": action}])
    for action in ["Extra"]:
        ops += [{"Action": action}]
    mcp.call_capability("ManageOne", Operations=ops)
''')
        self.assertEqual(visitor.actions["ManageOne"], {"Before", "Add", "Remove", "First", "Last", "Extra"})

    def test_empty_discovery_fails(self):
        with patch.object(audit, "collect_cpp", return_value=({}, {})), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(audit.main(), 1)

    def test_mutated_parameter_tables_preserve_rows(self):
        for mutation in [
            'cases.append(("ManageThree", "Update"))',
            'cases.extend([("ManageThree", "Update")])',
            'cases.insert(1, ("ManageThree", "Update"))',
            'cases += [("ManageThree", "Update")]',
        ]:
            with self.subTest(mutation=mutation):
                visitor = self.parse('''
def test_pairs(mcp):
    cases = [("ManageOne", "Add"), ("ManageTwo", "Remove")]
    ''' + mutation + '''
    for cap, action in cases:
        mcp.call_capability(cap, Operations=[{"Action": action}])
''')
                self.assertEqual(dict(visitor.actions), {
                    "ManageOne": {"Add"}, "ManageTwo": {"Remove"}, "ManageThree": {"Update"},
                })

    def test_payload_keeps_mutable_list_aliases_and_rebinding(self):
        for assignment in ['payload =', 'payload: dict =']:
            with self.subTest(assignment=assignment):
                visitor = self.parse('''
def test_ops(mcp):
    ops = []
    alias = ops
    ''' + assignment + ''' {"Operations": ops}
    for action in ["Add", "Remove"]:
        alias.append({"Action": action})
    ops += [{"Action": "Extra"}]
    mcp.call_capability("ManageOne", **payload)
    ops = []
    ops.append({"Action": "Other"})
    mcp.call_capability("ManageOld", **payload)
    mcp.call_capability("ManageNew", Operations=ops)
''')
                self.assertEqual(visitor.actions["ManageOne"], {"Add", "Remove", "Extra"})
                self.assertEqual(visitor.actions["ManageOld"], {"Add", "Remove", "Extra"})
                self.assertEqual(visitor.actions["ManageNew"], {"Other"})

    def test_tuple_addition_rebinds_without_changing_aliases(self):
        visitor = self.parse('''
def test_pairs(mcp):
    cases = (("ManageOne", "Add"),)
    alias = cases
    cases += (("ManageTwo", "Remove"),)
    for cap, action in cases:
        mcp.call_capability(cap, Operations=[{"Action": action}])
    for cap, action in alias:
        mcp.call_capability("ManageAlias", Operations=[{"Action": action}])
''')
        self.assertEqual(dict(visitor.actions), {
            "ManageOne": {"Add"}, "ManageTwo": {"Remove"}, "ManageAlias": {"Add"},
        })

    def test_parameter_contexts_isolate_mutable_lists(self):
        visitor = self.parse('''
ops = []
payload = {"Operations": ops}
@pytest.mark.parametrize("cap, action", [("ManageOne", "Add"), ("ManageTwo", "Remove")])
def test_ops(mcp, cap, action):
    ops.append({"Action": action})
    mcp.call_capability(cap, **payload)
''')
        self.assertEqual(dict(visitor.actions), {"ManageOne": {"Add"}, "ManageTwo": {"Remove"}})

    def test_pytest_param_and_unknown_rows_keep_calls(self):
        visitor = self.parse('''
@pytest.mark.parametrize("cap, action", [
    pytest.param("ManageOne", "Add", id="one", marks=pytest.mark.slow),
    ("ManageTwo", "Remove"),
])
def test_pairs(mcp, cap, action):
    mcp.call_capability(cap, Operations=[{"Action": action}])

@pytest.mark.parametrize("section", [pytest.param("Details", id="details")])
def test_section(mcp, section):
    mcp.call_capability("GetOne", Sections=[section])

@pytest.mark.parametrize("mode, value", [build_case()])
def test_unknown(mcp, mode, value):
    mcp.call_capability("ManageStatic", Operations=[{"Action": "Fixed"}])
''')
        self.assertEqual(dict(visitor.actions), {
            "ManageOne": {"Add"}, "ManageTwo": {"Remove"}, "ManageStatic": {"Fixed"},
        })
        self.assertEqual(visitor.sections["GetOne"], {"Details"})


if __name__ == "__main__":
    unittest.main()
