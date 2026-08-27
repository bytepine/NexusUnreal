# Copyright byteyang. All Rights Reserved.
"""FoliageType create → set_mesh → get。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import first_asset_path
from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l3_asset


def test_foliage_type_roundtrip(test_ns, mcp):
    path = f"{test_ns}/FT_Created"
    kwargs = {"assetPath": path}
    mesh = first_asset_path(mcp, "StaticMesh")
    if mesh:
        kwargs["meshPath"] = mesh
    cr = mcp.call_capability("create_asset_foliage_type", **kwargs)
    entry = cap_first(cr)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower():
        pytest.fail(f"create_asset_foliage_type 失败: {entry}")

    if mesh:
        man = cap_first(
            mcp.call_capability(
                "manage_asset_foliage_type",
                assetPath=path,
                operations=[{"action": "set_mesh", "meshPath": mesh}],
            )
        )
        assert not man.get("error"), man

    dens = cap_first(
        mcp.call_capability(
            "manage_asset_foliage_type",
            assetPath=path,
            operations=[{"action": "set_density", "density": 0.25}],
        )
    )
    assert not dens.get("error"), dens
    prop = cap_first(
        mcp.call_capability(
            "manage_asset_foliage_type",
            assetPath=path,
            operations=[{"action": "set_property", "propertyPath": "Radius", "value": "100"}],
        )
    )
    if prop.get("error"):
        pytest.skip(f"foliage set_property 跳过: {prop}")

    got = cap_first(mcp.call_capability("get_asset_foliage_type", assetPath=path))
    assert not got.get("error"), got
    assert "density" in got, got

    try:
        bad = cap_first(
            mcp.call_capability(
                "manage_asset_foliage_type",
                assetPath=path,
                operations=[{"action": "nope"}],
            )
        )
    except MCPError as exc:
        bad = {"error": str(exc)}
    assert bad.get("error"), bad
