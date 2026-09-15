#!/usr/bin/env bash
# Copyright byteyang. All Rights Reserved.
# NexusUnreal 任意平台打包 — macOS / Linux 入口
# 用法: ./package.sh [--platform Mac Linux] [--config Development] [--dry-run]

set -euo pipefail

cd "$(dirname "$0")"

exec python3 Script/package.py "$@"
