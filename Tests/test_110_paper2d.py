# Copyright byteyang. All Rights Reserved.
"""Paper2D Sprite/Flipbook（插件门控 skip）。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l3_asset


@pytest.fixture(scope="module", autouse=True)
def require_paper2d(mcp):
    if not is_capability_available(mcp, "create_asset_paper_sprite"):
        pytest.skip("Paper2D capability 未编入（需 WITH_PAPER2D）")


def test_paper_sprite_flipbook(test_ns, mcp):
    sp = f"{test_ns}/PS_Created"
    cr = mcp.call_capability("create_asset_paper_sprite", assetPath=sp)
    entry = cap_first(cr)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower():
        pytest.fail(f"create_asset_paper_sprite 失败: {entry}")
    got = cap_first(mcp.call_capability("get_asset_paper_sprite", assetPath=sp))
    assert not got.get("error"), got

    fb = f"{test_ns}/PF_Created"
    cr2 = mcp.call_capability("create_asset_paper_flipbook", assetPath=fb)
    e2 = cap_first(cr2)
    if e2.get("error") and "already exists" not in str(e2.get("error")).lower():
        pytest.fail(f"create_asset_paper_flipbook 失败: {e2}")
    man = cap_first(
        mcp.call_capability(
            "manage_asset_paper_flipbook",
            assetPath=fb,
            operations=[
                {"action": "add_key", "spritePath": sp, "frameRun": 1},
                {"action": "set_frames_per_second", "framesPerSecond": 12},
            ],
        )
    )
    assert not man.get("error"), man
    got_fb = cap_first(mcp.call_capability("get_asset_paper_flipbook", assetPath=fb))
    assert not got_fb.get("error"), got_fb
