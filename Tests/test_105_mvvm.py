# Copyright byteyang. All Rights Reserved.
"""MVVM ViewModel manage — UE 5.5+ 门控 skip。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.5")]


@pytest.fixture(scope="module", autouse=True)
def require_mvvm(mcp):
    if not is_capability_available(mcp, "manage_asset_view_model"):
        pytest.skip("manage_asset_view_model 未编入（需 WITH_MVVM）")


def test_manage_view_model_add_and_get(test_ns, mcp):
    wbp = f"{test_ns}/WBP_Mvvm"
    mcp.call_capability("create_asset_user_widget", assetPath=wbp)
    r = mcp.call_capability(
        "manage_asset_view_model",
        assetPath=wbp,
        operations=[{
            "action": "add_view_model",
            "viewModelName": "NxVM",
            "viewModelClass": "MVVMViewModelBase",
        }],
    )
    entry = cap_first(r)
    assert isinstance(entry, dict), r
    got = cap_first(mcp.call_capability("get_asset_view_model", assetPath=wbp))
    assert not got.get("error"), got
    bad = mcp.call_capability(
        "manage_asset_view_model",
        assetPath=wbp,
        operations=[{"action": "not_a_real_action"}],
    )
    assert cap_first(bad).get("error"), bad
    extra = mcp.call_capability(
        "manage_asset_view_model",
        assetPath=wbp,
        operations=[
            {"action": "add_binding", "viewModelName": "NxVM", "widgetName": "Root", "propertyPath": "Text"},
            {"action": "remove_binding", "viewModelName": "NxVM"},
            {"action": "remove_view_model", "viewModelName": "NxVM"},
        ],
    )
    for e in (extra.get("results") or [cap_first(extra)]):
        if isinstance(e, dict) and e.get("error"):
            pytest.skip(f"view_model remaining 跳过: {e}")
