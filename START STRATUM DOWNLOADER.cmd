@echo off
setlocal
set "APP_ROOT=%~dp0"
cd /d "%APP_ROOT%"

where pythonw >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    start "" pythonw "%APP_ROOT%StratumDownloadStudio.pyw"
    exit /b 0
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    start "" python "%APP_ROOT%StratumDownloadStudio.pyw"
    exit /b 0
)

if exist "C:\Python314\pythonw.exe" (
    start "" "C:\Python314\pythonw.exe" "%APP_ROOT%StratumDownloadStudio.pyw"
    exit /b 0
)

echo [ERROR] Python not found on PATH. Please ensure Python is installed.
pause
