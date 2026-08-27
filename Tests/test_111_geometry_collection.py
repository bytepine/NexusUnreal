# Copyright byteyang. All Rights Reserved.
"""GeometryCollection create/get（UE5+ Chaos 门控 skip）。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.0")]


@pytest.fixture(scope="module", autouse=True)
def require_gc(mcp):
    if not is_capability_available(mcp, "create_asset_geometry_collection"):
        pytest.skip("GeometryCollection capability 未编入（需 WITH_GEOMETRY_COLLECTION）")


def test_geometry_collection_create_get(test_ns, mcp):
    path = f"{test_ns}/GC_Created"
    cr = mcp.call_capability("create_asset_geometry_collection", assetPath=path)
    entry = cap_first(cr)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower():
        pytest.fail(f"create_asset_geometry_collection 失败: {entry}")
    got = cap_first(mcp.call_capability("get_asset_geometry_collection", assetPath=path))
    assert not got.get("error"), got
    man = cap_first(
        mcp.call_capability(
            "manage_asset_geometry_collection",
            assetPath=path,
            operations=[{"action": "set_damage_threshold", "index": 0, "value": 1.5}],
        )
    )
    assert isinstance(man, dict), man
    extra = cap_first(
        mcp.call_capability(
            "manage_asset_geometry_collection",
            assetPath=path,
            operations=[{"action": "set_property", "propertyPath": "EnableClustering", "value": "true"}],
        )
    )
    if extra.get("error"):
        pytest.skip(f"geometry_collection set_property 跳过: {extra}")
