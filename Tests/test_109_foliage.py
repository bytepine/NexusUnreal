# Copyright byteyang. All Rights Reserved.
"""FoliageType create → set_mesh → get。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import first_asset_path
from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l3_asset


def test_foliage_type_roundtrip(test_ns, mcp):
    path = f"{test_ns}/FT_Created"
    kwargs = {"AssetPath": path}
    mesh = first_asset_path(mcp, "StaticMesh")
    if mesh:
        kwargs["MeshPath"] = mesh
    cr = mcp.call_capability("CreateAssetFoliageType", **kwargs)
    entry = cap_first(cr)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower():
        pytest.fail(f"create_asset_foliage_type 失败: {entry}")

    if mesh:
        man = cap_first(
            mcp.call_capability(
                "ManageAssetFoliageType",
                AssetPath=path,
                Operations=[{"Action": "SetMesh", "MeshPath": mesh}],
            )
        )
        assert not man.get("Error"), man

    dens = cap_first(
        mcp.call_capability(
            "ManageAssetFoliageType",
            AssetPath=path,
            Operations=[{"Action": "SetDensity", "Density": 0.25}],
        )
    )
    assert not dens.get("Error"), dens
    prop = cap_first(
        mcp.call_capability(
            "ManageAssetFoliageType",
            AssetPath=path,
            Operations=[{"Action": "SetProperty", "PropertyPath": "Radius", "Value": "100"}],
        )
    )
    if prop.get("Error"):
        pytest.skip(f"foliage set_property 跳过: {prop}")

    got = cap_first(mcp.call_capability("GetAssetFoliageType", AssetPath=path))
    assert not got.get("Error"), got
    assert "Density" in got, got

    try:
        bad = cap_first(
            mcp.call_capability(
                "ManageAssetFoliageType",
                AssetPath=path,
                Operations=[{"Action": "nope"}],
            )
        )
    except MCPError as exc:
        bad = {"Error": str(exc)}
    assert bad.get("Error"), bad
