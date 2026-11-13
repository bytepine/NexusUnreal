"""UE 报告门禁的真实 JUnit 成功、跳过、错误与缺失边界。"""

import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET


spec = importlib.util.spec_from_file_location("check_ue_ci_report", Path(__file__).resolve().parents[1] / "check_ue_ci_report.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class UeReportTests(unittest.TestCase):
    def report(self, mutate=lambda root: None, gui=False):
        root = ET.Element("testsuites")
        suite = ET.SubElement(root, "testsuite")
        for module, names in checker.REQUIRED.items():
            for name in names:
                ET.SubElement(suite, "testcase", classname="Tests." + module, name=name)
        if gui:
            for name in checker.GUI_REQUIRED:
                ET.SubElement(suite, "testcase", classname="Tests.test_15_editor_operations", name=name)
        mutate(root)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "junit.xml"
            ET.ElementTree(root).write(path, encoding="utf-8")
            return checker.check_report(path, "gui" if gui else "headless")

    def test_actual_baseline_passes_and_optional_skips_are_reported(self):
        def add_optional(root):
            case = ET.SubElement(root.find("testsuite"), "testcase", classname="Tests.test_optional", name="test_optional")
            ET.SubElement(case, "skipped")
        result = self.report(add_optional)
        self.assertFalse(result["errors"])
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["passed"], 9)

    def test_required_native_skip_fails(self):
        def skip_native(root):
            case = next(case for case in root.iter("testcase") if "automation_local_run" in case.get("name"))
            ET.SubElement(case, "skipped")
        self.assertTrue(self.report(skip_native)["errors"])

    def test_missing_duplicate_and_wrong_module_results_fail(self):
        def remove_case(root):
            suite = root.find("testsuite")
            suite.remove(suite[0])
        def duplicate(root):
            suite = root.find("testsuite")
            ET.SubElement(suite, "testcase", **suite[0].attrib)
        def wrong_module(root):
            root.find("testsuite")[0].set("classname", "unrelated")
        for mutate in (remove_case, duplicate, wrong_module):
            with self.subTest(mutate=mutate.__name__):
                self.assertTrue(self.report(mutate)["errors"])

    def test_optional_failure_or_setup_error_also_fails(self):
        for tag in ("failure", "error"):
            def fail_optional(root):
                case = ET.SubElement(root.find("testsuite"), "testcase", classname="optional", name="test_optional")
                ET.SubElement(case, tag)
            self.assertTrue(self.report(fail_optional)["errors"])

    def test_empty_report_fails(self):
        self.assertTrue(self.report(lambda root: root.clear())["errors"])

    def test_gui_requires_actual_gui_cases(self):
        self.assertFalse(self.report(gui=True)["errors"])
        def skip_gui(root):
            case = next(case for case in root.iter("testcase") if case.get("name") == checker.GUI_REQUIRED[0])
            ET.SubElement(case, "skipped")
        self.assertTrue(self.report(skip_gui, gui=True)["errors"])


if __name__ == "__main__":
    unittest.main()
