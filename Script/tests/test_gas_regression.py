"""自动回归的门禁、失败归档和基线保护；不启动 UE。"""
import copy
import io
from html.parser import HTMLParser
import json
from pathlib import Path
import posixpath
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1]))
import gas_regression as regression


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.baselines = self.root / "baselines"
        shutil.copytree(regression.PROJECT / "Tests/GasRetest/baselines", self.baselines)
        self.previous = regression.load_baselines(self.baselines)
        self.output = self.root / "run"
        self.args = ["--ue-root", str(self.root / "engine"), "--baselines", str(self.baselines), "--output", str(self.output)]
        self.addCleanup(patch.stopall)
        patch("sys.stdout", new=io.StringIO()).start()
        patch("sys.stderr", new=io.StringIO()).start()

    def replay(self, command, **kwargs):
        self.assertIn("--quickstart", command)
        destination = Path(command[command.index("--output") + 1])
        kwargs["stdout"].write("isolated replay fixture\n")
        for scenario, report in self.current.items():
            regression.write_reports(report, destination / ("01-" + scenario))
        return subprocess.CompletedProcess(command, self.replay_exit)

    def run_fixture(self, reports=None, replay_exit=0):
        self.current = copy.deepcopy(self.previous if reports is None else reports)
        self.replay_exit = replay_exit
        with patch("gas_regression.subprocess.run", side_effect=self.replay) as process:
            code = regression.main(self.args)
        self.assertEqual(process.call_count, 1)
        return code, json.loads((self.output / "results.json").read_text(encoding="utf-8"))

    def assert_archive(self):
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []
            def handle_starttag(self, tag, attrs):
                if tag == 'a':
                    self.links.append(dict(attrs)['href'])
        with zipfile.ZipFile(self.output / "reports.zip") as archive:
            names = archive.namelist()
            self.assertTrue({"index.html", "report.html", "results.json", "junit.xml", "run.log"}.issubset(names))
            self.assertNotIn("reports.zip", names)
            self.assertIsNone(archive.testzip())
            for name in names:
                if name.endswith('.html'):
                    parser = Links()
                    parser.feed(archive.read(name).decode('utf-8'))
                    for link in parser.links:
                        self.assertIn(posixpath.normpath(posixpath.join(posixpath.dirname(name), link)), names)
            return names

    def test_success_archives_comparisons_and_rejects_reusing_output(self):
        original = {path.name: path.read_bytes() for path in self.baselines.glob("*.json")}
        code, report = self.run_fixture()
        self.assertEqual(code, 0)
        self.assertTrue(all(item["Status"] == "Passed" for item in report["Records"]))
        self.assertEqual(ET.parse(self.output / "junit.xml").getroot().get("tests"), "2")
        names = self.assert_archive()
        for scenario in regression.QUICKSTART_SCENARIOS:
            self.assertIn(f"comparisons/{scenario}/comparison.html", names)
            self.assertIn(f"comparisons/{scenario}/before/results.json", names)
            self.assertIn(f"current/01-{scenario}/junit.xml", names)
        before = (self.output / "reports.zip").read_bytes()
        with patch("gas_regression.subprocess.run") as process:
            self.assertEqual(regression.main(self.args), 2)
            process.assert_not_called()
        self.assertEqual(before, (self.output / "reports.zip").read_bytes())
        self.assertEqual(original, {path.name: path.read_bytes() for path in self.baselines.glob("*.json")})

    def test_assertion_failure_reaches_junit_and_keeps_raw_evidence(self):
        current = copy.deepcopy(self.previous)
        current["PredictionRejected"]["ExitCode"] = 1
        current["PredictionRejected"]["Records"][-1].update(Status="Failed", Message="assertion fixture")
        code, report = self.run_fixture(current, replay_exit=1)
        self.assertEqual(code, 1)
        self.assertEqual([record["Status"] for record in report["Records"]], ["Failed", "Passed"])
        self.assertEqual(ET.parse(self.output / "junit.xml").getroot().get("failures"), "1")
        self.assertIn("comparisons/PredictionRejected/after/results.json", self.assert_archive())

    def test_missing_case_is_an_error_instead_of_a_skip_or_pass(self):
        code, report = self.run_fixture({"PredictionRejected": self.previous["PredictionRejected"]}, replay_exit=1)
        self.assertEqual(code, 2)
        self.assertEqual(report["Records"][1]["Status"], "Error")
        self.assertIn("not completed", report["Records"][1]["Message"])
        self.assertEqual(ET.parse(self.output / "junit.xml").getroot().get("errors"), "1")
        self.assert_archive()

    def test_runtime_error_and_unexpected_child_exit_are_errors(self):
        current = copy.deepcopy(self.previous)
        current["PredictionRejected"]["ExitCode"] = 2
        current["PredictionRejected"]["Records"][-1].update(Status="Error", Message="transport fixture")
        code, report = self.run_fixture(current, replay_exit=2)
        self.assertEqual(code, 2)
        self.assertEqual(report["Records"][0]["Status"], "Error")
        self.assert_archive()
        self.output = self.root / "other"
        self.args[-1] = str(self.output)
        code, report = self.run_fixture(replay_exit=9)
        self.assertEqual(code, 2)
        self.assertEqual(report["Records"][-1]["Id"], "ReplayProcess")

    def test_all_baselines_validated_before_any_replay(self):
        target = self.baselines / "Success.json"
        wrapper = json.loads(target.read_text(encoding="utf-8"))
        wrapper["Report"]["CaseSignature"] = "b" * 64
        target.write_text(json.dumps(wrapper), encoding="utf-8")
        before = target.read_bytes()
        with patch("gas_regression.subprocess.run") as process:
            self.assertEqual(regression.main(self.args), 2)
            process.assert_not_called()
        self.assertEqual(before, target.read_bytes())
        self.assertTrue((self.output / "reports.zip").is_file())
        target.unlink()
        self.output = self.root / "missing-baseline"
        self.args[-1] = str(self.output)
        with patch("gas_regression.subprocess.run") as process:
            self.assertEqual(regression.main(self.args), 2)
            process.assert_not_called()
        self.assertFalse(target.exists())
        self.assertEqual(ET.parse(self.output / "junit.xml").getroot().get("errors"), "1")


if __name__ == "__main__":
    unittest.main()
