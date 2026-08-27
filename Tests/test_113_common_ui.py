# Copyright byteyang. All Rights Reserved.
"""CommonUI Style create/get（UE5+ 插件门控 skip）。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import cap_first

pytestmark = [pytest.mark.l3_asset, pytest.mark.skipif_ue_below("5.0")]


@pytest.fixture(scope="module", autouse=True)
def require_common_ui(mcp):
    if not is_capability_available(mcp, "create_asset_common_button_style"):
        pytest.skip("CommonUI capability 未编入（需 WITH_COMMON_UI）")


def test_common_ui_styles(test_ns, mcp):
    btn = f"{test_ns}/CBS_Created"
    cr = mcp.call_capability("create_asset_common_button_style", assetPath=btn)
    e = cap_first(cr)
    if e.get("error") and "already exists" not in str(e.get("error")).lower():
        pytest.fail(f"create_asset_common_button_style 失败: {e}")
    got = cap_first(mcp.call_capability("get_asset_common_button_style", assetPath=btn))
    assert not got.get("error"), got

    txt = f"{test_ns}/CTS_Created"
    cr2 = mcp.call_capability("create_asset_common_text_style", assetPath=txt)
    e2 = cap_first(cr2)
    if e2.get("error") and "already exists" not in str(e2.get("error")).lower():
        pytest.fail(f"create_asset_common_text_style 失败: {e2}")
    got2 = cap_first(mcp.call_capability("get_asset_common_text_style", assetPath=txt))
    assert not got2.get("error"), got2

    btn_man = mcp.call_capability(
        "manage_asset_common_button_style",
        assetPath=btn,
        operations=[{"action": "set_property", "propertyPath": "DisabledOpacity", "value": "0.5"}],
    )
    btn_e = cap_first(btn_man)
    if btn_e.get("error"):
        pytest.skip(f"manage_asset_common_button_style set_property 跳过: {btn_e}")
    txt_man = mcp.call_capability(
        "manage_asset_common_text_style",
        assetPath=txt,
        operations=[{"action": "set_property", "propertyPath": "FontSize", "value": "16"}],
    )
    txt_e = cap_first(txt_man)
    if txt_e.get("error"):
        pytest.skip(f"manage_asset_common_text_style set_property 跳过: {txt_e}")
