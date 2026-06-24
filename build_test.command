#!/usr/bin/env bash
# Copyright byteyang. All Rights Reserved.
# NexusLink 跨版本编译测试 — macOS 双击入口
# Finder 双击 .command 时工作目录常为 $HOME；脚本内 cd 到仓库侧 nexus-unreal。
# 从终端调用时可带参数：open build_test.command --args --versions UE_5.4

cd "$(dirname "$0")"
exec bash build_test.sh "$@"
