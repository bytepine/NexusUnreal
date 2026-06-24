#!/usr/bin/env bash
# Copyright byteyang. All Rights Reserved.
# NexusLink Game-target build test (WITH_EDITOR=0)
# 用法: ./build_test_game.sh [--ue-root <路径>] [--versions UE_X.Y ...] [--vs 2019|2022] [--max-workers N]

set -euo pipefail
cd "$(dirname "$0")"
exec python3 Script/build_test_game.py "$@"
