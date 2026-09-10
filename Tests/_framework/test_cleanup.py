# Copyright byteyang. All Rights Reserved.
"""pytest / run_e2e 临时产物清理：磁盘日志 + UE 测试命名空间资产。"""

from __future__ import annotations

import contextlib
import logging
import shutil
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from _framework.mcp_client import MCPClient, MCPError, list_asset_paths

log = logging.getLogger(__name__)

# 现行 test_ns = /Game/_McpTest/<ts>；_NexusTest 为 test_103–106 曾硬编码的历史路径
MCP_TEST_PREFIX = "/Game/_McpTest"
NEXUS_TEST_PREFIX = "/Game/_NexusTest"
TEST_ASSET_PREFIXES: Sequence[str] = (MCP_TEST_PREFIX, NEXUS_TEST_PREFIX)

CONTENT_MCP_TEST_DIR = Path("Content") / "_McpTest"
CONTENT_NEXUS_TEST_DIR = Path("Content") / "_NexusTest"
CONTENT_TEST_DIRS: Sequence[Path] = (CONTENT_MCP_TEST_DIR, CONTENT_NEXUS_TEST_DIR)

# Saved/ 已在 .gitignore；此处只删测试 runner 写入的固定文件名
_DISK_ARTIFACT_NAMES = (
    "UE-auto-launch.stdout.log",
    "UE-auto-launch-build.log",
    "TestReport.xml",
)


def purge_disk_test_artifacts(
    project_root: Path,
    *,
    include_report: bool = True,
) -> List[str]:
    """删除本地 pytest/e2e 临时文件。返回已删路径（相对 project_root）。

    ``include_report=False`` 时保留本轮 ``TestReport.xml``（供跑完立即查看）。
    """
    root = project_root.resolve()
    deleted: List[str] = []

    logs_dir = root / "Saved" / "Logs"
    if logs_dir.is_dir():
        names = _DISK_ARTIFACT_NAMES if include_report else tuple(
            n for n in _DISK_ARTIFACT_NAMES if n != "TestReport.xml"
        )
        for name in names:
            path = logs_dir / name
            if path.is_file():
                _unlink(path, root, deleted)
        for path in logs_dir.glob("Automation-*.stdout.log"):
            if path.is_file():
                _unlink(path, root, deleted)

    for rel in CONTENT_TEST_DIRS:
        content_tree = root / rel
        if content_tree.is_dir():
            try:
                shutil.rmtree(content_tree)
                deleted.append(str(content_tree.relative_to(root)))
            except OSError as exc:
                log.warning("failed to delete %s: %s", content_tree, exc)

    content_dir = root / "Content"
    if content_dir.is_dir():
        for path in content_dir.glob("__nexus_*__.uasset"):
            if path.is_file():
                _unlink(path, root, deleted)

    return deleted


def purge_mcp_test_assets(
    mcp: MCPClient,
    *,
    prefix: Optional[str] = None,
    prefixes: Optional[Iterable[str]] = None,
) -> int:
    """删除测试命名空间下全部 UE 资产（含历史 `_NexusTest`）。返回删除条数。

    默认同时清理 ``TEST_ASSET_PREFIXES``；``prefix`` 仅清一个（旧调用兼容）。
    """
    if prefixes is not None:
        targets = tuple(prefixes)
    elif prefix is not None:
        targets = (prefix,)
    else:
        targets = tuple(TEST_ASSET_PREFIXES)

    deleted = 0
    for target in targets:
        deleted += _purge_prefix(mcp, target)
    return deleted


def _purge_prefix(mcp: MCPClient, prefix: str) -> int:
    paths = list_asset_paths(mcp, prefix)
    if not paths:
        return 0

    paths.sort(key=len, reverse=True)
    deleted = 0
    for asset_path in paths:
        with contextlib.suppress(MCPError):
            mcp.call("delete_asset", assetPath=asset_path)
            deleted += 1
    if deleted:
        log.info("purged %d UE asset(s) under %s", deleted, prefix)
    return deleted


def _unlink(path: Path, root: Path, deleted: List[str]) -> None:
    try:
        path.unlink()
        deleted.append(str(path.relative_to(root)))
    except OSError as exc:
        if getattr(exc, "winerror", None) == 32:
            log.debug("skip locked file %s", path)
        else:
            log.warning("failed to delete %s: %s", path, exc)
