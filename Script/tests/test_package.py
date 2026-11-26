# Copyright byteyang. All Rights Reserved.
"""打包使用项目原始配置或按引擎隔离配置的回归测试。"""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "package.py"
spec = importlib.util.spec_from_file_location("package", SCRIPT)
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackageProjectTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "Project" / "Nexus.uproject"
        self.engine = self.root / "EngineInstallation"
        self.archive = self.root / "Archive"
        self.files = {
            "Build/Win64/Application.ico": "icon",
            "Config/DefaultEngine.ini": "settings",
            "Content/Map.umap": "asset",
            "Source/Nexus.Target.cs": "target",
            "Plugins/NexusLink/NexusLink.uplugin": "{}",
            "Plugins/NexusLink/Binaries/Old.dll": "stale",
        }
        for relative, content in self.files.items():
            self.write(self.project.parent / relative, content)
        self.engine_version(4, 26)
        self.source_descriptor = json.dumps({
            "EngineAssociation": "5.7",
            "Modules": [{"Name": "Nexus"}, {"Name": "NexusGameplay"}],
            "Plugins": [
                {"Name": "NexusLink", "Enabled": True},
                {"Name": "EnhancedInput", "Enabled": True, "Optional": True},
                {"Name": "Paper2D", "Enabled": False},
            ],
        })
        self.write(self.project, self.source_descriptor)

    @staticmethod
    def write(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def engine_version(self, major, minor):
        self.write(self.engine / "Engine/Build/Build.version", json.dumps({
            "MajorVersion": major, "MinorVersion": minor,
        }))

    @staticmethod
    def command_project(command):
        return Path(next(arg for arg in command if arg.startswith("-project=")).split("=", 1)[1])

    def run_package(self, version, run_uat, *options):
        args = ["package.py", "--version", version, "--platform", "Win64", "--output", str(self.archive), *options]
        output = io.StringIO()
        with patch.object(package, "UPROJECT_PATH", self.project), \
                patch.object(package, "_resolve_engine", return_value=(version, self.engine)), \
                patch.object(package, "_package_one", side_effect=run_uat), \
                patch.object(package.sys, "argv", args), contextlib.redirect_stdout(output):
            result = package.main()
        self.assertEqual(result, 0, output.getvalue())
        self.assertEqual(self.project.read_text(encoding="utf-8"), self.source_descriptor)
        return output.getvalue()

    def test_ue4_packages_isolated_project_with_compatible_input(self):
        projects = []

        def run_uat(command, dry_run):
            self.assertFalse(dry_run)
            project = self.command_project(command)
            projects.append(project)
            self.assertNotEqual(project, self.project)
            self.assertEqual(project.name, self.project.name)
            descriptor = json.loads(project.read_text(encoding="utf-8"))
            self.assertEqual(descriptor["Modules"], [{"Name": "Nexus"}])
            self.assertEqual(descriptor["Plugins"], [
                {"Name": "NexusLink", "Enabled": True},
                {"Name": "EnhancedInput", "Enabled": False, "Optional": True},
                {"Name": "Paper2D", "Enabled": False},
            ])
            for file, contents in self.files.items():
                if file.endswith(".dll"):
                    self.assertFalse((project.parent / file).exists())
                else:
                    self.assertEqual((project.parent / file).read_text(encoding="utf-8"), contents)
            return 0

        self.run_package("UE_4.26", run_uat)
        self.assertEqual(len(projects), 1)
        self.assertFalse(projects[0].parent.exists())

    def test_gameplay_module_alone_triggers_isolation_before_5_6(self):
        self.engine_version(5, 5)

        def run_uat(command, dry_run):
            self.assertFalse(dry_run)
            project = self.command_project(command)
            self.assertNotEqual(project, self.project)
            descriptor = json.loads(project.read_text(encoding="utf-8"))
            self.assertEqual(descriptor["Modules"], [{"Name": "Nexus"}])
            self.assertEqual(descriptor["Plugins"], json.loads(self.source_descriptor)["Plugins"])
            return 0

        output = self.run_package("UE_5.5", run_uat)
        self.assertIn("NexusGameplay", output)

    def test_compatible_engine_packages_original_project(self):
        self.engine_version(5, 6)

        def run_uat(command, dry_run):
            self.assertFalse(dry_run)
            self.assertEqual(self.command_project(command), self.project)
            return 0

        with patch.object(package.tempfile, "TemporaryDirectory") as isolate:
            self.run_package("UE_5.6", run_uat)
        isolate.assert_not_called()

    def test_dry_run_reports_ue4_compatibility_changes_without_writing(self):
        def run_uat(command, dry_run):
            self.assertTrue(dry_run)
            self.assertNotEqual(self.command_project(command), self.project)
            return 0

        with patch.object(package.tempfile, "TemporaryDirectory") as isolate:
            output = self.run_package("UE_4.26", run_uat, "--dry-run")
        isolate.assert_not_called()
        self.assertIn("EnhancedInput", output)
        self.assertIn("NexusGameplay", output)
        self.assertFalse(self.archive.exists())
        self.assertFalse((self.project.parent / "Saved").exists())
