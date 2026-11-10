"""首批独立能力的协议回归；游戏输入及 CommonUI 使用隔离 GUI/PIE 宿主。"""
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from _framework.mcp_client import cap_first, MCPClient, MCPError
from _framework.assertions import merge_with_defaults


def test_first_batch_live_performance(mcp, require_tools):
    require_tools("GetRuntimePerformance")
    result = cap_first(mcp.call("GetRuntimePerformance"))
    assert result["Unit"] == "ms" and result["Scope"] == "Process", result
    assert result["SampleKind"] == "LatestAvailableThreadSamples", result
    assert isinstance(result["bGpuTimingAvailable"], bool), result
    if not result["bGpuTimingAvailable"]:
        assert result["GpuTimingUnavailableReason"] and "GpuMs" not in result, result


@pytest.mark.skipif_ue_below("5.7")
def test_first_batch_csv_snapshot_and_interval(mcp, require_tools):
    require_tools("GetProfilerCsv", "ExecPython")
    filename = "FirstBatch_" + uuid.uuid4().hex + ".csv"
    contents = "placeholder\n10,1,Begin\n20,2,Middle\n30,3,End\nFrameTime,GameThread,events\n[hasheaderrowatend],1\n"
    mcp.call("ExecPython", Code=f"import pathlib, unreal\np=pathlib.Path(unreal.Paths.project_saved_dir())/'Profiling'/{filename!r}\np.parent.mkdir(parents=True,exist_ok=True)\np.write_text({contents!r},encoding='utf-8')")
    try:
        listing = cap_first(mcp.call("GetProfilerCsv", Action="Files", Limit=500))
        files = merge_with_defaults(listing["Files"], listing.get("Files_defaults", {}))
        capture = next(item["CapturePath"] for item in files if item["CapturePath"].endswith(filename))
        result = cap_first(mcp.call("GetProfilerCsv", Action="Stats", CapturePath=capture, FrameStart=1, FrameEnd=3, StatFilter="FrameTime"))
        stats = merge_with_defaults(result["Stats"], result.get("Stats_defaults", {}))
        assert len(stats) == 1 and stats[0]["Mean"] == 25 and stats[0]["Total"] == 50 and stats[0]["SampleCount"] == 2, result
        events = cap_first(mcp.call("GetProfilerCsv", Action="Events", CapturePath=capture, FrameStart=1, FrameEnd=3))
        assert events["Total"] == 2, events
    finally:
        mcp.call("ExecPython", Code=f"(pathlib.Path(unreal.Paths.project_saved_dir())/'Profiling'/{filename!r}).unlink(missing_ok=True)")


def test_first_batch_umg_diagnostic_sections(mcp, require_tools, test_ns):
    require_tools("CreateAssetUserWidget", "GetAssetUserWidget")
    created = cap_first(mcp.call("CreateAssetUserWidget", AssetPath=f"{test_ns}/WBP_FirstBatchStatic"))
    path = created.get("Path") or f"{test_ns}/WBP_FirstBatchStatic"
    read = cap_first(mcp.call("GetAssetUserWidget", AssetPath=path, Sections=["PropertyOverrides", "Connections"], Limit=2))
    assert read["bCompleteConnectionAnalysis"] is False and read["AnalysisScope"], read
    records = merge_with_defaults(read["PropertyOverrides"], read.get("PropertyOverrides_defaults", {}))
    assert all(record["bRuntimeWinnerCertain"] is False for record in records), read
    assert len(records) <= 2, read


@pytest.mark.skipif_ue_below("5.9")
@pytest.mark.requires_gui
def test_first_batch_busy_loop_keeps_protocol_responsive(mcp, require_tools):
    require_tools("ExecPython", "GetRuntimePerformance")
    code = "import unreal,time\nwith unreal.ScopedSlowTask(150,'Nexus MCP busy regression') as task:\n task.make_dialog(False)\n for i in range(150):\n  task.enter_progress_frame(1)\n  time.sleep(.02)"
    with MCPClient(mcp.url, timeout=1) as probe, ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(mcp.call, "ExecPython", Code=code)
        deadline = time.monotonic() + 2
        rejected = False
        while time.monotonic() < deadline:
            try:
                probe._rpc("tools/call", {"name": "CallCapability", "arguments": {"Capability": "GetRuntimePerformance", "Arguments": {}}})
            except MCPError as error:
                data = error.raw["error"]["data"]
                assert error.code == -32002 and data["ErrorKind"] == "EditorBusy" and data["bExecuted"] is False, error.raw
                rejected = True
                break
            time.sleep(.05)
        assert rejected, "No busy rejection observed during the slow task"
        assert probe._rpc("ping") == {}
        task.result(timeout=8)


@pytest.mark.requires_gui
@pytest.mark.l4_runtime
def test_first_batch_player_input_release(mcp, require_tools, pie):
    require_tools("InteractRuntimeInput", "GetRuntimeInput", "ExecPython")
    started = cap_first(mcp.call("InteractRuntimeInput", Action="Apply", Inputs=[{"Key": "SpaceBar"}], DurationSeconds=3))
    operation = started["OperationId"]
    try:
        active = cap_first(mcp.call("GetRuntimeInput", OperationId=operation))
        assert active["State"] == "Running" and active["bInjecting"] is True, active
        states = merge_with_defaults(active["Inputs"], active.get("Inputs_defaults", {}))
        assert states[0]["bPlayerInputKeyDown"] is True, active
        # UPlayerInput 的真实 Key 状态，而非仅检查操作对象里的标签。
        mcp.call("ExecPython", Code="import unreal\nw=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()\npc=unreal.GameplayStatics.get_player_controller(w,0)\nkey=unreal.Key()\nkey.set_editor_property('key_name','SpaceBar')\nassert pc.is_input_key_down(key), 'Injected key is not held by PlayerInput'")
        stopped = cap_first(mcp.call("InteractRuntimeInput", Action="Release", OperationId=operation))
        assert stopped["State"] == "Cancelled", stopped
        mcp.call("ExecPython", Code="assert not pc.is_input_key_down(key), 'Released key remains held'")
        tap = cap_first(mcp.call("InteractRuntimeInput", Action="Apply", Inputs=[{"Key": "SpaceBar"}], DurationSeconds=0))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = cap_first(mcp.call("GetRuntimeInput", OperationId=tap["OperationId"]))
            if result["State"] != "Running":
                break
            time.sleep(.05)
        assert result["State"] == "Completed" and result["Result"]["bInputReleased"], result
        mcp.call("ExecPython", Code="assert not pc.is_input_key_down(key)")
    finally:
        mcp.call("InteractRuntimeInput", Action="Release", OperationId=operation)
        mcp.call("ExecPython", Code="globals().pop('pc',None); globals().pop('w',None); globals().pop('key',None)")


@pytest.mark.requires_gui
@pytest.mark.l4_runtime
@pytest.mark.skipif_ue_below("5.7")
def test_first_batch_action_input_and_owner(mcp, require_tools, pie, test_ns):
    require_tools("CreateAssetInputAction", "InteractRuntimeInput", "GetRuntimeInput")
    created = cap_first(mcp.call("CreateAssetInputAction", AssetPath=f"{test_ns}/IA_FirstBatch", ValueType="Axis2D"))
    path = created.get("Path") or f"{test_ns}/IA_FirstBatch"
    operation = cap_first(mcp.call("InteractRuntimeInput", Action="Apply", Inputs=[{"AssetPath": path, "X": .5, "Y": .25}], DurationSeconds=5))
    try:
        active = cap_first(mcp.call("GetRuntimeInput", OperationId=operation["OperationId"]))
        states = merge_with_defaults(active["Inputs"], active.get("Inputs_defaults", {}))
        assert states[0]["bActionInjectionActive"] is True, active
        with MCPClient(mcp.url) as other:
            assert other.try_call("GetRuntimeInput", OperationId=operation["OperationId"]).get("isError")
            assert other.try_call("InteractRuntimeInput", Action="Release", OperationId=operation["OperationId"]).get("isError")
        assert cap_first(mcp.call("GetRuntimeInput", OperationId=operation["OperationId"]))["bInjecting"] is True
        assert mcp.try_call("InteractRuntimeInput", Action="Apply", Inputs=[{"AssetPath": path, "X": 1}], DurationSeconds=1).get("isError")
    finally:
        mcp.call("InteractRuntimeInput", Action="Release", OperationId=operation["OperationId"])


@pytest.mark.skipif_ue_below("5.9")
@pytest.mark.requires_gui
@pytest.mark.l4_runtime
def test_first_batch_commonui_snapshot_and_capture(mcp, require_tools, pie, test_ns):
    require_tools("GetCommonUIInfo", "ControlCommonUIDiagnostics", "SpawnRuntimeWidget", "CreateAssetUserWidget", "ExecPython")
    players = cap_first(mcp.call("GetCommonUIInfo", Sections=["Players"]))
    entries = merge_with_defaults(players["Players"], players.get("Players_defaults", {}))
    assert players["PlayerCount"] > 0 and entries[0]["PlayerId"], players
    state = cap_first(mcp.call("GetCommonUIInfo", Sections=["Focus", "InputRouting", "ActivatableTree"], LocalPlayerIndex=0, Limit=2))
    assert all(key in state for key in ("Focus", "InputRouting", "ActivatableTree")), state
    created = cap_first(mcp.call("CreateAssetUserWidget", AssetPath=f"{test_ns}/WBP_FirstBatchCommon", ParentClass="CommonActivatableWidget"))
    path = created.get("Path") or f"{test_ns}/WBP_FirstBatchCommon"
    operation = cap_first(mcp.call("ControlCommonUIDiagnostics", Action="Start", DurationSeconds=3, BufferSize=64))
    mcp.call("SpawnRuntimeWidget", AssetPath=path)
    mcp.call("ExecPython", Code="import unreal\nworld=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()\nwidgets=unreal.WidgetLibrary.get_all_widgets_of_class(world,unreal.CommonActivatableWidget,False)\nprobe_widget=next(widget for widget in widgets if 'WBP_FirstBatchCommon' in widget.get_class().get_name())\nprobe_widget.activate_widget()\ndel world,widgets")
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        log = cap_first(mcp.call("GetCommonUIInfo", Sections=["EventLog"], LocalPlayerIndex=-1, Epoch=operation["Epoch"], Limit=64))
        if not log["EventLogStatus"]["bLogging"]:
            break
        time.sleep(.1)
    assert log["EventLogStatus"]["bLogging"] is False and len(log["Events"]) <= 64, log
    events = merge_with_defaults(log["Events"], log.get("Events_defaults", {}))
    assert any('WBP_FirstBatchCommon' in event["WidgetClass"] and event["EventType"].endswith("Activated") for event in events), log
    stopped = cap_first(mcp.call("ControlCommonUIDiagnostics", Action="Stop", OperationId=operation["OperationId"]))
    assert stopped["State"] == "Completed", stopped
    mcp.call("ExecPython", Code="probe_widget.deactivate_widget(); probe_widget.remove_from_parent(); del probe_widget")


@pytest.mark.requires_gui
@pytest.mark.l4_runtime
def test_first_batch_input_world_cleanup(mcp, require_tools, pie):
    require_tools("InteractRuntimeInput", "GetRuntimeInput", "ControlPie")
    operation = cap_first(mcp.call("InteractRuntimeInput", Action="Apply", Inputs=[{"Key": "SpaceBar"}], DurationSeconds=30))
    mcp.call("ControlPie", Action="Stop")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        state = cap_first(mcp.call("GetRuntimeInput", OperationId=operation["OperationId"]))
        if state["State"] != "Running":
            break
        time.sleep(.1)
    assert state["State"] == "Interrupted" and state["Result"]["bInputReleased"] is True, state


@pytest.mark.requires_gui
@pytest.mark.l4_runtime
def test_first_batch_multiplayer_input_world_selection(mcp, require_tools):
    require_tools("ControlPie", "InteractRuntimeInput", "GetRuntimeInput")
    mcp.call("ControlPie", Action="Start", NetMode="ListenServer", NumberOfClients=2, bRunUnderOneProcess=True)
    try:
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            status = cap_first(mcp.call("ControlPie", Action="Status"))
            worlds = merge_with_defaults(status.get("PlayWorlds", []), status.get("PlayWorlds_defaults", {}))
            if len(worlds) >= 2:
                break
            time.sleep(.1)
        time.sleep(.5)
        status = cap_first(mcp.call("ControlPie", Action="Status"))
        worlds = merge_with_defaults(status.get("PlayWorlds", []), status.get("PlayWorlds_defaults", {}))
        assert len(worlds) == 2 and len({world["WorldPath"] for world in worlds}) == 2, status
        assert mcp.try_call("InteractRuntimeInput", Action="Apply", Inputs=[{"Key": "SpaceBar"}], DurationSeconds=1).get("isError")
        operations = []
        for world in worlds:
            operation = cap_first(mcp.call("InteractRuntimeInput", Action="Apply", WorldPath=world["WorldPath"], LocalPlayerIndex=0, Inputs=[{"Key": "SpaceBar"}], DurationSeconds=5))
            assert operation["WorldPath"] == world["WorldPath"], operation
            operations.append(operation)
        for operation in operations:
            state = cap_first(mcp.call("GetRuntimeInput", OperationId=operation["OperationId"]))
            inputs = merge_with_defaults(state["Inputs"], state.get("Inputs_defaults", {}))
            assert inputs[0]["bPlayerInputKeyDown"] is True, state
            mcp.call("InteractRuntimeInput", Action="Release", OperationId=operation["OperationId"])
    finally:
        mcp.call("ControlPie", Action="Stop")
