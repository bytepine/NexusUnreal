# Copyright byteyang. All Rights Reserved.
"""连接已有编辑器时保留被测工程路径，不启动 UE。"""

import importlib.util
import sys
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


def test_main_cleans_selected_project_only(tmp_path, monkeypatch):
    original, selected = tmp_path / "original", tmp_path / "selected"
    for root in (original, selected):
        artifact = root / "Content/_McpTest/keep.txt"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("fixture", encoding="utf-8")
    project = selected / "Selected.uproject"
    project.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(runner, "NEXUS_UNREAL_DIR", original)
    monkeypatch.setattr(runner, "LOG_DIR", selected / "Saved/Logs")
    monkeypatch.setattr(runner, "_ensure_deps", lambda: None)
    monkeypatch.setattr(runner, "_resolve_connection", lambda args: (["--ue-url", "http://127.0.0.1:45009/stream"], "test"))
    monkeypatch.setattr(runner.subprocess, "call", lambda *args, **kwargs: 0)
    monkeypatch.setattr(sys, "argv", ["run_e2e.py", "--uproject", str(project)])
    assert runner.main() == 0
    assert (original / "Content/_McpTest/keep.txt").is_file()
    assert not (selected / "Content/_McpTest").exists()


def test_cleanup_removes_only_generated_tag_sources(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(runner.TESTS_DIR))
    from _framework.test_cleanup import purge_disk_test_artifacts

    tags = tmp_path / "Config/Tags"
    tags.mkdir(parents=True)
    generated = tags / ("NexusMcpTest_" + "a" * 32 + ".ini")
    permanent = tags / "GameplayTags.ini"
    ambiguous = tags / "NexusMcpTest_custom.ini"
    for path in (generated, permanent, ambiguous):
        path.write_text("[/Script/GameplayTags.GameplayTagsList]\n", encoding="utf-8")
    purge_disk_test_artifacts(tmp_path)
    assert not generated.exists()
    assert permanent.is_file() and ambiguous.is_file()
