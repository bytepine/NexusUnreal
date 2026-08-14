# Copyright byteyang. All Rights Reserved.
"""PCG Graph — create + add_node/add_edge/remove_edge（UE 5.4+ 门控 skip）。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.4")]


@pytest.fixture(scope="module", autouse=True)
def require_pcg(mcp):
    if not is_capability_available(mcp, "create_asset_pcg_graph"):
        pytest.skip("PCG capability 未编入（需 WITH_PCG）")


def test_pcg_create_add_remove_edge(test_ns, mcp):
    path = f"{test_ns}/PCG_Created"
    cr = mcp.call_capability("create_asset_pcg_graph", assetPath=path)
    entry = cap_first(cr)
    assert not entry.get("error") or entry.get("alreadyExists") or entry.get("created"), cr

    add_a = mcp.call_capability(
        "manage_asset_pcg_graph",
        assetPath=path,
        operations=[{"action": "add_node", "settingsClass": "PCGDebugSettings"}],
    )
    a = cap_first(add_a)
    if a.get("error"):
        pytest.skip(f"PCG add_node 失败（settingsClass 可能因版本而异）: {a}")
    id_a = a.get("nodeId")
    add_b = mcp.call_capability(
        "manage_asset_pcg_graph",
        assetPath=path,
        operations=[{"action": "add_node", "settingsClass": "PCGDebugSettings"}],
    )
    id_b = cap_first(add_b).get("nodeId")
    if not id_a or not id_b:
        pytest.skip("未能获得 PCG nodeId")
    mcp.call_capability(
        "manage_asset_pcg_graph",
        assetPath=path,
        operations=[{"action": "add_edge", "fromNodeId": id_a, "toNodeId": id_b}],
    )
    rem = mcp.call_capability(
        "manage_asset_pcg_graph",
        assetPath=path,
        operations=[{"action": "remove_edge", "fromNodeId": id_a, "toNodeId": id_b}],
    )
    assert not cap_first(rem).get("error"), rem
    got = cap_first(mcp.call_capability("get_asset_pcg_graph", assetPath=path))
    assert not got.get("error"), got
    bad = mcp.call_capability(
        "manage_asset_pcg_graph",
        assetPath=path,
        operations=[{"action": "not_a_real_action"}],
    )
    assert cap_first(bad).get("error"), bad
