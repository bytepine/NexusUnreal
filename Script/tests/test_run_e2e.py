# Copyright byteyang. All Rights Reserved.
"""连接已有编辑器时保留被测工程路径，不启动 UE。"""

import importlib.util
import json
import socket
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

spec = importlib.util.spec_from_file_location("run_e2e", Path(__file__).resolve().parents[1] / "run_e2e.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
sys.path.insert(0, str(runner.TESTS_DIR))
from _framework import ue_launcher

spec = importlib.util.spec_from_file_location("e2e_fixtures", runner.TESTS_DIR / "conftest.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


@pytest.mark.parametrize("explicit", [True, False])
def test_existing_editor_preserves_project(explicit, tmp_path):
    project = tmp_path / "Project.uproject"
    project.touch()
    url = "http://127.0.0.1:45009/stream"
    args = SimpleNamespace(ue_url=url if explicit else None, ue_root=None, uproject=project)
    with patch.object(ue_launcher, "matching_editor_urls", return_value=[url]) as identify:
        connection, _ = runner._resolve_connection(args)
    assert connection == ["--ue-url", url, "--uproject", str(project)]
    expected = (project, url) if explicit else (project,)
    identify.assert_called_once_with(*expected)


def test_ambiguous_and_unverified_connections(tmp_path, monkeypatch):
    project = tmp_path / "Project.uproject"
    project.touch()
    args = SimpleNamespace(ue_url=None, ue_root=None, uproject=str(project), no_launch=True)
    monkeypatch.setattr(ue_launcher, "matching_editor_urls", lambda *args: ["one", "two"])
    with pytest.raises(ValueError, match="Multiple Editors"):
        runner._resolve_connection(args)
    monkeypatch.setattr(ue_launcher, "matching_editor_urls", lambda *args: [])
    assert not runner._resolve_connection(args)[0]
    args.no_launch = False
    monkeypatch.setattr(runner, "_autodetect_ue_root", lambda preferred, *, headless: ("UE_5.7", "engine"))
    assert runner._resolve_connection(args)[0] == ["--ue-root", "engine", "--uproject", str(project)]
    args.ue_url = "http://127.0.0.1:45000/stream"
    with pytest.raises(ValueError, match="Cannot verify"):
        runner._resolve_connection(args)


@pytest.mark.parametrize("headless", [True, False])
@pytest.mark.parametrize("preferred", [None, "UE_5.7", "UE_5.8"])
def test_autodetect_uses_the_local_editor_resolver(tmp_path, monkeypatch, headless, preferred):
    local = tmp_path / "UE_5.7"
    foreign = tmp_path / "UE_5.8"
    for binary in (
        local / "Engine/Binaries/Win64/UnrealEditor.exe",
        foreign / "Engine/Binaries/Linux/UnrealEditor-Cmd",
    ):
        binary.parent.mkdir(parents=True)
        binary.touch()
    monkeypatch.setattr(ue_launcher, "_is_windows", lambda: True)
    monkeypatch.setitem(sys.modules, "engine_discovery", SimpleNamespace(
        discover_engines_auto=lambda: [
            {"version": root.name, "path": str(root)} for root in (local, foreign)
        ],
    ))
    assert runner._autodetect_ue_root(preferred, headless=headless) == ("UE_5.7", str(local))


def test_attach_requires_project_path_and_live_port_owner(tmp_path, monkeypatch):
    project = tmp_path / "Project.uproject"
    project.touch()
    registry = tmp_path / "NexusLink"
    registry.mkdir()
    monkeypatch.setattr(ue_launcher.tempfile, "gettempdir", lambda: str(tmp_path))
    processes = {}
    for pid, path in enumerate([tmp_path / "other/Project.uproject", project, project], 1):
        port = 45000 + pid
        (registry / f"{pid}.json").write_text(json.dumps(dict(
            pid=pid, projectName="Project", engineVersion="5.7", mcpPort=port, wsPort=55000 + pid)))
        process = processes[pid] = Mock()
        process.cmdline.return_value = ["UnrealEditor", f"-project={path}"]
        process.net_connections.return_value = [SimpleNamespace(
            status="LISTEN", family=socket.AF_INET, laddr=SimpleNamespace(ip="127.0.0.1", port=port if pid != 3 else 12345))]
    monkeypatch.setattr(ue_launcher.psutil, "Process", processes.__getitem__)
    url = "http://127.0.0.1:45002"
    response = Mock()
    response.json.return_value = dict(server="Nexus-Unreal", hostKind="Editor", projectName="Project", wsPort=55002)
    with patch.object(ue_launcher.httpx, "Client") as constructor:
        http = constructor.return_value.__enter__.return_value
        http.get.return_value = response
        assert ue_launcher.matching_editor_urls(project) == [url + "/stream"]
        http.get.assert_called_once_with(url + "/status")
        assert ue_launcher.matching_editor_urls(project, url.replace("127.0.0.1", "localhost")) == [url + "/stream"]
        assert ue_launcher.matching_editor_urls(project, "http://127.0.0.1:45001/stream") == []
        response.json.return_value["hostKind"] = "Game"
        assert ue_launcher.matching_editor_urls(project, url) == []
        response.json.return_value["hostKind"] = "Editor"
        processes[2].cmdline.return_value = ["UnrealEditor", "Project.uproject"]
        with pytest.raises(RuntimeError, match="Cannot verify"):
            ue_launcher.matching_editor_urls(project)


def test_process_project_distinguishes_target_from_other_file_arguments(tmp_path):
    project = tmp_path / "Project.uproject"
    other = tmp_path / "Other.uproject"
    process = Mock()
    process.cmdline.return_value = ["UnrealEditor", str(project), str(other), f"-project={other}"]
    assert ue_launcher._process_project(process, "4.27") == project
    assert ue_launcher._process_project(process, "5.2") == other
    process.cmdline.return_value = ["UnrealEditor", "Project", str(project)]
    assert ue_launcher._process_project(process, "5.7") is None


def test_failed_identity_or_handshake_cannot_clean(tmp_path, monkeypatch):
    project = tmp_path / "Project.uproject"
    url = "http://127.0.0.1:45000/stream"
    config = SimpleNamespace(getoption={"--ue-url": url, "--keep-artifacts": False}.get)
    clean = Mock(return_value=[])
    monkeypatch.setattr(fixtures, "purge_disk_test_artifacts", clean)
    monkeypatch.setattr(fixtures, "matching_editor_urls", lambda *args, **kwargs: [])
    with pytest.raises(pytest.fail.Exception, match="Cannot verify"):
        next(fixtures._ue_url.__wrapped__(config, project))
    with patch.object(fixtures, "MCPClient") as client:
        with pytest.raises(pytest.fail.Exception, match="identity changed"):
            next(fixtures.mcp.__wrapped__(url, config, project))
        client.return_value.close.assert_called_once_with()
    session = SimpleNamespace(config=config)
    fixtures.pytest_sessionfinish(session, 1)
    clean.assert_not_called()
    config._nexus_launched_pid = 1234
    identify = Mock(return_value=[url])
    monkeypatch.setattr(fixtures, "matching_editor_urls", identify)
    with patch.object(fixtures, "MCPClient"):
        fixture = fixtures.mcp.__wrapped__(url, config, project)
        next(fixture)
        fixture.close()
    identify.assert_called_once_with(project, url, launched_pid=1234)
    fixtures.pytest_sessionfinish(session, 0)
    clean.assert_called_once_with(project.parent, include_report=False)


def test_keep_artifacts_skips_disk_and_editor_cleanup(tmp_path, monkeypatch):
    config = SimpleNamespace(getoption=lambda _: True, _nexus_verified_project=tmp_path / "Project.uproject")
    clean_disk, clean_editor = Mock(), Mock()
    monkeypatch.setattr(fixtures, "purge_disk_test_artifacts", clean_disk)
    monkeypatch.setattr(fixtures, "purge_mcp_test_assets", clean_editor)
    assert list(fixtures._test_artifact_hygiene.__wrapped__(Mock(), config)) == [None]
    fixtures.pytest_sessionfinish(SimpleNamespace(config=config), 0)
    clean_disk.assert_not_called()
    clean_editor.assert_not_called()


def test_verified_loopback_client_ignores_proxy_environment(monkeypatch):
    monkeypatch.setenv("NEXUS_MCP_TOKEN", "fixture")
    with patch("_framework.mcp_client.httpx.Client") as http:
        client = fixtures.MCPClient("http://127.0.0.1:45000/stream")
        assert http.call_args.kwargs["trust_env"] is False
        client.close()


def test_coverage_failure_stops_before_cleanup_and_launch(monkeypatch):
    commands = []
    monkeypatch.setattr(runner, "_ensure_deps", lambda: None)
    monkeypatch.setattr(runner.subprocess, "call", lambda command: commands.append(command) or 1)
    monkeypatch.setattr(runner, "_resolve_connection", lambda args: pytest.fail("must not launch on audit failure"))
    monkeypatch.setattr(sys, "argv", ["run_e2e.py"])
    assert runner.main() == 1
    assert len(commands) == 1 and Path(commands[0][1]).name == "audit_e2e_coverage.py"


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
