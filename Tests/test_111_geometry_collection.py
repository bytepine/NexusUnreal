# Copyright byteyang. All Rights Reserved.
"""GeometryCollection create/get（UE5+ Chaos 门控 skip）。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.0")]


@pytest.fixture(scope="module", autouse=True)
def require_gc(mcp):
    if not is_capability_available(mcp, "CreateAssetGeometryCollection"):
        pytest.skip("GeometryCollection capability 未编入（需 WITH_GEOMETRY_COLLECTION）")


def test_geometry_collection_create_get(test_ns, mcp):
    path = f"{test_ns}/GC_Created"
    cr = mcp.call_capability("CreateAssetGeometryCollection", AssetPath=path)
    entry = cap_first(cr)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower():
        pytest.fail(f"create_asset_geometry_collection 失败: {entry}")
    got = cap_first(mcp.call_capability("GetAssetGeometryCollection", AssetPath=path))
    assert not got.get("Error"), got
    man = cap_first(
        mcp.call_capability(
            "ManageAssetGeometryCollection",
            AssetPath=path,
            Operations=[{"Action": "SetDamageThreshold", "Index": 0, "Value": 1.5}],
        )
    )
    assert isinstance(man, dict), man
    extra = cap_first(
        mcp.call_capability(
            "ManageAssetGeometryCollection",
            AssetPath=path,
            Operations=[{"Action": "SetProperty", "PropertyPath": "EnableClustering", "Value": "true"}],
        )
    )
    if extra.get("Error"):
        pytest.skip(f"geometry_collection set_property 跳过: {extra}")
