@echo off
:: Copyright byteyang. All Rights Reserved.
:: NexusUnreal 任意平台打包 - Windows 入口
:: Usage: package.bat [--platform Win64 Linux] [--config Development] [--dry-run]

setlocal
cd /d "%~dp0"

python Script\package.py %*
exit /b %ERRORLEVEL%
