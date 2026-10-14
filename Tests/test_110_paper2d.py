# Copyright byteyang. All Rights Reserved.
"""Paper2D Sprite/Flipbook（插件门控 skip）。"""

from __future__ import annotations

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import cap_first

pytestmark = pytest.mark.l3_asset


@pytest.fixture(scope="module", autouse=True)
def require_paper2d(mcp):
    if not is_capability_available(mcp, "CreateAssetPaperSprite"):
        pytest.skip("Paper2D capability 未编入（需 WITH_PAPER2D）")


def test_paper_sprite_flipbook(test_ns, mcp):
    sp = f"{test_ns}/PS_Created"
    cr = mcp.call_capability("CreateAssetPaperSprite", AssetPath=sp)
    entry = cap_first(cr)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower():
        pytest.fail(f"create_asset_paper_sprite 失败: {entry}")
    got = cap_first(mcp.call_capability("GetAssetPaperSprite", AssetPath=sp))
    assert not got.get("Error"), got

    fb = f"{test_ns}/PF_Created"
    cr2 = mcp.call_capability("CreateAssetPaperFlipbook", AssetPath=fb)
    e2 = cap_first(cr2)
    if e2.get("Error") and "already exists" not in str(e2.get("Error")).lower():
        pytest.fail(f"create_asset_paper_flipbook 失败: {e2}")
    man = cap_first(
        mcp.call_capability(
            "ManageAssetPaperFlipbook",
            AssetPath=fb,
            Operations=[
                {"Action": "AddKey", "SpritePath": sp, "FrameRun": 1},
                {"Action": "SetFramesPerSecond", "FramesPerSecond": 12},
            ],
        )
    )
    assert not man.get("Error"), man
    got_fb = cap_first(mcp.call_capability("GetAssetPaperFlipbook", AssetPath=fb))
    assert not got_fb.get("Error"), got_fb
    rm_key = cap_first(
        mcp.call_capability(
            "ManageAssetPaperFlipbook",
            AssetPath=fb,
            Operations=[{"Action": "RemoveKey", "KeyIndex": 0}],
        )
    )
    assert not rm_key.get("Error"), rm_key


def test_paper_sprite_manage_source_pivot(test_ns, mcp):
    sp = f"{test_ns}/PS_Manage"
    cr = mcp.call_capability("CreateAssetPaperSprite", AssetPath=sp)
    entry = cap_first(cr)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower():
        pytest.fail(f"create_asset_paper_sprite 失败: {entry}")
    tex = None
    listing = mcp.call_capability(
        "SearchAsset", AssetType="Texture2D", PathFilter="/Game/", Limit=5
    )
    payload = cap_first(listing)
    for row in payload.get("Assets") or []:
        tex = row.get("AssetPath") or row.get("Path")
        if tex:
            break
    ops = [{"Action": "SetPivot", "PivotX": 0.5, "PivotY": 0.5}]
    if tex:
        ops.insert(0, {"Action": "SetSource", "SourceTexturePath": tex})
    r = mcp.call_capability("ManageAssetPaperSprite", AssetPath=sp, Operations=ops)
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict):
            assert not e.get("Error"), r


def test_paper_tile_map_create_get_manage(test_ns, mcp):
    if not is_capability_available(mcp, "CreateAssetPaperTileMap"):
        pytest.skip("create_asset_paper_tile_map 未编入")
    path = f"{test_ns}/PTM_Created"
    cr = mcp.call_capability(
        "CreateAssetPaperTileMap",
        AssetPath=path,
        MapWidth=8,
        MapHeight=8,
        TileWidth=32,
        TileHeight=32,
    )
    entry = cap_first(cr)
    if entry.get("Error") and "already exists" not in str(entry.get("Error")).lower():
        pytest.fail(f"create_asset_paper_tile_map 失败: {entry}")
    got = cap_first(mcp.call_capability("GetAssetPaperTileMap", AssetPath=path))
    assert not got.get("Error"), got

    tile_set = None
    listing = mcp.call_capability(
        "SearchAsset", AssetType="PaperTileSet", PathFilter="/Game/", Limit=3
    )
    for row in (cap_first(listing).get("Assets") or []):
        tile_set = row.get("AssetPath") or row.get("Path")
        if tile_set:
            break
    ops = [
        {"Action": "SetMapSize", "MapWidth": 4, "MapHeight": 4},
        {"Action": "SetTileSize", "TileWidth": 16, "TileHeight": 16},
        {"Action": "AddLayer", "LayerName": "NxLayer"},
        {"Action": "SetLayerName", "LayerIndex": 0, "LayerName": "NxBase"},
    ]
    if tile_set:
        ops.insert(2, {"Action": "SetTileset", "TileSetPath": tile_set})
        ops.extend(
            [
                {"Action": "SetCell", "LayerIndex": 0, "x": 0, "y": 0, "TileIndex": 0},
                {"Action": "ClearCell", "LayerIndex": 0, "x": 0, "y": 0},
            ]
        )
    r = mcp.call_capability("ManageAssetPaperTileMap", AssetPath=path, Operations=ops)
    for e in (r.get("Results") or [cap_first(r)]):
        if isinstance(e, dict):
            assert not e.get("Error"), r
    rm = mcp.call_capability(
        "ManageAssetPaperTileMap",
        AssetPath=path,
        Operations=[{"Action": "RemoveLayer", "LayerIndex": 1}],
    )
    rm_e = cap_first(rm)
    if rm_e.get("Error"):
        pytest.skip(f"remove_layer 跳过: {rm_e}")
