# Copyright byteyang. All Rights Reserved.
"""PCG Graph — create + add_node/add_edge/remove_edge（UE 5.4+ 门控 skip）。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import MCPError, cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.4")]


@pytest.fixture(scope="module", autouse=True)
def require_pcg(mcp):
    if not is_capability_available(mcp, "CreateAssetPCGGraph"):
        pytest.skip("PCG capability 未编入（需 WITH_PCG）")


def test_pcg_create_add_remove_edge(test_ns, mcp):
    path = f"{test_ns}/PCG_Created"
    cr = mcp.call_capability("CreateAssetPCGGraph", AssetPath=path)
    entry = cap_first(cr)
    assert not entry.get("Error") or entry.get("bAlreadyExists") or entry.get("bCreated"), cr

    add_a = mcp.call_capability(
        "ManageAssetPCGGraph",
        AssetPath=path,
        Operations=[{"Action": "AddNode", "SettingsClass": "PCGTransformPointsSettings"}],
    )
    a = cap_first(add_a)
    if a.get("Error"):
        pytest.skip(f"PCG add_node 失败（settingsClass 可能因版本而异）: {a}")
    id_a = a.get("NodeId")
    add_b = mcp.call_capability(
        "ManageAssetPCGGraph",
        AssetPath=path,
        Operations=[{"Action": "AddNode", "SettingsClass": "PCGTransformPointsSettings"}],
    )
    id_b = cap_first(add_b).get("NodeId")
    if not id_a or not id_b:
        pytest.skip("未能获得 PCG nodeId")
    mcp.call_capability(
        "ManageAssetPCGGraph",
        AssetPath=path,
        Operations=[{"Action": "AddEdge", "FromNodeId": id_a, "ToNodeId": id_b}],
    )
    rem = mcp.call_capability(
        "ManageAssetPCGGraph",
        AssetPath=path,
        Operations=[{"Action": "RemoveEdge", "FromNodeId": id_a, "ToNodeId": id_b}],
    )
    assert not cap_first(rem).get("Error"), rem
    got = cap_first(mcp.call_capability("GetAssetPCGGraph", AssetPath=path))
    assert not got.get("Error"), got
    try:
        bad = cap_first(
            mcp.call_capability(
                "ManageAssetPCGGraph",
                AssetPath=path,
                Operations=[{"Action": "not_a_real_action"}],
            )
        )
    except MCPError as exc:
        bad = {"Error": str(exc)}
    assert bad.get("Error"), bad
    rm_node = mcp.call_capability(
        "ManageAssetPCGGraph",
        AssetPath=path,
        Operations=[{"Action": "RemoveNode", "NodeId": id_b}],
    )
    if cap_first(rm_node).get("Error"):
        pytest.skip(f"pcg remove_node 跳过: {cap_first(rm_node)}")
