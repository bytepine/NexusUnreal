# Copyright byteyang. All Rights Reserved.
"""StringTable 往返 + Font get/manage。"""

from __future__ import annotations

import pytest

from _framework.asset_helpers import first_asset_path
from _framework.mcp_client import MCPError, cap_first

pytestmark = pytest.mark.l3_asset


def test_string_table_roundtrip(test_ns, mcp):
    # 不要叫 ST_Created：test_97_statetree_manage 用同名建 StateTree，会抢同一个包
    path = f"{test_ns}/StrTable_Created"
    cr = mcp.call_capability("CreateAssetStringTable", AssetPath=path, Namespace="NxTest")
    entry = cap_first(cr)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower():
        pytest.fail(f"create_asset_string_table 失败: {entry}")

    man = mcp.call_capability(
        "ManageAssetStringTable",
        AssetPath=path,
        Operations=[{"Action": "AddKey", "Key": "Hello", "Source": "World"}],
    )
    m = cap_first(man)
    assert not m.get("Error"), man

    got = cap_first(mcp.call_capability("GetAssetStringTable", AssetPath=path))
    assert not got.get("Error"), got
    keys = got.get("Keys") or []
    assert any(isinstance(k, dict) and k.get("Key") == "Hello" for k in keys), got

    extra = mcp.call_capability(
        "ManageAssetStringTable",
        AssetPath=path,
        Operations=[
            {"Action": "SetSource", "Key": "Hello", "Source": "World2"},
            {"Action": "RemoveKey", "Key": "Hello"},
        ],
    )
    for e in (extra.get("Results") or [cap_first(extra)]):
        if isinstance(e, dict):
            assert not e.get("Error"), extra

    try:
        bad = cap_first(
            mcp.call_capability(
                "ManageAssetStringTable",
                AssetPath=path,
                Operations=[{"Action": "not_a_real_action", "Key": "x"}],
            )
        )
    except MCPError as exc:
        bad = {"Error": str(exc)}
    assert bad.get("Error"), bad


def test_font_get_manage(mcp, test_ns):
    path = first_asset_path(mcp, "Font", path_filter="/Engine/") or first_asset_path(mcp, "Font")
    if not path:
        pytest.skip("未找到 Font 资产")
    copy = f"{test_ns}/Font_SetProperty"
    mcp.call("DuplicateAsset", AssetPath=path, DestAssetPath=copy)
    before = cap_first(mcp.call("GetAssetFont", AssetPath=copy))["ScalingFactor"]
    value = 1.25 if before != 1.25 else 1.5
    man = cap_first(
        mcp.call_capability(
            "ManageAssetFont",
            AssetPath=copy,
            Operations=[{"Action": "SetProperty", "PropertyPath": "ScalingFactor", "Value": str(value)}],
        )
    )
    assert man["PropertyPath"] == "ScalingFactor" and float(man["OldValue"]) == pytest.approx(before), man
    assert float(man["NewValue"]) == cap_first(mcp.call("GetAssetFont", AssetPath=copy))["ScalingFactor"] == value
