# Copyright byteyang. All Rights Reserved.
"""Pytest fixtures for the NexusLink MCP E2E suite.

Two run modes:

  Dev mode:
    pytest Tests --ue-url http://127.0.0.1:45000/stream
    — connects to an already-running Editor.

  CI mode:
    pytest Tests --ue-root <EnginePath> --uproject <...>.uproject
    — launches UEEditor-Cmd in the background and tears it down on exit.

Either mode yields the same `mcp` fixture.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
from pathlib import Path
from typing import Generator, List, Optional

import pytest

from _framework.mcp_client import MCPClient, MCPError, list_asset_paths
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
        "--headless",
        action="store_true",
        default=False,
        help="Auto-launch UEEditor-Cmd with -nullrhi (no window). "
             "Default is GUI mode so the user can watch pytest drive the editor.",
    )


# ─────────────────────────────────────────────────────────────
# Session-scoped fixtures
# ─────────────────────────────────────────────────────────────

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

    headless = bool(pytestconfig.getoption("--headless"))
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


def _require_tools(tool_names: List[str], required: List[str]) -> None:
    missing = [t for t in required if t not in tool_names]
    if missing:
        pytest.skip(f"required tool(s) not registered: {missing}")


@pytest.fixture(scope="session")
def require_tools(tool_names: List[str]):
    """Callable fixture: require_tools(['search_asset', 'get_asset'])."""

    def _f(*required: str) -> None:
        _require_tools(tool_names, list(required))

    return _f


@pytest.fixture(scope="session")
def test_ns(mcp: MCPClient, pytestconfig: pytest.Config) -> Generator[str, None, None]:
    """Session-scoped /Game/_McpTest/<ts> namespace + best-effort cleanup."""
    ns = f"/Game/_McpTest/{int(time.time())}"
    log.info("test namespace: %s", ns)
    yield ns

    if pytestconfig.getoption("--keep-artifacts"):
        log.info("--keep-artifacts set; leaving %s intact", ns)
        return

    try:
        paths = list_asset_paths(mcp, ns)
        if not paths:
            return
        log.info("cleaning up %d test assets under %s", len(paths), ns)
        with contextlib.suppress(MCPError):
            for p in paths:
                mcp.call("delete_asset", assetPath=p)
    except Exception as e:  # noqa: BLE001
        log.warning("test_ns cleanup failed (non-fatal): %s", e)


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
        if not status.get("isPIERunning") and status.get("state") != "running":
            mcp.call("control_pie", action="start")
            time.sleep(2.0)
    try:
        yield
    finally:
        with contextlib.suppress(MCPError):
            mcp.call("control_pie", action="stop")
