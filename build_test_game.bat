@echo off
:: Copyright byteyang. All Rights Reserved.
:: NexusLink Game-target build test (WITH_EDITOR=0) - Windows entry
:: Usage: build_test_game.bat [--ue-root <path>] [--versions UE_X.Y ...] [--vs 2019|2022] [--max-workers N]

setlocal
cd /d "%~dp0"

python Script\build_test_game.py %*
exit /b %ERRORLEVEL%
