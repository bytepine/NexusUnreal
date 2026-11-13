# NexusLinkTestSuite

[中文](README.md) | English

The L1 C++ Automation test plugin for NexusLink lives in this sample project and is **not** included in the [NexusLink](https://github.com/bytepine/NexusLink) plugin repository.

It depends on the sibling `Plugins/NexusLink` plugin. The module name remains `NexusLinkTests`; its Automation filter prefix is `NexusLink.`. L1 tests for UnLua capabilities live in `Plugins/NexusLinkExtTestSuite` (prefix `NexusLinkExt.`).

## Run tests

In the editor: Session Frontend → Automation → `NexusLink`.

Widget targeting regression: `NexusLink.Runtime.Widget.ExactInteraction`. Run it in an editor without an active PIE session (`-NullRHI` is supported). It creates a temporary Game World, viewport, and identically named buttons to verify clicks by full instance path, zero clicks on ambiguity, exclusion of cached instances, nested panels, and visible hierarchy. It cleans up afterward without saving test assets.

Command-line example:

```text
UnrealEditor-Cmd Nexus.uproject -unattended -NullRHI -ExecCmds="Automation RunTests NexusLink.;Quit"
```
