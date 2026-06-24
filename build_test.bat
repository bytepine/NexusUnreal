@echo off
:: Copyright byteyang. All Rights Reserved.
:: NexusLink cross-version build test - Windows entry
:: Usage: build_test.bat [--ue-root <path>] [--versions UE_X.Y ...] [--vs 2019|2022] [--max-workers N]
:: Default: Editor (WITH_EDITOR=1) + Game (WITH_EDITOR=0). --editor-only / --game-only to skip a phase.

setlocal
cd /d "%~dp0"

python Script\build_test.py %*
exit /b %ERRORLEVEL%
