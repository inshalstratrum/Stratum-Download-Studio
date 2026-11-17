@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title I-DS First-Time Setup
echo ===================================================
echo  I-DS - I.os Download Support
echo  One-time source installation (Windows)
echo ===================================================
echo.
set "IDS_PY=python"
where python >nul 2>&1
if errorlevel 1 (
    set "IDS_PY=py"
    where py >nul 2>&1
    if errorlevel 1 goto NO_PYTHON
)
%IDS_PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10+ is required. Python 3.14 is recommended.
    goto ERROR_END
)
echo [1/3] Checking desktop GUI...
%IDS_PY% -c "import PyQt6.QtWidgets" >nul 2>&1
if errorlevel 1 (
    echo Installing PyQt6 for this Windows user...
    %IDS_PY% -m pip install --user "PyQt6>=6.5,<7"
    if errorlevel 1 goto ERROR_END
)
echo [2/3] Checking isolated download dependencies...
%IDS_PY% stratum_dependency_policy.py ".deps" ".tools" >nul 2>&1
if errorlevel 1 (
    echo Installing verified dependencies and Deno - internet required...
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\bootstrap_ytdlp.ps1" -Python "%IDS_PY%"
    if errorlevel 1 goto ERROR_END
)
%IDS_PY% stratum_dependency_policy.py ".deps" ".tools"
if errorlevel 1 goto ERROR_END
echo [3/3] Checking FFmpeg...
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [NOTICE] FFmpeg is missing. Video merging/conversion requires FFmpeg on PATH.
)
where ffprobe >nul 2>&1
if errorlevel 1 (
    echo [NOTICE] FFprobe is missing. Video output verification requires FFprobe on PATH.
)
echo.
echo [READY] Setup finished. Double-click START I-DS.cmd to open the app.
pause
exit /b 0
:NO_PYTHON
echo [ERROR] Python not found. Install Python 3.14 from python.org.
:ERROR_END
echo [ERROR] Setup did not finish; no release or installer was created.
echo See errors above and rerun SETUP I-DS.cmd.
pause
exit /b 1
