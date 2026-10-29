# Copyright byteyang. All Rights Reserved.
"""连接已有编辑器时保留被测工程路径，不启动 UE。"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location("run_e2e", Path(__file__).resolve().parents[1] / "run_e2e.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize("explicit", [True, False])
@pytest.mark.parametrize("project", [None, "isolated/Project.uproject"])
def test_existing_editor_preserves_project(explicit, project):
    url = "http://127.0.0.1:45009/stream"
    args = SimpleNamespace(ue_url=url if explicit else None, ue_root=None, uproject=project)
    with patch.object(runner, "_probe_live_editor", return_value=url):
        connection, _ = runner._resolve_connection(args)
    assert connection == ["--ue-url", url] + (["--uproject", project] if project else [])
