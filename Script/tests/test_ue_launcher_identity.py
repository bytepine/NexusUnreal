import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Tests"))
from _framework.ue_launcher import UELauncher


class LauncherIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "Probe.uproject"
        self.project.write_text("{}")
        self.launcher = UELauncher(self.project, self.root, port_range=range(45000, 45002))
        self.launcher._proc = SimpleNamespace(pid=1234, poll=lambda: None)
        (self.root / "NexusLink").mkdir()
        self.manifest = self.root / "NexusLink/1234.json"
        self.temp_patch = patch("_framework.ue_launcher.tempfile.gettempdir", return_value=str(self.root))
        self.temp_patch.start()

    def tearDown(self):
        self.temp_patch.stop()
        self.temp.cleanup()

    def test_pid_and_project_must_match(self):
        for data in ({"pid": 55, "projectName": "Probe", "mcpPort": 45001},
                     {"pid": 1234, "projectName": "Foreign", "mcpPort": 45001}):
            self.manifest.write_text(json.dumps(data))
            self.assertIsNone(self.launcher._registered_mcp_port())

    def test_ready_only_on_owned_port_even_if_previously_occupied(self):
        self.manifest.write_text(json.dumps({"pid": 1234, "projectName": "Probe", "mcpPort": 45001}))
        calls = []
        response = SimpleNamespace(status_code=200, text='{"wsPort":55001}')
        client = SimpleNamespace(get=lambda url: (calls.append(url), response)[1])
        with patch("_framework.ue_launcher.httpx.Client") as constructor:
            constructor.return_value.__enter__.return_value = client
            self.launcher._wait_until_ready(skip_ports={45001})
        self.assertEqual(self.launcher._resolved_port, 45001)
        self.assertEqual(calls, ["http://127.0.0.1:45001/status"])


if __name__ == "__main__":
    unittest.main()
