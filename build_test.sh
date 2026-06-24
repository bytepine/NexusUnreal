#!/usr/bin/env bash
# Copyright byteyang. All Rights Reserved.
# NexusLink 跨版本编译测试 — macOS / Linux 入口
# 用法: ./build_test.sh [--ue-root <路径>] [--versions UE_X.Y ...] [--vs 2019|2022] [--max-workers N]

set -euo pipefail

cd "$(dirname "$0")"

exec python3 Script/build_test.py "$@"
