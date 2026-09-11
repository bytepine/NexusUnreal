@echo off
:: Copyright byteyang. All Rights Reserved.
:: NexusUnreal 跨版本工程编译 - Windows 入口
:: Usage: build_test.bat [--ue-root <path>] [--versions UE_X.Y ...] [--vs 2019|2022] [--max-workers N]
:: Default: NexusEditor + Nexus Game. --editor-only / --game-only to skip a phase.

setlocal
cd /d "%~dp0"

python Script\build_test.py %*
exit /b %ERRORLEVEL%
