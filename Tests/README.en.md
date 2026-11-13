# NexusUnreal — pytest E2E tests

[中文](README.md) | English

Navigation/collision feedback regressions are in `test_25_feedback_navigation_collision.py`: navigation state; bounded read-only octree/tile/BSP queries; 16 per-frame navigation projections, batch cancellation/timeouts/write preflight; mesh navigation/section/triangle diagnostics and collision refresh. Automation `NexusLink.FeedbackNov12.LiveCollision` verifies that registered components use rebuilt BodySetup; `NexusLink.Review.DirtyLevelProtection` checks specific dirty packages and StateConflict; `NexusLink.EditorOperations.SearchableCombo` verifies selection through the public base class of UE4 property combo boxes in GUI mode.

Migration feedback: Automation `NexusLink.FeedbackMigration` runs in isolated Editor-Cmd to verify fragmented UTF-8 reception/total limits, temporary SuperFunction save interception, complete restoration of zero BodyInstance values, custom event naming/conflicts, nested defaults/missing paths, typed-array set/clear and struct validation, dry-run/connection preservation when remapping same-type inherited getters, instance-owned object Schema when CDO references are null, and narrowing suggestions for broad searches. The isolated host uses empty Content and engine-matched module configuration, without loading business assets.

Related capabilities: Automation `NexusLink.EditorRelated` covers complete container-type readback and UDS metadata lifetime, inherited-component writes/restoration and owned-subobject Undo, rejection of external asset paths during restoration, scientific-notation preview/validation and no invalid-input writes, local renaming, member type changes, DataAsset/Level prior-value/readback, parent-component baselines/restoration, dedicated Blueprint reparenting, validation-only export/conflicts, disk-byte preservation on compile failure, real Recast multi-Agent/projection, and AI request state. `Tests/test_24_editor_related_capabilities.py` covers MCP read/write chains; asset-editor lists/dirty-asset close rejection, reopening edited behavior trees, and PIE AI query/stop cases use `requires_gui`.

Editor gaps: Automation `NexusLink.EditorGaps` verifies reparenting with Undo/inheritance-cycle/data-loss preconditions, full/partial paths dispatched through real NavigationSystem, no movement for plain Actors, and actual asset-editor opening/focus/validation-only behavior. Navigation uses deterministic ANavigationData fixtures without building Recast meshes. MCP cases are in `test_23_editor_feedback_gaps.py`; actual editor-opening cases use `requires_gui`, while the rest run headlessly.

Feedback regressions: `NexusLink.Review.FeedbackVariableTypesAndRename`, `NexusLink.Review.FeedbackLevelActorProperties`, `NexusLink.Review.ScsReattachAndCopy`, `NexusLink.AssetEdit.BlueprintVerification`, `NexusLink.AssetEdit.OwnedComponentPreview`, `NexusLink.Utils.PinType.ParsePrimitives`, and `NexusLink.Feedback.ReportRegression` cover Blueprint types/leaf-member renaming and subclass-default protection, level properties, component overrides, centralized compilation, and report statistics. `NexusLink.AssetEdit.ScalarPreview` also covers false/0 export. Run in an isolated Editor-Cmd host; do not replay crash-inducing batches in a business session.

`NexusLink.AssetEdit.AutomatedExport` verifies automated T3D export, output content, and file-free failure for unsupported extensions. Component preview also verifies rejection of null and external object references.

PascalCase contracts: `NexusLink.Reliability.PascalCasePayload` verifies actually registered input Schema, creation-result Name fields, and GetAsset/ManageAsset path deduplication. `NexusLink.Feedback.RoundTrip` verifies Call* classification in drafts and summary reports; `NexusLinkExt.Smoke.LuaCaps` and `NexusLinkExt.Lua.ValueToJsonStackBalance` verify Lua capability names and table-field Type metadata. Python cases and behavior-tree retest tools use the same field naming.

Review-fix regressions: UE Automation `NexusLink.Review` verifies dirty-level/external-Actor-package protection, SCS reattachment cycle rejection/root consistency, copied inherited-component override templates, and complete transform-argument preflight with side-effect-free failures. `NexusLink.Runtime.Widget.ExactInteraction` also verifies WidgetComponent list-path interaction/property read-write and rejection after hiding/unregistration. Run both in isolated Editor-Cmd with `-ExecCmds="Automation RunTests NexusLink.Review+NexusLink.Runtime.Widget.ExactInteraction" -TestExit="Automation Test Queue Empty" -unattended -nullrhi`.

Lua L1: `NexusLinkExt.Lua.ValueToJsonStackBalance` uses an independent Lua state to verify stack balance/truncation for tables of 0/1/49/50/51/120 entries, nested tables, positive/negative indexes, and cycles; PIE is unnecessary. Run that name in Session Frontend → Automation or pass `-ExecCmds="Automation RunTests NexusLinkExt.Lua.ValueToJsonStackBalance" -TestExit="Automation Test Queue Empty" -unattended -nullrhi` to Editor-Cmd. If linked optional dependencies are not enabled in the host, add `-EnablePlugins=GameFeatures,DataRegistry,GameplayTagsEditor` for the test session.

NexusLink and NexusLinkTestSuite do not directly link to or call official Toolset/Registry APIs. PCG, Niagara, ControlRig, SemanticSearch, and related cases check actual domain plugins/current APIs. Standard domain-plugin dependencies follow engine requirements; for example, UE 5.9 PCG must retain Registry. See [transitive dependency boundaries](../Plugins/NexusLink/docs/toolset-backends.en.md). Semantic search additionally needs a valid index and Embedding Provider.

Behavior-tree acceptance: after compilation, run `python Script/bt_retest_acceptance.py --ue-root <UE-directory> --output <new-output-directory>`. An independent GameModeBase server explicitly spawns the test Pawn/AIController and inherited Blackboard, verifying failure/recovery, last snapshots, cleanup, baselines, stopping trees, and target destruction. The accompanying UE Automation prefix is `NexusLink.AI.Blackboard`; the project's default GameMode is unchanged.

Performance-comparison acceptance: run UE Automation `NexusLink.Trace.GetTrace` and `NexusLink.Trace.Statistics`, then `python Script/trace_compare_acceptance.py --ue-root <UE-directory> --output <new-output-directory>`. The script starts an isolated Editor, reads an Automation-generated stopped Trace through an explicit endpoint, verifies export/offline zero-difference reports, and closes its own process afterward.

`test_00_smoke.py::test_proxy_discovery_status` checks actual HTTP `/status` discovery fields, including `server`, `wsPort`, and `authRequired`, so capability-name migrations do not break Desktop / Rider / VSCode instance scans.

## Animation, Niagara, and independent-capability regressions

UE Automation `NexusLink.AssetEdit` covers interface-implementation graphs, Unicode structural Hash, widget-variable-reference deletion, and refusing to save after partial success followed by structural-readback failure. `NexusLink.Toolsets.Compatibility` uses real host channels/types and existing PCG instances for keyframes, Niagara vectors, graph-parameter propagation, and UE 5.6 UIComponent ordering. `NexusLink.Import.MultiTakeConflicts` builds two-take FBX fixtures to verify no overwrite for Fail/Unique and readback of every Replace output. `NexusLink.Registry.AllDefinitionsValid` checks real registered definitions against startup naming/asset-routing constraints. Run with Editor-Cmd `-ExecCmds="Automation RunTests <prefix>" -TestExit="Automation Test Queue Empty" -unattended -nullrhi`; version-dependent cases adapt to the host.

`test_22_feature_gap_followups.py` covers action Schema, structural plans/readback/stale-hash rejection, first-import PNG/WAV/FBX conflicts, skeletal poses, owned task history, and read-only source-control preflight. PCG generation/point reads, two-player ListenServer PIE, and skeletal-mesh/animation FBX export fixtures require GUI/RHI and use `requires_gui`; run `py Script/run_e2e.py --gui -k gap_`. `NexusLink.EditorOperations.OwnerAndContract` also verifies cross-owner isolation for task enumeration/cancellation. Offline budget regressions live in plugin `tools/trace_compare/test_runner.py`.

`test_19_toolset_reuse.py` verifies that existing query/edit endpoints return synchronously and strictly report `Backend=Independent`; `NexusLink.Independent.SettingsAndPlugins` verifies settings/plugin query contracts. Tests do not depend on official Toolset enablement.

`test_20_editor_compatibility.py` verifies independent Blueprint GraphPlan/function parameters, UMG structure, static-mesh LOD/convex hulls, scene folders, Sequencer sections/keyframes, Niagara User Variables/Renderer, and PCG parameter round trips. GraphText cases export actual getter/setter `UnrealGraphText`, pre-import and append it to the target graph, then read back nodes/connections. Legacy Lisp and invalid node text are rejected without changing the target graph. Failed GraphPlan operations must remove their new nodes; PCG cases require UE 5.4+.

`test_23_editor_feedback_gaps.py` covers batch writes for 42 variable categories, ToolTip, Replication/RepNotify and CallInEditor readback, and rejection of invalid notify functions. `test_10_editor.py::test_manage_asset_lua_binding` verifies compiled Lua module names and repeated binding updates. `NexusLink.EditorRelated.ComponentBaseline` also checks that level SCS defaults use inherited override templates even when Actor CDO component pointers are null, and that restoration supports Undo.

`test_19_remaining_toolsets.py` covers Sequencer sections and float/bool keyframes, four-frame Control Rig baking/control-key readback, Niagara systems/renderers/user variables and nested dynamic-input writes, Game Features lifecycle, and NexusLink-owned group→tool→Schema discovery. It rejects unknown groups/capabilities and external Registry identifiers; `NexusLink.Independent.DiscoveryContract` checks the owned discovery contract.

Owned discovery works on all supported editor versions; deep animation/Niagara actions are gated by actual engine APIs rather than official Toolsets. Game Features requires UE 5.7+ `GameFeatures`; Control Rig cases additionally require the sample Mannequin mesh and Body Rig content. Cases capable of headless execution remain headless.

Lifecycle cases use only the dedicated empty Feature plugin explicitly set through `NEXUS_GAME_FEATURE_FIXTURE`. It must already be discovered by the editor, allow content, and reside in an engine-recognized Game Features directory. Without the variable, cases skip. When configured, they verify failure without GameFeatureData, creation of a test DataAsset, activation to `Active`, and deactivation to `Loaded`. Set it only in isolated test hosts; never point it at a business Feature plugin.

## Full-project startup acceptance

`Script/run_e2e.py` also forwards `--uproject` when explicitly connecting through `--ue-url` or reusing an existing editor. Supply the actual project path for isolated-host tests so disk validation and before/after cleanup target the tested project. Cleanup includes `Config/Tags/NexusMcpTest_<GUID>.ini` from Tag lifecycle tests and verifies paths remain inside the project.

After changing public C++ structs or base-class layouts, close the editor and fully rebuild every referencing module, including NexusLink, editor modules, extensions, and test plugins. Live Coding does not replace this step. Do not relink old `Intermediate` objects against new source. `Script/build_test.py` builds the complete sample in clean directories by default; when retaining isolated directories for incremental tests, ensure dependencies rebuild as well.

If the editor reports DLL `GetLastError=1114` before MCP is ready, locate the first load-stage exception; class-registration callbacks crashing after unload can be secondary symptoms. A successful build does not prove successful startup. Full acceptance also starts the matching engine in GUI mode and runs `test_00_smoke.py`, `test_15_editor_operations.py`, and the affected runtime cases. Cross-version acceptance uses separate Content/Config copies to prevent writes to the original project. `test_02_asset_edit_preview.py` follows `--uproject` for disk checks and reads the tested project's asset files. PIE fixtures start/stop per test module, so later modules do not reuse sessions invalidated by editor operations such as Automation. Runtime compression cases explicitly request PIE; Slate screenshots use the window query's returned `Ref`, independent of earlier PIE-window focus.

MVVM removal negative cases use complete compilable bindings, checking that failed removal retains the original binding and avoiding empty-binding compile dialogs that block later PIE. Slate screenshot regression uses log sequence numbers to verify that no ensure occurs during capture.

## GAS diagnostics and network retests

Generic project-integration acceptance: after compilation, run `python Script/gas_generic_retest.py --ue-root <UE-directory>`. It starts an isolated `GameModeBase` server and explicitly spawns three independent test targets (plain Actor, Pawn, PlayerState ASC), checking GenericActivation preflight, real failure tags, recovery conditions, reruns, and baseline comparison. Output defaults to `Saved/GenericGasRetest`. If the output already contains a baseline, overwriting is refused; use `--output` for a new directory. This scenario does not use `NexusDiagnosticGameMode` or change default game configuration.

`test_120_gas_diagnostics.py` verifies read-only diagnostics, existing-ability activation, event capture, and stopping in PIE. It uses `l4_runtime`; run `py Script/run_e2e.py --gui -k gas_diagnostics`. It depends on the sample's native diagnostic classes and `Config/DefaultGameplayTags.ini`; a skip is not a feature pass.

Build UE 5.7 NexusEditor first, then run:

```sh
py Script/gas_network_retest.py --ue-root <UE_5.7-directory> --repeat 10
```

For a first run, add `--quickstart`, a fixed `PredictionRejected` → `Success` cycle. The script performs read-only checks of character bindings/required abilities, reproduces rejection, and restores conditions. Open output `index.html` to compare both reports. Each scenario includes `case.json`, `report.html`, `results.json`, and `junit.xml`; startup preflight reports live in `startup/`. Without this flag, the original eight-scenario regression remains available.

The tool starts hidden standalone `-server` / `-game` / `-game` processes using the Engine Entry map and explicit `NexusDiagnosticGameMode`, leaving the default GameMode unchanged. `--uproject` can target another compiled sample-project copy. Only processes created by this run are closed afterward. Logs, generated cases, evidence, and JUnit default to `Saved/GasRetest/`.

Coverage includes abilities not granted, missing required tags, blocking tags, cooldown, insufficient cost, predicted client activation rejected by the server, and successful LocalPredicted / ServerOnly activation after recovery. The observing client checks replicated commit counts; it need not see other players' ability lists. For capabilities and JSON case format, see [GAS replay](../Plugins/NexusLink/docs/gas-retest.en.md).

### Fixed-case automated regression and archives

After compiling the diagnostic project:

```sh
py Script/gas_regression.py --ue-root <UE_5.7-directory>
```

This runs fixed `PredictionRejected` and `Success` cases through the same isolated one-server/two-client workflow. Every baseline is checked before UE starts: it must be a complete passing retest with a signature matching the current case. Verified results live in `Tests/GasRetest/baselines/`. Missing/old signatures or changed cases fail; the current run never automatically creates or replaces baselines.

Each run creates a new `Saved/GasRegression/<UTC-time>/`, or `--output <new-directory>` selects another location. Existing directories are rejected to avoid mixing old results. Supports `--baselines <directory>` and `--uproject <built-project>`. Outputs:

- `index.html` / `report.html`: fixed-case status and individual comparison links.
- `results.json` / `junit.xml`: aggregate results and per-case gate status. Failed/missing assertions fail; runtime errors and unexecuted cases are errors. Skips do not replace execution.
- `current/`: startup preflight, HTML / JSON / JUnit for executed cases, generated cases, and logs from every process.
- `comparisons/`: baseline/current comparisons retaining complete before/after evidence; event changes appear separately and are not automatically regressions.
- `run.log` / `reports.zip`: execution log and all-report archive; archiving is attempted after success, assertion failure, and baseline/configuration/runtime errors.

Exit codes: `0` means all fixed cases/baseline checks passed; `1` means assertion/baseline-check failure; `2` means baseline/configuration/runtime error, unexecuted cases, or archive failure. The network script cleans up processes and stops later scenarios on failure; automated regression explicitly marks remaining cases unexecuted. Writes are not retried.

Baseline changes require manual review: use the plugin tool's `--save-baseline` to create a new file, inspect assertions, authoritative-side events, and the case signature, then replace the version-controlled file and commit it with the case change. Aggregate reports cannot replace per-scenario baselines. UE-free gate/archive regressions: `py -m unittest discover -s Script/tests -p 'test_gas*.py'`.

The [GAS Tools Checks workflow](../.github/workflows/gas-regression.yml) runs UE-free tool checks and UE report-gate tests on GitHub-hosted Ubuntu. Users still start GAS network retests manually; the optional UE build/MCP workflow is described below. The repository does not install or register runners.

## Controlled UE 5.7 validation

[UE 5.7 Validation](../.github/workflows/ue-validation.yml) supports manual `workflow_dispatch` only, fixed to Windows x64 / UE 5.7, with no push, PR, or schedule trigger. Dispatch it from the default branch with the full 40-character SHA of a commit already merged into that branch and containing this workflow and checker. A GitHub-hosted job checks the SHA and ancestry before scheduling the engine machine. Recursive submodules follow the selected commit's exact pointers.

Before enabling it, an administrator must configure a dedicated runner with `self-hosted`, `Windows`, `X64`, and `ue-5.7` labels, and the `ue-validation` Environment: restrict it to the default branch, configure required reviewers, and set Environment variable `UE_5_7_ROOT` to the actual installation directory named `UE_5.7`, for example `D:/Epic Games/UE_5.7`. The runner needs Python 3.12, MSVC/Windows SDK, network access to install `Tests/requirements.txt`, and enough build disk space. GUI mode additionally needs a working interactive desktop and RHI; a Windows background-service session does not provide that desktop. Workflow files do not create these protections or prove runner readiness. A job waiting for a runner/approval has not passed validation. Do not share this machine with interactive development or other UE builds: the existing builder cleans up leftover build processes.

The workflow first compiles `NexusEditor` and the `Nexus` Game target in clean copies, then explicitly runs `Script/run_e2e.py --ue-root <UE_5.7> --uproject Nexus.uproject`. The launcher also runs UBT for the actual tested project, does not reuse binaries from the isolated build, and does not attach to an existing local editor. Default `headless` mode skips existing `l4_runtime` / `lua` / `requires_gui` cases; select `gui` to run those cases. Neither mode constitutes all-engine-version acceptance.

The `Script/check_ue_ci_report.py` gate requires actual passes for `/status`, meta-tools, EditorInfo, unknown-operation handling, and all five native Automation cases in `test_15_editor_operations.py`. Those existing native cases support headless execution and assert real C++ outcomes through MCP. GUI mode also requires the two Slate GUI cases. Missing/empty reports, failures/errors, or missing/skipped baseline cases fail. Other conditional skips remain counted and are not presented as passes. On the first enabled run, review remaining skip reasons and required optional fixtures manually.

Each run archives `Saved/UEValidation/source.json` (project/submodule commits, engine version, platform, and mode), JUnit, gate counts, build/E2E console output, and Editor/Game build summaries, UBT, and editor logs under `Saved/Logs/`. Logs/reports are retained for 14 days; the existing builder removes its isolated temporary tree. Release/full acceptance still needs the cross-version, GUI, GAS network, and dedicated-fixture checks relevant to the change. A green baseline does not establish that every feature passed.

This directory implements NexusLink L2 regression tests inside the **NexusUnreal sample project**.

Any failure in a batch returns `isError=true`. For expected failures, use `assert_tool_error(mcp.try_call(...))` to check both the error flag and `structuredContent`, then inspect `FailureCount`, `bRolledBack`, and per-item results. Lack of a thrown exception does not verify rollback. Blueprint CDO/runtime widgets depend on compiled classes; compile after writes. Mesh, texture, and animation writes use copies inside `test_ns`.

For shared tool-model/filtering guidance, see [NexusLink docs/testing.md](https://github.com/bytepine/NexusLink/blob/master/docs/testing.md).

## Test policy (required)

| Scenario | Required approach |
|----------|-------------------|
| **New feature / capability** | Cover **every manage `operations[].action`** and **every named section** of MultiSection gets in the relevant `test_*.py`. Write within `test_ns` (`/Game/_McpTest/<ts>/`); purge `_McpTest` and legacy `_NexusTest` after the session |
| **Coverage gate** | `py Script/audit_e2e_coverage.py` scans NexusLink / NexusLinkExt Runtime and Editor modules, comparing C++ `RegisterActions` / `GetSectionNames` with actual Python call arguments. Missing items/empty scans exit 1 before UE starts |
| **Daily / CI / developer checks** | **Headless command line by default**: `py Script/run_e2e.py` (`UEEditor-Cmd -nullrhi`, fast and windowless) |
| **Unavailable from command line** | Mark `l4_runtime` / `lua` / `requires_gui`; headless skips them, so verify in **GUI** |
| **Full regression / complete coverage** | **GUI required**: `py Script/run_e2e.py --gui` or `--full`, including PIE, UnLua, viewport/RHI |
| **NexusLink release validation** | **Choose by changes**, without changing daily defaults: editor assets/manage-get/Schema only→headless; PIE/UnLua/viewport/`l4_runtime`/`lua`/`requires_gui`/`interact_runtime_*`→`--gui`; mixed/unclear→`--gui` |

`run_e2e.py` audits coverage before cleaning test assets or connecting/starting the engine and exits immediately for gaps. It discovers C++ operations by merging explicit registrations and `Action` enums, including loop registration, without counting other parameter enums. Python AST analysis associates each call with `Operations[].Action` and `Sections`, supporting `dict(...)`, local/imported direct wrappers, `CallCapability(Calls=[...])`, container aliases, appends, loops, and paired parameterization rows. Unpassed literals and uncalled helpers do not count; audited test modules are neither imported nor executed.

Static audits prove source calls exist, not successful paths, actual execution, or assertion coverage; skips do not count as passes. Missing-argument Notify/RootMotion cases in `test_100` and unknown DataRegistry types are rejection paths; native in-memory fixtures still verify positive DataRegistry row values. Check native reports, pytest passed/skipped/failed, and optional-plugin conditions separately. C++ line/branch coverage reports are not currently generated. UE-free auditor regression: `py -m unittest discover -s Script/tests -p test_audit_e2e_coverage.py`.

Native `NexusLink.EditorRelated` / `NexusLink.EditorGaps` cases for related capabilities awaiting release assert type-change replication restrictions, descendant protection, graph-reference rebuilding/GUIDs, local-name conflicts/references, dedicated-reparenting type/skeleton/member conflicts, real Recast Filter/WorldName selection, AI arrival/rejection/consecutive-request isolation, shared-editor close protection, and actual Unique/Replace exports/file preservation on rejection. `test_24` adds corresponding MCP renaming, component/level-default readback, export content, and unrelated-window preservation. Shared-editor tests register multi-asset windows through native subsystems and run assertions via MCP in GUI.

`test_25_trace_readback.py` reads Summary/Frames/Timers/Bookmarks through MCP and verifies frames, CPU truncation, and Bookmarks. First run native `NexusLink.Trace.GetTrace.Readback` in an isolated producer process, wait for exit, then set `NEXUS_STOPPED_TRACE` to the absolute generated `Saved/Profiling/NexusLinkTraceReadTest.utrace` path. Readback cases do not start/stop recording; asynchronous analysis waits through frame-spaced queries. Missing stopped-recording fixtures explicitly skip. This case currently uses UE5+ producer fixtures; UE4 Trace integration uses the independent acceptance script described earlier.

### Choosing markers

| Marker | When to use |
|--------|-------------|
| None | Editor asset read/write, read-only probes, cases runnable headlessly |
| `l4_runtime` | PIE dependencies such as `spawn_runtime_*`, `control_pie`, `interact_runtime_*` |
| `lua` | UnLua + PIE dependencies |
| `requires_gui` | Full RHI / viewport / Slate, such as actual `capture_viewport` images or `get_asset_texture` pixels |

**Principle:** keep headless-capable cases independent of GUI. Mark only cases needing PIE/viewport and ensure full `--gui` runs reach them.

**Parameter conventions (matching NexusLink breaking changes):** capabilities target one `assetPath`/`actorName`/`widgetName`; use multiple calls or `call_capability.calls[]` for multiple targets; manage uses `operations[]`; get uses `propertyPaths[]`; spawn uses `assetPath`, not `blueprintPath`; duplicate/rename use `destAssetPath`, not `newPath`. Old keys are unsupported.

**Do not use `help *` with `exec_command`:** UE can open `ConsoleHelp.html` in the system browser in either GUI or headless mode.

MCP E2E requires Bearer authentication from `NEXUS_MCP_TOKEN`, `{Temp}/NexusLink/{PID}.json`, or the local shared `%LOCALAPPDATA%/NexusLink/mcp-auth-token`. Auto-launch adds `-EnableNexusMcp` and `-NexusEnableDangerousCaps`, enabling `exec_command` / `exec_python` / Lua eval/dofile for the session. Manual `--ue-url` connections require MCP already enabled and dangerous capabilities enabled in settings or with the same CLI flag.

## Quick start

```bash
pip install -r Tests/requirements.txt
```

### Default: headless command line (recommended daily)

```bash
py Script/run_e2e.py
# Detects or launches UEEditor-Cmd; skips l4_runtime / lua / requires_gui.
# Auto-launch ignores previously listening MCP ports, connecting to the new
# instance even when a local Editor already occupies :45000.
```

### Full: GUI Editor

```bash
py Script/run_e2e.py --gui
# Or:
py Script/run_e2e.py --full
```

### Connect to an existing Editor

```bash
py Script/run_e2e.py --ue-url http://127.0.0.1:45000/stream
# GUI Editor without --headless: full run, including runtime.
# GUI Editor with pytest --headless: runtime cases still skip.
```

### Direct pytest

```bash
pytest Tests --ue-root "E:/EpicGames/UE_5.7" --uproject Nexus.uproject          # Headless launch
pytest Tests --ue-root "E:/EpicGames/UE_5.7" --uproject Nexus.uproject --gui  # Full GUI
pytest Tests --ue-url http://127.0.0.1:45000/stream
```

## Common filters

| Command | Purpose |
|---------|---------|
| `py Script/audit_e2e_coverage.py` | Compare C++ registration; fail missing actions/sections without starting UE |
| `pytest Tests -m "not l4_runtime"` | Manually skip PIE, already automatic in headless mode |
| `pytest Tests -m "not lua"` | Skip UnLua |
| `pytest Tests --headless` | Explicit command-line mode, skipping `l4_runtime` / `lua` / `requires_gui` |
| `pytest Tests -k blueprint` | Keyword filter |
| `pytest Tests --keep-artifacts` | Retain `/Game/_McpTest/<ts>/` and legacy `/Game/_NexusTest` |

## Test-file map

| Stage | File |
|-------|------|
| Probes + editor | `test_00_smoke.py`, `test_10_editor.py` |
| Struct / DataTable | `test_20_struct_datatable.py` |
| Blueprint | `test_30_blueprint.py` |
| Widget | `test_40_widget.py` |
| Material | `test_50_material.py` |
| Asset references | `test_60_asset_refs.py` |
| Gameplay Tags | `test_70_gameplay_tags.py` |
| AI / animation assets | `test_80_ai_anim_assets.py` |
| GAS assets | `test_85_gas_assets.py` |
| Asset management | `test_90_asset_mgmt.py` |
| Mesh / Texture | `test_91_asset_mesh_texture.py` |
| Read-only animation / mesh | `test_92_anim_mesh_assets.py` |
| Sound / Niagara | `test_93_sound_niagara.py` |
| Levels | `test_94_level.py` |
| PIE Runtime + Lua | `test_95_pie_runtime.py` |
| GAS Runtime | `test_96_gas_runtime.py` |
| StateTree | `test_97_statetree_manage.py` (UE 5.5+) |
| Sequencer / Physics / EQS | `test_98_sequencer_physics_eqs.py` |
| Response compaction | `test_99_response_compact.py` |
| BlendSpace / AnimSequence keyframes | `test_100_blendspace_animkeys.py` |
| MetaSound / PCG / PoseSearch | `test_101_metasound_pcg_posesearch.py` |
| Curve / UserDefinedEnum | `test_102_curve_enum.py` |
| AnimComposite / PhysicalMaterial / RenderTarget | `test_103_anim_phys_rt.py` |
| SoundClass / Submix | `test_104_audio_system.py` |
| MetaSoundPatch | `test_105_metasound_patch.py` |
| DataLayer | `test_106_data_layer.py` |
| ControlRig | `test_107_control_rig.py` |
| StringTable / Font | `test_108_string_table_font.py` |
| FoliageType | `test_109_foliage.py` |
| Paper2D | `test_110_paper2d.py` |
| GeometryCollection | `test_111_geometry_collection.py` |
| FileMediaSource | `test_112_media.py` |
| CommonUI Style | `test_113_common_ui.py` |
| MoviePipeline | `test_114_movie_pipeline.py` |
| Enhanced Input | `test_115_enhanced_input.py` |
| Material subtypes | `test_116_material_subtypes.py` |
| IKRig / IKRetargeter | `test_117_ik.py` |
| MVVM | `test_118_mvvm.py` (UE 5.5+): contexts/nested paths, five directions, single-input conversion, compile/save/readback, no added bindings for invalid configuration |
| PCG Graph | `test_119_pcg.py` (UE 5.4+) |

## Trace L1 (UE 4.26+)

Filter prefix: `NexusLink.Trace.`. Readback prefers closed recordings supplied through `-NexusTraceTestPath` to avoid older-engine writer-thread errors during in-process stop. UE5 can still make a short recording when none is supplied. First run `NexusLink.Trace.RecordProbe` in an independent Editor-Cmd process with `-trace=cpu,frame,bookmark -tracefile=<absolute-path>` and `-TestExit="Automation Test Queue Empty"`, so completion exits and closes the file. In a second process, run `NexusLink.Trace.` with `-NexusTraceTestPath=<absolute-path>`. Both support `-unattended -nullrhi -nosplash -nosound`.

Cross-version runs use isolated hosts: copies below UE 5.6 omit the `NexusGameplay` template module that their Target does not build, and pass `-ini:EditorPerProjectUserSettings:[/Script/UnrealEd.EditorLoadingSavingSettings]:LoadLevelAtStartup=None` to avoid loading newer default maps. The original project is unchanged.

UE4 Store cases start a Store with automatically assigned ports in an independent temporary directory, without relying on existing user Insights sessions. They verify pathless listings, TraceId stream readback, and session reuse. Snapshot-stream tests cover read limits and premature termination. Test Store ports pass only through internal C++ entry points; no MCP parameters are added.

### Editor long-operation regressions

`test_15_editor_operations.py` covers invalid operation IDs, read-only Slate/capture (GUI), local Automation discovery, and execution by full name. Query all state through `GetEditorOperation`, never the proxy cache.

The 11 cases in `test_28_editor_graph.py` cover dedicated `GetEditorGraph` / `ControlEditorGraph`: headless discovery, node layout and paginated/exact queries, plus native GUI opening, view navigation, selection add/remove/clear, no partial selection for invalid-node batches, and deferred focus/zoom. GUI cases cover standard/widget/animation Blueprints, material/material-function preview graphs, behavior trees, and available PCG graphs, verifying unchanged node layout/source dirty state without Slate input. UE 5.8+ PCG multi-document cases first run host `NexusLink.EditorGraph.PCGMultiDocumentFixture` to create two embedded graphs through public PCG APIs and prebuild unopened graph data. MCP discovers asset/graph paths, verifies that read-only queries do not open graphs, opens each graph, and checks selection/view isolation and unchanged layouts across main/two subgraphs. Run `py Script/run_e2e.py --gui -k editor_graph`; PCG-only runs use `-k 'editor_graph_discovery or editor_graph_pcg_multi_document_views'`, retaining discovery to initialize engine-version gates.

The nine headless cases in `test_28_blueprint_graph_edit.py` verify struct-pin splitting/recombination, parent/child pins and default readback, node coordinates/sizes/comments, and safe-copy internal links/new GUID maps/offsets. They cover large coordinates/tiny decimals in Vector / Rotator / Vector2D / LinearColor and precision after changing child values, merging, and resplitting. Copying one endpoint excludes external connections. Reject linked/scalar pins, invalid child defaults, input structs unable to preserve defaults, nodes from other graphs, boundary nodes, invalid selections, and out-of-range/overflow offsets; failures leave the source graph unchanged. Run `py Script/run_e2e.py -k blueprint_graph_edit`.

C++ `NexusLink.EditorOperations` covers ownership, final compact-output Schema, batch preflight, and GUI Chinese input, clicks, keys, disabled/hidden/stale Ref. `NexusLink.EditorOperations.SlatePointer` checks actual right/middle clicks, double clicks, wheel/modifiers, normalized coordinates, and same-widget drag events; covers held-button movement after left/right/middle capture, capture release, and engine `DetectDrag`; verifies parent Ref/local size and pre-input rejection of invalid arguments. MCP cases in `test_27_editor_pointer.py` run through `py Script/run_e2e.py --gui -k editor_pointer`; GUI is required, and modal windows are not a supported scenario. GUI probes follow dedicated write-capability enablement; `NexusLink.DangerousCap.Tags` verifies only arbitrary-code execution entry points carry dangerous tags. With `-NexusEditorOperationFailureProbe` in an isolated project, `NexusLink.EditorOperations.Probe.Outcome` deliberately fails to verify per-item adapter failure results; ordinary runs omit it. `Probe.Latent` checks progress, bounded waits, and stop boundaries.

Auto-launch readiness binds the port through the current editor PID's instance-registration file. Concurrent editors cannot cause connection to a different project just because its port listens first.

## Independent domains and image regressions

`test_16_project_discovery.py` covers settings registration trees, explicit property reads, plugin dependencies, and mount ownership. `test_17_native_toolsets.py` retains its historical filename but tests independent capabilities: listing/details for temporary project `Skills/<unique>/SKILL.md`, exact-path restrictions/finally cleanup, real typed semantic search, PCG instance creation→execution→node sampling, and Niagara diagnostics. Shared helpers strictly check `Backend=Independent` and gate only on actual domain plugins; unready semantic indexes/providers produce explicit skip reasons.

UE 5.8 cases in `test_40_widget.py` verify movement/reordering, wrapping/single-child restoration/template replacement, cycle rejection, and inherited named-slot compilation/filling/occupied-slot rejection/removal. `NexusLink.EditorOperations.SlateInput` uses temporary windows for replacement, visible waits, form preflight, checkboxes/combo boxes, same-name misclick protection, dragging, and stale Ref; run with GUI.

`test_18_mcp_images.py` verifies real PNG/JPEG bytes, path-only mode, asynchronous captures, and two inline images in a `CallCapability/Calls` batch. `NexusLink.Protocol.ImageContent` covers trusted attachments, count/byte limits, deduplication, and retained text metadata; `NexusLink.Protocol.CaptureRetention` checks timestamp-based retention across mixed capture types while preserving unrelated files. GUI captures use valid Ref returned by Windows queries; assertions merge generic compact-output `_defaults` before inspecting fields.

`test_19_native_followups.py` covers PCG parameter/subgraph/instance-override readback, PhysicsAsset creation/fine editing, Tag INI lifecycle, and real DataRegistry rows/cache misses. Tag-write regressions require separate Config copies to prevent engine rename Redirects from writing user configuration. DataRegistry uses temporary in-memory fixtures and unregisters only its own objects.

`test_21_editor_followups.py` covers UMG renaming/variables/delegates/UIComponent, material/function graph organization, typed settings, content-plugin lifecycle, Sequence folders/conditions/FBX, and native AnimMixer. Persistent project-settings/plugin cases run only in isolated writable hosts explicitly configured with `NEXUS_PERSISTENT_EDIT_FIXTURE=1`; Outliner/custom-binding conversion requires `--gui` and UE 5.8.

`test_25_feedback_nov09.py` covers inherited variable defaults, ClassReference preview/verification, legacy animation/ABP Retarget, and navigation-volume geometry/asynchronous build/save. Map writes use test maps; switching skips if the original map has unsaved changes. L1 `NexusLink.EditorRelated.Feedback*` and `NexusLink.Utils.PinType.ParsePrimitives` cover corresponding engine behavior.

`NexusLink.FeedbackNov10` verifies Actor ownership and preview/write/delete in actual streamed ULevel, component world-transform refresh, early rejection of mixed validation batches, native navigation-volume geometry/resizing, nonfatal reads of null default BrushBuilder, immediate discovery-state updates, and unchanged original files after read-only/Windows external-lock save failures. `NexusLink.EditorOperations.SlateInput` uses SSearchBox for replacement-input coverage.

`NexusLink.FeedbackNov12` verifies UE4/UE5 skeletal sampling, native BlendSpace1D interpolation, nested state-graph read/write, hidden-level navigation data chunks/native map saves, nonfatal rejection without a valid map object, and mixed native-component scalar-validation/array-restoration batches. `test_26_feedback_nov12.py` verifies 1D save/unload/reload and variable writes across seven Blueprints in a headless isolated host. CommonUI ActionBindings explicitly requests PIE, uses `requires_gui` and `l4_runtime`, and runs on a GUI host.

`NexusLink.FirstBatch` covers slow-task protocol rejection/recovery, static UMG provenance/binding evidence, CSV interval aggregation, and malformed-column rejection. `test_24_first_batch_diagnostics.py` verifies live timings, CSV snapshots, UMG diagnostics, actual HTTP responses during slow tasks, player key/single-frame/Action injection, owning-session isolation, PIE cleanup, multiplayer-world selection, and actual CommonUI activation events. Game/modal scenarios require `--gui`; CommonUI/progress pumping requires UE 5.9. The test client retries only bounded EditorBusy responses with bExecuted=false; writes are not retried on timeout/disconnection.
