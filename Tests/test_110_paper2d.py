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
    rm_key = cap_first(
        mcp.call_capability(
            "manage_asset_paper_flipbook",
            assetPath=fb,
            operations=[{"action": "remove_key", "keyIndex": 0}],
        )
    )
    assert not rm_key.get("error"), rm_key


def test_paper_sprite_manage_source_pivot(test_ns, mcp):
    sp = f"{test_ns}/PS_Manage"
    cr = mcp.call_capability("create_asset_paper_sprite", assetPath=sp)
    entry = cap_first(cr)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower():
        pytest.fail(f"create_asset_paper_sprite 失败: {entry}")
    tex = None
    listing = mcp.call_capability(
        "search_asset", assetType="Texture2D", pathFilter="/Game/", limit=5
    )
    payload = cap_first(listing)
    for row in payload.get("assets") or []:
        tex = row.get("assetPath") or row.get("path")
        if tex:
            break
    ops = [{"action": "set_pivot", "pivotX": 0.5, "pivotY": 0.5}]
    if tex:
        ops.insert(0, {"action": "set_source", "sourceTexturePath": tex})
    r = mcp.call_capability("manage_asset_paper_sprite", assetPath=sp, operations=ops)
    for e in (r.get("results") or [cap_first(r)]):
        if isinstance(e, dict):
            assert not e.get("error"), r


def test_paper_tile_map_create_get_manage(test_ns, mcp):
    if not is_capability_available(mcp, "create_asset_paper_tile_map"):
        pytest.skip("create_asset_paper_tile_map 未编入")
    path = f"{test_ns}/PTM_Created"
    cr = mcp.call_capability(
        "create_asset_paper_tile_map",
        assetPath=path,
        mapWidth=8,
        mapHeight=8,
        tileWidth=32,
        tileHeight=32,
    )
    entry = cap_first(cr)
    if entry.get("error") and "already exists" not in str(entry.get("error")).lower():
        pytest.fail(f"create_asset_paper_tile_map 失败: {entry}")
    got = cap_first(mcp.call_capability("get_asset_paper_tile_map", assetPath=path))
    assert not got.get("error"), got

    tile_set = None
    listing = mcp.call_capability(
        "search_asset", assetType="PaperTileSet", pathFilter="/Game/", limit=3
    )
    for row in (cap_first(listing).get("assets") or []):
        tile_set = row.get("assetPath") or row.get("path")
        if tile_set:
            break
    ops = [
        {"action": "set_map_size", "mapWidth": 4, "mapHeight": 4},
        {"action": "set_tile_size", "tileWidth": 16, "tileHeight": 16},
        {"action": "add_layer", "layerName": "NxLayer"},
        {"action": "set_layer_name", "layerIndex": 0, "layerName": "NxBase"},
    ]
    if tile_set:
        ops.insert(2, {"action": "set_tileset", "tileSetPath": tile_set})
        ops.extend(
            [
                {"action": "set_cell", "layerIndex": 0, "x": 0, "y": 0, "tileIndex": 0},
                {"action": "clear_cell", "layerIndex": 0, "x": 0, "y": 0},
            ]
        )
    r = mcp.call_capability("manage_asset_paper_tile_map", assetPath=path, operations=ops)
    for e in (r.get("results") or [cap_first(r)]):
        if isinstance(e, dict):
            assert not e.get("error"), r
    rm = mcp.call_capability(
        "manage_asset_paper_tile_map",
        assetPath=path,
        operations=[{"action": "remove_layer", "layerIndex": 1}],
    )
    rm_e = cap_first(rm)
    if rm_e.get("error"):
        pytest.skip(f"remove_layer 跳过: {rm_e}")
