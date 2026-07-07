# Copyright byteyang. All Rights Reserved.
"""Pytest fixtures for the NexusLink MCP E2E suite.

Two run modes:

  Daily / CI (default):
    py Script/run_e2e.py  →  UEEditor-Cmd headless; skips l4_runtime / lua / requires_gui

  Full regression:
    py Script/run_e2e.py --gui|--full  →  UnrealEditor.exe; runs all markers

  Dev attach:
    pytest Tests --ue-url http://127.0.0.1:45000/stream
    — GUI Editor without --headless runs full suite; with --headless skips runtime markers.

See Tests/README.md for new-feature test policy.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
from pathlib import Path
from typing import Generator, List, Optional

import pytest

from _framework.capability_probe import _MissingCapabilities, require_capabilities
from _framework.mcp_client import MCPClient, MCPError, cap_first
from _framework.runtime_helpers import pie_is_running
from _framework.test_cleanup import purge_disk_test_artifacts, purge_mcp_test_assets
from _framework.ue_launcher import UELauncher, autodetect_uproject

log = logging.getLogger(__name__)


def pytest_addoption(parser: pytest.Parser) -> None:
    g = parser.getgroup("nexuslink")
    g.addoption(
        "--ue-url",
        action="store",
        default=os.environ.get("NEXUS_UE_URL"),
        help="Connect to an existing UE MCP server (e.g. http://127.0.0.1:45000/stream).",
    )
    g.addoption(
        "--ue-root",
        action="store",
        default=os.environ.get("NEXUS_UE_ROOT"),
        help="UE install root (contains Engine/Binaries). Enables auto-launch mode.",
    )
    g.addoption(
        "--uproject",
        action="store",
        default=os.environ.get("NEXUS_UE_UPROJECT"),
        help="Host .uproject for auto-launch mode. Auto-detected from the repo if omitted.",
    )
    g.addoption(
        "--keep-artifacts",
        action="store_true",
        default=False,
        help="Keep /Game/_McpTest/<ts>/ assets after the run for post-mortem.",
    )
    g.addoption(
        "--gui",
        action="store_true",
        default=False,
        help="Auto-launch UnrealEditor.exe (visible window). "
             "Default is headless UEEditor-Cmd with -nullrhi -unattended.",
    )
    g.addoption(
        "--headless",
        action="store_true",
        default=False,
        help="命令行/headless 会话：跳过 l4_runtime、lua、requires_gui 用例。",
    )


_HEADLESS_SKIP_MARKERS = frozenset({"l4_runtime", "lua", "requires_gui"})


def _is_headless_session(config: pytest.Config) -> bool:
    """headless = UEEditor-Cmd 自动拉起，或显式 --headless；--gui 或仅 --ue-url 连 GUI 不算。"""
    if config.getoption("--gui"):
        return False
    if config.getoption("--headless"):
        return True
    if config.getoption("--ue-root"):
        return True
    return False


def pytest_configure(config: pytest.Config) -> None:
    config._nexus_headless = _is_headless_session(config)  # type: ignore[attr-defined]
    if config._nexus_headless:
        log.info("headless session: skipping l4_runtime / lua / requires_gui tests")


def pytest_runtest_setup(item: pytest.Item) -> None:
    if not getattr(item.config, "_nexus_headless", False):
        return
    names = {m.name for m in item.iter_markers()}
    blocked = names & _HEADLESS_SKIP_MARKERS
    if blocked:
        pytest.skip(f"headless/命令行模式跳过（{','.join(sorted(blocked))}）")


# ─────────────────────────────────────────────────────────────
# Session-scoped fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def _test_artifact_hygiene(
    mcp: MCPClient,
    pytestconfig: pytest.Config,
) -> Generator[None, None, None]:
    """测试前后清理磁盘临时文件与 /Game/_McpTest 下全部 UE 资产。"""
    keep = bool(pytestconfig.getoption("--keep-artifacts"))
    uproject = pytestconfig.getoption("--uproject")
    resolved = Path(uproject) if uproject else autodetect_uproject()
    project_root = resolved.parent if resolved and resolved.exists() else Path.cwd()

    removed = purge_disk_test_artifacts(project_root)
    if removed:
        log.info("pre-run disk cleanup: %s", ", ".join(removed))

    if not keep:
        purge_mcp_test_assets(mcp)

    yield

    if not keep:
        purge_mcp_test_assets(mcp)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """UE 进程退出后再删磁盘日志，避免 WinError 32 文件占用。"""
    if session.config.getoption("--keep-artifacts"):
        return
    uproject = session.config.getoption("--uproject")
    resolved = Path(uproject) if uproject else autodetect_uproject()
    project_root = resolved.parent if resolved and resolved.exists() else Path.cwd()
    removed = purge_disk_test_artifacts(project_root, include_report=False)
    if removed:
        log.info("session-finish disk cleanup: %s", ", ".join(removed))


@pytest.fixture(scope="session")
def _ue_url(pytestconfig: pytest.Config) -> Generator[str, None, None]:
    direct = pytestconfig.getoption("--ue-url")
    if direct:
        log.info("using existing UE at %s", direct)
        yield direct
        return

    ue_root = pytestconfig.getoption("--ue-root")
    uproject = pytestconfig.getoption("--uproject")
    if not ue_root:
        pytest.skip(
            "no --ue-url and no --ue-root provided; "
            "start a UE Editor with NexusLink loaded and pass --ue-url."
        )
    resolved_uproject = Path(uproject) if uproject else autodetect_uproject()
    if not resolved_uproject or not resolved_uproject.exists():
        pytest.skip("could not locate .uproject for auto-launch mode")

    headless = not bool(pytestconfig.getoption("--gui"))
    with UELauncher(
        uproject=resolved_uproject,
        ue_root=Path(ue_root),
        headless=headless,
    ) as launcher:
        yield launcher.url


@pytest.fixture(scope="session")
def mcp(_ue_url: str) -> Generator[MCPClient, None, None]:
    client = MCPClient(_ue_url)
    client.initialize()
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="session")
def tool_names(mcp: MCPClient) -> List[str]:
    return [t["name"] for t in mcp.list_tools()]


@pytest.fixture(scope="session", autouse=True)
def _cache_ue_engine_version(mcp: MCPClient, pytestconfig: pytest.Config) -> None:
    """session 启动时查询 get_editor_info 缓存 UE 版本元组，供 skipif_ue_below 使用。"""
    try:
        info_list = mcp.call("get_editor_info")
        entries = info_list if isinstance(info_list, list) else [info_list]
        for entry in entries:
            if isinstance(entry, dict):
                ver_str = entry.get("engineVersion", "")
                if ver_str:
                    parts = ver_str.split(".")
                    if len(parts) >= 2:
                        pytestconfig._nexus_ue_version = (int(parts[0]), int(parts[1]))  # type: ignore[attr-defined]
                        log.info("UE version detected: %s.%s", parts[0], parts[1])
                        break
    except Exception as exc:
        log.warning("无法获取 UE 版本（skipif_ue_below 将默认 skip）: %s", exc)


@pytest.fixture(autouse=True)
def _check_skipif_ue_below(request: pytest.FixtureRequest) -> None:
    """每个测试前检查 skipif_ue_below marker，对版本不足的测试 skip。"""
    marker = request.node.get_closest_marker("skipif_ue_below")
    if marker is None:
        return
    threshold_str = str(marker.args[0]) if marker.args else "5.0"
    parts = threshold_str.split(".")
    required = (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
    ue_version: Optional[tuple] = getattr(request.config, "_nexus_ue_version", None)
    if ue_version is None:
        pytest.skip(f"UE 版本未知，跳过（需 {threshold_str}+）")
    if ue_version < required:
        pytest.skip(f"UE {ue_version[0]}.{ue_version[1]} < {threshold_str}，跳过")


def skipif_ue_below(major: int, minor: int = 0):
    """返回 pytest.mark.skipif_ue_below 标记，供 _check_skipif_ue_below autouse fixture 按版本跳过。
    用法：@skipif_ue_below(5, 1)"""
    return pytest.mark.skipif_ue_below(f"{major}.{minor}")


def _require_tools(mcp: MCPClient, required: List[str]) -> None:
    try:
        require_capabilities(mcp, *required)
    except _MissingCapabilities as exc:
        pytest.skip(str(exc))


@pytest.fixture(scope="session")
def require_tools(mcp: MCPClient):
    """Callable fixture: require_tools(['search_asset', 'get_asset'])."""

    def _f(*required: str) -> None:
        _require_tools(mcp, list(required))

    return _f


@pytest.fixture(scope="session")
def test_ns(mcp: MCPClient, pytestconfig: pytest.Config) -> Generator[str, None, None]:
    """Session-scoped /Game/_McpTest/<ts> 命名空间；资产由 _test_artifact_hygiene 统一清理。"""
    ns = f"/Game/_McpTest/{int(time.time())}"
    log.info("test namespace: %s", ns)
    yield ns

    if pytestconfig.getoption("--keep-artifacts"):
        log.info("--keep-artifacts set; leaving %s and siblings under /Game/_McpTest", ns)


# ─────────────────────────────────────────────────────────────
# PIE fixture (opt-in)
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def pie(mcp: MCPClient) -> Generator[None, None, None]:
    """Session-wide PIE: started once for tests marked l4_runtime.

    Tests that do NOT request this fixture will not start PIE. The fixture
    tolerates already-running PIE (idempotent start) and best-effort stops
    on teardown.
    """
    with contextlib.suppress(MCPError):
        status = mcp.call("control_pie", action="status")
        if not pie_is_running(status):
            mcp.call("control_pie", action="start")
            time.sleep(2.0)
    try:
        yield
    finally:
        with contextlib.suppress(MCPError):
            mcp.call("control_pie", action="stop")
