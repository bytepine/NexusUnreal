# Copyright byteyang. All Rights Reserved.
"""构建调度回归；不启动 UBT，也不清理真实隔离目录。"""

import contextlib
import ctypes
import importlib.util
import io
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1] / "build_test.py"
spec = importlib.util.spec_from_file_location("build_test", SCRIPT)
build = importlib.util.module_from_spec(spec)
with patch("atexit.register") as register:
    spec.loader.exec_module(build)
    IMPORT_REGISTERED_CLEANUP = register.called


class BuildSchedulingTests(unittest.TestCase):
    def budget(self, physical, commit, success=True):
        def memory_status(pointer):
            pointer._obj.avail_phys = physical * 1024 ** 3
            pointer._obj.avail_commit = commit * 1024 ** 3
            return success

        kernel = SimpleNamespace(GlobalMemoryStatusEx=memory_status)
        with patch.object(build, "_SYSTEM", "Windows"), \
                patch.object(build.os, "cpu_count", return_value=32), \
                patch.object(ctypes, "windll", SimpleNamespace(kernel32=kernel), create=True):
            return build._compile_action_budget()

    def test_import_has_no_cleanup_side_effect(self):
        self.assertFalse(IMPORT_REGISTERED_CLEANUP)

    def test_memory_budget_uses_lower_of_physical_and_commit(self):
        self.assertEqual(self.budget(80, 16), 3)
        self.assertEqual(self.budget(12, 100), 2)
        self.assertEqual(self.budget(100, 100), 16)

    def test_low_or_unknown_memory_is_conservative(self):
        self.assertEqual(self.budget(2, 1), 1)
        self.assertEqual(self.budget(100, 100, success=False), 2)

    def test_engine_and_action_counts_share_budget(self):
        with patch.object(build, "_compile_action_budget", return_value=2):
            self.assertEqual(build._parallel_limits(3, 11), (2, 1))
            self.assertEqual(build._parallel_limits(3, 1), (1, 2))
        with patch.object(build, "_compile_action_budget", return_value=1):
            self.assertEqual(build._parallel_limits(3, 11), (1, 1))

    def run_phase(self, outcomes, workers=1):
        engine = {"version": "UE_4.27", "path": "unused"}

        def result(exit_code, errors):
            return dict(ver=engine["version"], eng_path=engine["path"],
                        exit_code=exit_code, error_lines=errors, output=errors, warn_lines=[])

        builder = Mock(side_effect=[result(*outcome) for outcome in outcomes])
        with patch.object(build, "_build_one", builder), \
                patch.object(build, "_compile_action_budget", return_value=8), \
                contextlib.redirect_stdout(io.StringIO()):
            summary = build._run_phase([engine], build.EDITOR_TARGET, workers, None, "Editor")
        return builder, summary

    def test_single_engine_oom_retries_with_one_action(self):
        builder, (results, passed, failed, warnings) = self.run_phase(
            [(6, ["error C3859", "fatal error C1076"]), (0, [])])
        self.assertEqual([call.args[-1] for call in builder.call_args_list], [8, 1])
        self.assertEqual((passed, failed, warnings), (1, 0, 0))
        self.assertTrue(results["UE_4.27"]["retried_pch_oom"])

    def test_failed_oom_retry_is_bounded(self):
        builder, (_, passed, failed, _) = self.run_phase(
            [(6, ["error C1076"]), (6, ["error C1076"])], workers=3)
        self.assertEqual(builder.call_count, 2)
        self.assertEqual(builder.call_args_list[-1].args[-1], 1)
        self.assertEqual((passed, failed), (0, 1))

    def test_code_error_is_not_retried(self):
        builder, (_, _, failed, _) = self.run_phase([(6, ["error C2039: missing member"])])
        self.assertEqual(builder.call_count, 1)
        self.assertEqual(failed, 1)


if __name__ == "__main__":
    unittest.main()
