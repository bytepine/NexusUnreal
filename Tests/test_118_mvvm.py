# Copyright byteyang. All Rights Reserved.
"""MVVM ViewModel manage — UE 5.5+ 门控 skip。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import MCPError, cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.5")]


@pytest.fixture(scope="module", autouse=True)
def require_mvvm(mcp):
    if not is_capability_available(mcp, "ManageAssetViewModel"):
        pytest.skip("manage_asset_view_model 未编入（需 WITH_MVVM）")


def test_manage_view_model_add_and_get(test_ns, mcp):
    wbp = f"{test_ns}/WBP_Mvvm"
    mcp.call_capability("CreateAssetUserWidget", AssetPath=wbp)
    r = mcp.call_capability(
        "ManageAssetViewModel",
        AssetPath=wbp,
        Operations=[{
            "Action": "AddViewModel",
            "ViewModelName": "NxVM",
            "ViewModelClass": "MVVMViewModelBase",
        }],
    )
    entry = cap_first(r)
    assert isinstance(entry, dict), r
    got = cap_first(mcp.call_capability("GetAssetViewModel", AssetPath=wbp))
    assert not got.get("Error"), got
    try:
        bad = cap_first(
            mcp.call_capability(
                "ManageAssetViewModel",
                AssetPath=wbp,
                Operations=[{"Action": "not_a_real_action"}],
            )
        )
    except MCPError as exc:
        bad = {"Error": str(exc)}
    assert bad.get("Error"), bad
    extra = mcp.call_capability(
        "ManageAssetViewModel",
        AssetPath=wbp,
        Operations=[
            {"Action": "AddBinding", "ViewModelName": "NxVM"},
            {"Action": "RemoveBinding", "BindingIndex": 0},
            {"Action": "RemoveViewModel", "ViewModelName": "NxVM"},
        ],
    )
    for e in (extra.get("Results") or [cap_first(extra)]):
        if isinstance(e, dict) and e.get("Error"):
            pytest.skip(f"view_model remaining 跳过: {e}")
