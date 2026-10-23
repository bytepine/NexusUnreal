# Copyright byteyang. All Rights Reserved.
"""阶段三：Struct + DataTable — 覆盖批量字段 / 行 操作。"""

from __future__ import annotations

import pytest

from _framework.assertions import assert_tool_error
from _framework.mcp_client import MCPError, cap_first

from _framework.assertions import assert_batch_success, assert_success_count

pytestmark = pytest.mark.l3_asset


@pytest.fixture(scope="module")
def struct_path(test_ns, mcp):
    path = f"{test_ns}/S_TestItem"
    mcp.call("CreateAssetStruct", AssetPath=path)
    yield path


@pytest.fixture(scope="module")
def datatable_path(test_ns, mcp, struct_asset_name):
    path = f"{test_ns}/DT_TestItems"
    mcp.call("CreateAssetDataTable", AssetPath=path, RowStructName=struct_asset_name)
    yield path


@pytest.fixture(scope="module")
def struct_asset_name(struct_path):
    # Struct asset name is the basename; create_data_table wants the asset name
    return struct_path.rsplit("/", 1)[-1]


def test_struct_field_batch_init(mcp, struct_path):
    """3.1–3.2：批量 add/remove/add/add — 关键批量用例。"""
    r = mcp.call(
        "ManageAssetStructField",
        AssetPath=struct_path,
        Operations=[
            {"Action": "Add", "FieldName": "ItemName", "FieldType": "string"},
            {"Action": "Remove", "FieldName": "MemberVar_0"},
            {"Action": "Add", "FieldName": "ItemCount", "FieldType": "int"},
            {"Action": "Add", "FieldName": "IsActive",  "FieldType": "bool",
             "DefaultValue": "true"},
        ],
    )
    assert_success_count(r, 4, context="struct batch init")


def test_struct_fields_visible(mcp, struct_path):
    r = mcp.call_capability("GetAssetStruct", AssetPath=struct_path)
    dump = str(r)
    for expected in ["ItemName", "ItemCount", "IsActive"]:
        assert expected in dump, f"field {expected} missing from struct dump: {dump}"


def test_struct_field_rename_retype(mcp, struct_path):
    r = mcp.call(
        "ManageAssetStructField",
        AssetPath=struct_path,
        Operations=[
            {"Action": "Set", "FieldName": "ItemCount",
             "NewName": "ItemPrice", "NewType": "float"},
        ],
    )
    assert_success_count(r, 1, context="struct rename")


def test_save_struct(mcp, struct_path):
    r = mcp.call("SaveAsset", AssetPath=struct_path)
    assert (r.get("bSaved") or 0) == 1, f"save_asset struct: {r!r}"


def test_datatable_row_batch_add(mcp, datatable_path):
    r = mcp.call(
        "ManageAssetDataTable",
        AssetPath=datatable_path,
        Operations=[
            {"Action": "Add", "RowName": "Row_001"},
            {"Action": "Add", "RowName": "Row_002"},
        ],
    )
    assert_success_count(r, 2, context="datatable add")


def test_datatable_row_get_batch(mcp, datatable_path):
    r = mcp.call("GetAssetDataTable",
                 AssetPath=datatable_path,
                 Mode="Rows",
                 RowNames=["Row_001", "Row_002"])
    assert_batch_success(r, expected_count=2, context="datatable get batch")


def test_datatable_row_get_by_name_filter(mcp, datatable_path):
    """Mode=rows + nameFilter（不带 rowNames）应按过滤条件解出行名并导出字段——
    此前 nameFilter 只在 schema 分支生效，rows 分支强制要求 rowNames。"""
    r = mcp.call("GetAssetDataTable",
                 AssetPath=datatable_path,
                 Mode="Rows",
                 NameFilter="Row_00")
    assert_batch_success(r, expected_count=2, context="datatable rows by nameFilter")


def test_datatable_row_mode_requires_rownames_or_namefilter(mcp, datatable_path):
    """Mode=rows 且 rowNames/nameFilter 均空——应报 arg_invalid 级错误，而不是此前的
    仅接受 rowNames 的强校验。"""
    with pytest.raises(MCPError) as exc_info:
        mcp.call_capability("GetAssetDataTable", AssetPath=datatable_path, Mode="Rows")
    assert "RowNames or NameFilter" in str(exc_info.value), exc_info.value


def test_datatable_set_row_error_path(mcp, datatable_path, require_tools):
    """不存在的行与字段须返回 isError，同时保留条目级错误详情。"""
    require_tools("ManageAssetDataTable")
    r = assert_tool_error(mcp.try_call(
        "ManageAssetDataTable",
        AssetPath=datatable_path,
        Operations=[
            {"Action": "Set", "RowName": "__NoSuchRow__",
             "FieldName": "__NoSuchField__", "Value": "x"},
        ],
    ))
    assert isinstance(r, dict), r
    entry = cap_first(r)
    assert entry.get("Error"), f"expected per-result error: {entry!r}"


def test_datatable_row_remove(mcp, datatable_path):
    r = mcp.call(
        "ManageAssetDataTable",
        AssetPath=datatable_path,
        Operations=[{"Action": "Remove", "RowName": "Row_002"}],
    )
    assert_success_count(r, 1, context="datatable remove")


def test_save_datatable(mcp, datatable_path):
    r = mcp.call("SaveAsset", AssetPath=datatable_path)
    assert (r.get("bSaved") or 0) == 1, f"save_asset datatable: {r!r}"
