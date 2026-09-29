# NexusLinkExtTestSuite

NexusLinkExt 的 L1 C++ Automation 测试插件，放在本示例工程侧，**不**进入 [NexusLinkExt](https://github.com/bytepine/NexusLinkExt) 插件仓。

依赖同级插件 `Plugins/NexusLink` 与 `Plugins/NexusLinkExt`。模块名 `NexusLinkExtTests`（Automation 过滤前缀 `NexusLinkExt.`）。

## 跑测

编辑器：Session Frontend → Automation → `NexusLinkExt`

```text
UnrealEditor-Cmd Nexus.uproject -unattended -NullRHI -ExecCmds="Automation RunTests NexusLinkExt.;Quit"
```
