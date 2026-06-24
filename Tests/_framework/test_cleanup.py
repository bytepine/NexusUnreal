# Copyright byteyang. All Rights Reserved.
"""pytest / run_e2e 临时产物清理：磁盘日志 + UE /Game/_McpTest 资产。"""

from __future__ import annotations

import contextlib
import logging
import shutil
from pathlib import Path
from typing import List

from _framework.mcp_client import MCPClient, MCPError, list_asset_paths

log = logging.getLogger(__name__)

MCP_TEST_PREFIX = "/Game/_McpTest"
CONTENT_MCP_TEST_DIR = Path("Content") / "_McpTest"

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

    content_tree = root / CONTENT_MCP_TEST_DIR
    if content_tree.is_dir():
        try:
            shutil.rmtree(content_tree)
            deleted.append(str(content_tree.relative_to(root)))
        except OSError as exc:
            log.warning("failed to delete %s: %s", content_tree, exc)

    return deleted


def purge_mcp_test_assets(
    mcp: MCPClient,
    *,
    prefix: str = MCP_TEST_PREFIX,
) -> int:
    """删除 prefix 下全部 UE 资产（含历史遗留命名空间）。返回删除条数。"""
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
