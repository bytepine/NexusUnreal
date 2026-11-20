# Copyright byteyang. All Rights Reserved.
"""CommonUI Style create/get（UE5+ 插件门控 skip）。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.0")]


@pytest.fixture(scope="module", autouse=True)
def require_common_ui(mcp):
    if not is_capability_available(mcp, "CreateAssetCommonButtonStyle"):
        pytest.skip("CommonUI capability 未编入（需 WITH_COMMON_UI）")


@pytest.mark.parametrize(("kind", "manage", "field", "value"), [
    ("CommonButtonStyle", "ManageAssetCommonButtonStyle", "ButtonPadding.Left", "3"),
    ("CommonTextStyle", "ManageAssetCommonTextStyle", "Font.Size", "16"),
])
def test_common_ui_styles(test_ns, mcp, kind, manage, field, value):
    path = f"{test_ns}/{kind}_Created"
    mcp.call_capability(f"CreateAsset{kind}", AssetPath=path)
    got = cap_first(mcp.call_capability(f"GetAsset{kind}", AssetPath=path))
    assert got["Name"], got
    operation = {"Action": "SetProperty", "PropertyPath": field, "Value": value}
    result = cap_first(mcp.call_capability(manage, AssetPath=path, Operations=[operation]))
    assert result["PropertyPath"] == field and "OldValue" in result, result
    assert float(result["NewValue"]) == float(value), result
    rejected = mcp.try_call(manage, AssetPath=path, Operations=[dict(operation, Value="")])
    assert rejected.get("isError") and "SetProperty requires PropertyPath and value" in str(rejected), rejected
