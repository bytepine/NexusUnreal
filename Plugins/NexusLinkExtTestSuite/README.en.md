# NexusLinkExtTestSuite

[中文](README.md) | English

The L1 C++ Automation test plugin for NexusLinkExt lives in this sample project and is **not** included in the [NexusLinkExt](https://github.com/bytepine/NexusLinkExt) plugin repository.

It depends on the sibling plugins `Plugins/NexusLink` and `Plugins/NexusLinkExt`. The module name is `NexusLinkExtTests`; its Automation filter prefix is `NexusLinkExt.`.

## Run tests

In the editor: Session Frontend → Automation → `NexusLinkExt`.

```text
UnrealEditor-Cmd Nexus.uproject -unattended -NullRHI -ExecCmds="Automation RunTests NexusLinkExt.;Quit"
```
