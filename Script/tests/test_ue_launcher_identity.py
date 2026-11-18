import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Tests"))
from _framework.ue_launcher import UELauncher, matching_editor_urls


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
            self.assertEqual(matching_editor_urls(self.project, launched_pid=self.launcher.pid), [])

    def test_ready_only_on_owned_port_even_if_previously_occupied(self):
        self.manifest.write_text(json.dumps({"pid": 1234, "projectName": "Probe", "mcpPort": 45001, "wsPort": 55001}))
        response = Mock()
        response.json.return_value = dict(server="Nexus-Unreal", hostKind="Editor", projectName="Probe", wsPort=55001)
        listener = SimpleNamespace(status="LISTEN", family=socket.AF_INET, laddr=SimpleNamespace(ip="0.0.0.0", port=45001))
        with patch("_framework.ue_launcher.psutil.Process") as process, patch("_framework.ue_launcher.httpx.Client") as http:
            process.return_value.net_connections.return_value = [listener]
            client = http.return_value.__enter__.return_value
            client.get.return_value = response
            self.launcher._wait_until_ready()
            process.assert_called_once_with(1234)
            client.get.assert_called_once_with("http://127.0.0.1:45001/status")
            listener.laddr.ip = "192.168.1.5"
            self.assertEqual(matching_editor_urls(self.project, launched_pid=self.launcher.pid), [])
            listener.family = socket.AF_INET6
            listener.laddr.ip = "::"
            self.assertEqual(matching_editor_urls(self.project, launched_pid=self.launcher.pid), [])
        self.assertEqual(self.launcher._resolved_port, 45001)


if __name__ == "__main__":
    unittest.main()
