# Copyright byteyang. All Rights Reserved.
"""构建调度回归；不启动 UBT，也不清理真实隔离目录。"""

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1] / "build_test.py"
spec = importlib.util.spec_from_file_location("build_test", SCRIPT)
build = importlib.util.module_from_spec(spec)
with patch("atexit.register") as register:
    spec.loader.exec_module(build)
    IMPORT_REGISTERED_CLEANUP = register.called


class BuildSchedulingTests(unittest.TestCase):
    def test_import_has_no_cleanup_side_effect(self):
        self.assertFalse(IMPORT_REGISTERED_CLEANUP)

    def test_one_engine_leaves_parallelism_to_ubt(self):
        self.assertEqual(build._parallel_limits(3, 11), (1, None))
        self.assertEqual(build._parallel_limits(8, 2), (1, None))

    def run_phase(self, outcomes, workers=1):
        engine = {"version": "UE_4.27", "path": "unused"}

        def result(exit_code, errors):
            return dict(ver=engine["version"], eng_path=engine["path"],
                        exit_code=exit_code, error_lines=errors, output=errors, warn_lines=[])

        builder = Mock(side_effect=[result(*outcome) for outcome in outcomes])
        with patch.object(build, "_build_one", builder), \
                contextlib.redirect_stdout(io.StringIO()):
            summary = build._run_phase([engine], build.EDITOR_TARGET, workers, None, "Editor")
        return builder, summary

    def test_single_engine_oom_retries_with_one_action(self):
        builder, (results, passed, failed, warnings) = self.run_phase(
            [(6, ["error C3859", "fatal error C1076"]), (0, [])])
        self.assertEqual([call.args[-1] for call in builder.call_args_list], [None, 1])
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

    def test_explicit_matrix_reports_missing_versions_before_building(self):
        output = io.StringIO()
        with patch.object(build.sys, "argv", ["build_test.py", "--versions", "UE_4.27", "UE_5.7"]), \
                patch.object(build, "discover_engines_auto", return_value=[{"version": "UE_5.7", "path": "unused"}]), \
                patch.object(build, "run_build_test", return_value=0) as compile_project, \
                patch.object(build, "_list_installed_msvc", return_value=[]), \
                patch.object(build, "_detect_msvc_for", return_value=None), \
                patch.object(build.atexit, "register"), patch.object(build.signal, "signal"), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(output):
            self.assertNotEqual(build.main(), 0)
        self.assertIn("Specified versions not found: UE_4.27", output.getvalue())
        compile_project.assert_not_called()

    def test_missing_build_script_fails_explicit_editor_and_game_targets(self):
        for phase, logfile in [("--editor-only", "Build.Log"), ("--game-only", "Build.Game.Log")]:
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as folder:
                logs = Path(folder)
                engine = {"version": "UE_5.7", "path": str(logs / "UE_5.7")}
                with patch.object(build.sys, "argv", ["build_test.py", phase, "--versions", "UE_5.7"]), \
                        patch.object(build, "discover_engines_auto", return_value=[engine]), \
                        patch.object(build, "_list_installed_msvc", return_value=[]), \
                        patch.object(build, "_detect_msvc_for", return_value=None), \
                        patch.object(build, "LOG_DIR", logs), \
                        patch.object(build, "LOG_FILE", logs / "Build.Log"), \
                        patch.object(build, "LOG_FILE_GAME", logs / "Build.Game.Log"), \
                        patch.object(build, "_kill_leftover_build_processes"), \
                        patch.object(build, "_reset_temp_workspace"), \
                        patch.object(build, "_isolated_uproject", return_value=build.UPROJECT_PATH), \
                        patch.object(build.atexit, "register"), patch.object(build.signal, "signal"), \
                        contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertNotEqual(build.main(), 0)
                report = (logs / logfile).read_text(encoding="utf-8")
                self.assertIn("[UE_5.7]", report)
                self.assertIn("UBT Build script not found", report)
                self.assertIn("PASS=0  FAIL=1", report)

    def test_discovery_mode_reports_missing_build_script_as_skip(self):
        _, (results, passed, failed, warnings) = self.run_phase([(-1, ["UBT Build script not found"])])
        lines = []
        self.assertEqual(build._format_result_block(results["UE_4.27"], lines, ""), (0, 0, 0))
        self.assertTrue(any("SKIP" in line for line in lines))
        self.assertEqual((passed, failed, warnings), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
