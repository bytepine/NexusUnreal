# NexusLinkTestSuite

NexusLink 的 L1 C++ Automation 测试插件，放在本示例工程侧，**不**进入 [NexusLink](https://github.com/bytepine/NexusLink) 插件仓。

依赖同级插件 `Plugins/NexusLink`。模块名仍为 `NexusLinkTests`（Automation 过滤前缀 `NexusLink.`）。

## 跑测

编辑器：Session Frontend → Automation → `NexusLink`

命令行示例：

```text
UnrealEditor-Cmd Nexus.uproject -unattended -NullRHI -ExecCmds="Automation RunTests NexusLink.;Quit"
```
