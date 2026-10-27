# NexusLinkTestSuite

NexusLink 的 L1 C++ Automation 测试插件，放在本示例工程侧，**不**进入 [NexusLink](https://github.com/bytepine/NexusLink) 插件仓。

依赖同级插件 `Plugins/NexusLink`。模块名仍为 `NexusLinkTests`（Automation 过滤前缀 `NexusLink.`）。UnLua Capability 的 L1 在 `Plugins/NexusLinkExtTestSuite`（前缀 `NexusLinkExt.`）。

## 跑测

编辑器：Session Frontend → Automation → `NexusLink`

控件定位回归：`NexusLink.Runtime.Widget.ExactInteraction`。在无 PIE 会话的编辑器运行（支持 `-NullRHI`）；临时创建 Game World、视口和同名按钮，验证完整实例路径点击、歧义时零点击、缓存实例排除、嵌套面板和可见层级，结束后清理，不保存测试资产。

命令行示例：

```text
UnrealEditor-Cmd Nexus.uproject -unattended -NullRHI -ExecCmds="Automation RunTests NexusLink.;Quit"
```
