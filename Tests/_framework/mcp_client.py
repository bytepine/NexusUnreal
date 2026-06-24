# Copyright byteyang. All Rights Reserved.
"""Tiny MCP Streamable HTTP client for the pytest E2E suite.

Only exposes what the tests need:
- initialize / notifications/initialized handshake
- tools/list
- tools/call (returns the parsed structuredContent on success or raises)

No async, no SSE — NexusLink always returns the full response on POST /stream.
"""

from __future__ import annotations

import itertools
import json
import logging
from typing import Any, Dict, Iterable, List, Optional

import httpx

from _framework.legacy_map import LEGACY_CAP_NAMES, META_TOOLS

log = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-06-18"
_SESSION_HEADER = "Mcp-Session-Id"


class MCPError(RuntimeError):
    """Raised when the MCP server returns a JSON-RPC error or an isError tool result."""

    def __init__(self, message: str, *, code: Optional[int] = None, tool: Optional[str] = None,
                 raw: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.tool = tool
        self.raw = raw


class MCPClient:
    """Synchronous MCP Streamable HTTP client bound to a single session."""

    def __init__(self, url: str, *, timeout: float = 30.0):
        if not url.rstrip("/").endswith("/stream"):
            # Accept both bare "http://host:port" and "http://host:port/stream"
            url = url.rstrip("/") + "/stream"
        self.url = url
        self._session_id: Optional[str] = None
        self._ids = itertools.count(1)
        self._http = httpx.Client(timeout=timeout)

    # ---- connection lifecycle ----

    def initialize(self) -> Dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": next(self._ids),
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "clientInfo": {"name": "nexus-pytest", "version": "1.0.0"},
                "capabilities": {},
            },
        }
        resp = self._http.post(self.url, json=payload)
        resp.raise_for_status()
        session_id = resp.headers.get(_SESSION_HEADER)
        if not session_id:
            raise MCPError("initialize response missing Mcp-Session-Id header")
        self._session_id = session_id

        result = self._unpack_rpc(resp.json())
        # Send 'initialized' notification (no id, no response expected)
        note = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        self._http.post(self.url, json=note, headers=self._session_headers())
        return result

    def close(self) -> None:
        try:
            self._http.close()
        except Exception:  # noqa: BLE001
            pass

    def __enter__(self) -> "MCPClient":
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ---- MCP methods ----

    def list_tools(self) -> List[Dict[str, Any]]:
        result = self._rpc("tools/list")
        return result.get("tools", [])

    def call(self, tool: str, **arguments: Any) -> Dict[str, Any]:
        """Backward-compatible call.

        - Meta-tools (search_capabilities / call_capability / submit_feedback / proxy tools):
          called directly via tools/call.
        - All other names: routed through the call_capability meta-tool, with legacy name
          translation applied automatically (see _framework/legacy_map.py).

        Raises MCPError on tool-level (isError: true) or JSON-RPC errors.
        """
        if tool in META_TOOLS:
            return self._tool_call_raw(tool, arguments)
        cap_name = LEGACY_CAP_NAMES.get(tool, tool)
        return self._tool_call_raw("call_capability", {"capability": cap_name, "arguments": arguments})

    def call_capability(self, name: str, arguments: Optional[Dict[str, Any]] = None,
                        **kwargs: Any) -> Dict[str, Any]:
        """Preferred API: invoke a capability by its exact current name.

        Equivalent to call_capability(capability=name, arguments={...}).
        Raises MCPError on tool-level or JSON-RPC errors.
        """
        all_args: Dict[str, Any] = dict(arguments or {}, **kwargs)
        return self._tool_call_raw("call_capability", {"capability": name, "arguments": all_args})

    def try_call(self, tool: str, **arguments: Any) -> Dict[str, Any]:
        """Call a tool but return the full result object (including isError)
        without raising. Tests that intentionally probe error paths use this.

        Routes through call_capability for non-meta-tools, same as call().
        """
        if tool in META_TOOLS:
            return self._rpc("tools/call", {"name": tool, "arguments": arguments})
        cap_name = LEGACY_CAP_NAMES.get(tool, tool)
        return self._rpc("tools/call", {"name": "call_capability",
                                        "arguments": {"capability": cap_name, "arguments": arguments}})

    def _tool_call_raw(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tools/call and unpack structuredContent. Raises MCPError on isError."""
        result = self._rpc("tools/call", {"name": tool, "arguments": arguments})
        if result.get("isError"):
            content = result.get("content") or []
            text = content[0].get("text", "") if content else ""
            raise MCPError(f"{tool}: {text}", tool=tool, raw=result)
        structured = result.get("structuredContent")
        if structured is not None:
            return structured
        # Fallback: text-only content; parse JSON if possible.
        content = result.get("content") or []
        if content:
            text = content[0].get("text", "")
            try:
                return json.loads(text)
            except Exception:  # noqa: BLE001
                return {"_text": text}
        return {}

    # ---- low-level ----

    def _session_headers(self) -> Dict[str, str]:
        if not self._session_id:
            raise MCPError("MCP session not initialized; call initialize() first")
        return {_SESSION_HEADER: self._session_id}

    def _rpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": next(self._ids),
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        resp = self._http.post(self.url, json=payload, headers=self._session_headers())
        resp.raise_for_status()
        return self._unpack_rpc(resp.json())

    @staticmethod
    def _unpack_rpc(body: Dict[str, Any]) -> Dict[str, Any]:
        if "error" in body:
            err = body["error"] or {}
            raise MCPError(
                f"JSON-RPC error {err.get('code')}: {err.get('message')}",
                code=err.get("code"),
                raw=body,
            )
        return body.get("result", {}) or {}


def cap_first(result: Dict[str, Any]) -> Dict[str, Any]:
    """call_capability 单条响应：取 results[0]，否则原样返回。"""
    results = result.get("results")
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict):
            return first
    return result


def list_asset_paths(mcp: MCPClient, path_prefix: str) -> List[str]:
    """Collect every asset path under a given /Game/... prefix (all types)."""
    out: List[str] = []
    try:
        r = mcp.call_capability("search_asset", assetType="all", pathFilter=path_prefix, limit=500)
    except MCPError as e:
        log.warning("search_asset failed while enumerating %s: %s", path_prefix, e)
        return out
    # 新版返回 {"results":[{...,"assets":[...]}]}，旧版顶层 assets；cap_first 兼容两者
    payload = cap_first(r)
    for item in payload.get("assets", []) or []:
        p = item.get("assetPath") or item.get("path")
        if p and p.startswith(path_prefix):
            out.append(p)
    return out
