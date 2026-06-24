# Copyright byteyang. All Rights Reserved.
"""阶段三：Struct + DataTable — 覆盖批量字段 / 行 操作。"""

from __future__ import annotations

import pytest

from _framework.assertions import assert_batch_success, assert_success_count

pytestmark = pytest.mark.l3_asset


@pytest.fixture(scope="module")
def struct_path(test_ns, mcp):
    path = f"{test_ns}/S_TestItem"
    mcp.call("create_struct", assetPath=path)
    yield path


@pytest.fixture(scope="module")
def datatable_path(test_ns, mcp, struct_asset_name):
    path = f"{test_ns}/DT_TestItems"
    mcp.call("create_data_table", assetPath=path, rowStructName=struct_asset_name)
    yield path


@pytest.fixture(scope="module")
def struct_asset_name(struct_path):
    # Struct asset name is the basename; create_data_table wants the asset name
    return struct_path.rsplit("/", 1)[-1]


def test_struct_field_batch_init(mcp, struct_path):
    """3.1–3.2：批量 add/remove/add/add — 关键批量用例。"""
    r = mcp.call(
        "manage_struct_field",
        assetPath=struct_path,
        fields=[
            {"action": "add", "fieldName": "ItemName", "fieldType": "string"},
            {"action": "remove", "fieldName": "MemberVar_0"},
            {"action": "add", "fieldName": "ItemCount", "fieldType": "int"},
            {"action": "add", "fieldName": "IsActive",  "fieldType": "bool",
             "defaultValue": "true"},
        ],
    )
    assert_success_count(r, 4, context="struct batch init")


def test_struct_fields_visible(mcp, struct_path):
    r = mcp.call_capability("get_asset_struct", assetPath=struct_path)
    dump = str(r)
    for expected in ["ItemName", "ItemCount", "IsActive"]:
        assert expected in dump, f"field {expected} missing from struct dump: {dump}"


def test_struct_field_rename_retype(mcp, struct_path):
    r = mcp.call(
        "manage_struct_field",
        assetPath=struct_path,
        fields=[
            {"action": "set", "fieldName": "ItemCount",
             "newName": "ItemPrice", "newType": "float"},
        ],
    )
    assert_success_count(r, 1, context="struct rename")


def test_save_struct(mcp, struct_path):
    r = mcp.call("save_asset", assetPaths=[struct_path])
    assert (r.get("saved") or 0) == 1, f"save_asset struct: {r!r}"


def test_datatable_row_batch_add(mcp, datatable_path):
    r = mcp.call(
        "manage_asset_data_table",
        assetPath=datatable_path,
        rows=[
            {"action": "add", "rowName": "Row_001"},
            {"action": "add", "rowName": "Row_002"},
        ],
    )
    assert_success_count(r, 2, context="datatable add")


def test_datatable_row_get_batch(mcp, datatable_path):
    r = mcp.call("get_asset_data_table",
                 assetPath=datatable_path,
                 mode="rows",
                 rowNames=["Row_001", "Row_002"])
    assert_batch_success(r, expected_count=2, context="datatable get batch")


def test_datatable_set_row_error_path(mcp, datatable_path, require_tools):
    """覆盖 `manage_asset_data_table` set 执行链 —— DataTable 底层字段名是 UE 内部序列化名
    (`FieldName_N_GUID`)，显示名 `ItemName` 不会命中；这里显式打一个不存在的
    rowName + 不存在的 fieldName，验证批量契约：totalCount / failCount / per-result
    error 三要素齐全而不是 top-level 抛出。"""
    require_tools("manage_asset_data_table")
    r = mcp.call(
        "manage_asset_data_table",
        assetPath=datatable_path,
        rows=[
            {"action": "set", "rowName": "__NoSuchRow__",
             "fieldName": "__NoSuchField__", "value": "x"},
        ],
    )
    assert isinstance(r, dict), r
    assert r.get("totalCount") == 1, r
    assert (r.get("failCount") or 0) >= 1, r
    per = (r.get("results") or [{}])[0]
    assert per.get("error"), f"expected per-result error: {per!r}"


def test_datatable_row_remove(mcp, datatable_path):
    r = mcp.call(
        "manage_asset_data_table",
        assetPath=datatable_path,
        rows=[{"action": "remove", "rowName": "Row_002"}],
    )
    assert_success_count(r, 1, context="datatable remove")


def test_save_datatable(mcp, datatable_path):
    r = mcp.call("save_asset", assetPaths=[datatable_path])
    assert (r.get("saved") or 0) == 1, f"save_asset datatable: {r!r}"
