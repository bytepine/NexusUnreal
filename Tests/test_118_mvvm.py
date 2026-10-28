# Copyright byteyang. All Rights Reserved.
"""MVVM ViewModel manage — UE 5.5+ 门控 skip。"""

from __future__ import annotations

import hashlib

import pytest

from _framework.capability_probe import is_capability_available
from _framework.mcp_client import MCPError, cap_first
from _framework.assertions import assert_batch_success, merge_with_defaults

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
    assert_batch_success(extra)


@pytest.fixture(scope="module")
def vm_class(test_ns, mcp):
    path = f"{test_ns}/BP_BindingViewModel"
    mcp.call_capability("CreateAssetBlueprint", AssetPath=path, ParentClass="MVVMViewModelBase")
    result = mcp.call_capability(
        "ManageAssetBlueprint", AssetPath=path, bCompile=True,
        Operations=[
            {"Action": "AddVariable", "VariableName": "Health", "VariableType": "float", "DefaultValue": "0.75"},
            {"Action": "AddVariable", "VariableName": "Nested", "VariableType": f"{path}.BP_BindingViewModel_C"},
        ],
    )
    assert_batch_success(result)
    return f"{path}.BP_BindingViewModel_C"


@pytest.fixture
def binding_wbp(test_ns, mcp, vm_class, request):
    # 参数化用例也使用独立资产，失败的配置不会污染下一项。
    name = hashlib.sha256(request.node.name.encode()).hexdigest()[:12]
    path = f"{test_ns}/WBP_{name}"
    mcp.call_capability("CreateAssetUserWidget", AssetPath=path)
    result = mcp.call_capability(
        "ManageAssetUserWidget", AssetPath=path, bCompile=True,
        Operations=[
            {"Action": "Add", "WidgetClass": "CanvasPanel", "WidgetName": "Root"},
            {"Action": "Add", "WidgetClass": "ProgressBar", "WidgetName": "Bar", "ParentWidget": "Root"},
            {"Action": "Add", "WidgetClass": "TextBlock", "WidgetName": "Label", "ParentWidget": "Root"},
        ],
    )
    assert_batch_success(result)
    result = mcp.call_capability(
        "ManageAssetViewModel", AssetPath=path,
        Operations=[{"Action": "AddViewModel", "ViewModelName": name, "ViewModelClass": vm_class} for name in ("First", "Second")],
    )
    assert_batch_success(result)
    return path


def _bindings(mcp, path):
    result = cap_first(mcp.call_capability("GetAssetViewModel", AssetPath=path))
    assert not result.get("Error"), result
    return merge_with_defaults(result.get("Bindings", []), result.get("Bindings_defaults", {}))


@pytest.mark.parametrize("mode", ["OneTimeToDestination", "OneTimeToSource"])
def test_mvvm_complete_binding_compile_save_readback(mcp, binding_wbp, mode):
    result = mcp.call_capability(
        "ManageAssetViewModel", AssetPath=binding_wbp, bCompile=True, bSaveToDisk=True,
        Operations=[{
            "Action": "AddBinding", "SourceContext": "ViewModel:Second", "SourcePath": "Health",
            "DestinationContext": "Widget:Bar", "DestinationPath": "Percent", "BindingType": mode,
        }],
    )
    assert_batch_success(result)
    assert result.get("bCompiled") is True and not result.get("CompileError"), result
    assert result.get("bSaved") is True, result
    binding_id = cap_first(result)["BindingId"]
    bindings = _bindings(mcp, binding_wbp)
    assert len(bindings) == 1, bindings
    binding = bindings[0]
    assert binding["Id"] == binding_id
    assert binding["SourceContext"] == "ViewModel:Second", binding
    assert binding["SourcePropertyPath"] == "Health", binding
    assert binding["DestinationContext"] == "Widget:Bar", binding
    assert binding["DestinationPropertyPath"] == "Percent", binding
    assert binding["BindingType"] == mode, binding
    removed = mcp.call_capability(
        "ManageAssetViewModel", AssetPath=binding_wbp,
        Operations=[{"Action": "RemoveBinding", "BindingId": binding_id}],
    )
    assert_batch_success(removed)
    assert _bindings(mcp, binding_wbp) == []


def test_mvvm_nested_object_path(mcp, binding_wbp):
    result = mcp.call_capability(
        "ManageAssetViewModel", AssetPath=binding_wbp, bCompile=True,
        Operations=[{
            "Action": "AddBinding", "SourceContext": "ViewModel:Second", "SourcePath": "Nested.Health",
            "DestinationContext": "Widget:Bar", "DestinationPath": "Percent", "BindingType": "OneTimeToDestination",
        }],
    )
    assert_batch_success(result)
    assert result.get("bCompiled") is True and not result.get("CompileError"), result
    binding = _bindings(mcp, binding_wbp)[0]
    assert binding["SourceContext"] == "ViewModel:Second", binding
    assert binding["SourcePropertyPath"] == "Nested.Health", binding


def test_mvvm_self_context(mcp, binding_wbp):
    result = mcp.call_capability(
        "ManageAssetViewModel", AssetPath=binding_wbp, bCompile=True,
        Operations=[{
            "Action": "AddBinding", "SourcePath": "RenderOpacity",
            "DestinationContext": "Widget:Bar", "DestinationPath": "Percent", "BindingType": "OneTimeToDestination",
        }],
    )
    assert_batch_success(result)
    assert result.get("bCompiled") is True, result
    assert _bindings(mcp, binding_wbp)[0]["SourceContext"] == "Self"


@pytest.mark.parametrize("mode", ["OneWayToDestination", "OneWayToSource", "TwoWay"])
def test_mvvm_binding_flags_and_modes(mcp, binding_wbp, mode):
    result = mcp.call_capability(
        "ManageAssetViewModel", AssetPath=binding_wbp, bCompile=True,
        Operations=[{
            "Action": "AddBinding", "SourceContext": "ViewModel:First", "SourcePath": "Health",
            "DestinationContext": "ViewModel:Second", "DestinationPath": "Health",
            "BindingType": mode, "bEnabled": False, "bCompile": False,
        }],
    )
    assert_batch_success(result)
    binding = _bindings(mcp, binding_wbp)[0]
    assert binding["BindingType"] == mode, binding
    assert binding["bEnabled"] is False and binding["bCompile"] is False, binding


@pytest.mark.parametrize("mode", ["OneWayToDestination", "OneWayToSource", "TwoWay"])
def test_mvvm_continuous_fieldnotify_binding_compiles(mcp, binding_wbp, mode):
    # UWidget 的 bIsEnabled 有原生 FieldNotify，两端都能支持持续通知。
    result = mcp.call_capability(
        "ManageAssetViewModel", AssetPath=binding_wbp, bCompile=True,
        Operations=[{
            "Action": "AddBinding", "SourceContext": "Widget:Bar", "SourcePath": "bIsEnabled",
            "DestinationContext": "Widget:Label", "DestinationPath": "bIsEnabled", "BindingType": mode,
        }],
    )
    assert_batch_success(result)
    assert result.get("bCompiled") is True and not result.get("CompileError"), result
    binding = _bindings(mcp, binding_wbp)[0]
    assert binding["BindingType"] == mode and binding["bCompile"] is True, binding


@pytest.mark.parametrize("reverse", [False, True])
def test_mvvm_explicit_unary_conversion(mcp, binding_wbp, reverse):
    discovered = cap_first(mcp.call_capability(
        "GetAssetViewModel", AssetPath=binding_wbp, bIncludeConversionFunctions=True,
        ConversionFilter="Conv_BoolToText", ConversionLimit=1,
    ))
    functions = discovered.get("ConversionFunctions", [])
    assert len(functions) == 1, discovered
    operation = {
        "Action": "AddBinding", "SourceContext": "Widget:Bar", "SourcePath": "bIsEnabled",
        "DestinationContext": "Widget:Label", "DestinationPath": "Text", "BindingType": "OneTimeToDestination",
        "ConversionFunction": functions[0],
    }
    if reverse:
        operation = {
            "Action": "AddBinding", "SourceContext": "Widget:Label", "SourcePath": "Text",
            "DestinationContext": "Widget:Bar", "DestinationPath": "bIsEnabled", "BindingType": "OneTimeToSource",
            "ReverseConversionFunction": functions[0],
        }
    result = mcp.call_capability(
        "ManageAssetViewModel", AssetPath=binding_wbp, bCompile=True, bSaveToDisk=True,
        Operations=[operation],
    )
    assert_batch_success(result)
    assert result.get("bCompiled") is True and not result.get("CompileError"), result
    assert result.get("bSaved") is True, result
    binding = _bindings(mcp, binding_wbp)[0]
    assert binding["ReverseConversionFunction" if reverse else "ConversionFunction"] == functions[0], binding
    assert binding["DestinationPropertyPath" if reverse else "SourcePropertyPath"] == "bIsEnabled", binding


def test_mvvm_missing_remove_id_keeps_existing_binding(mcp, binding_wbp):
    added = cap_first(mcp.call_capability("ManageAssetViewModel", AssetPath=binding_wbp, Operations=[{"Action": "AddBinding"}]))
    try:
        removed = mcp.call_capability("ManageAssetViewModel", AssetPath=binding_wbp, Operations=[{"Action": "RemoveBinding"}])
        assert cap_first(removed).get("Error"), removed
    except MCPError:
        pass
    bindings = _bindings(mcp, binding_wbp)
    assert len(bindings) == 1 and bindings[0]["Id"] == added["BindingId"], bindings


@pytest.mark.parametrize("patch", [
    {"SourceContext": "ViewModel:Missing"},
    {"SourceContext": "Widget:Missing"},
    {"SourcePath": "Health.NoSuchField"},
    {"SourcePath": "Health..Other"},
    {"SourcePath": ""},
    {"DestinationPath": "Missing"},
    {"DestinationContext": "Widget:Label", "DestinationPath": "Text"},
    {"ConversionFunction": "/Script/Engine.KismetTextLibrary:Missing"},
    {"ReverseConversionFunction": "/Script/Engine.KismetTextLibrary:Conv_BoolToText"},
])
def test_mvvm_invalid_binding_leaves_no_empty_entry(mcp, binding_wbp, patch):
    operation = {
        "Action": "AddBinding", "SourceContext": "ViewModel:First", "SourcePath": "Health",
        "DestinationContext": "Widget:Bar", "DestinationPath": "Percent", "BindingType": "OneTimeToDestination",
        **patch,
    }
    try:
        result = mcp.call_capability("ManageAssetViewModel", AssetPath=binding_wbp, Operations=[operation])
        assert cap_first(result).get("Error"), result
    except MCPError:
        pass
    assert _bindings(mcp, binding_wbp) == []
