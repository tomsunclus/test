@echo off
title ECG HTTP Capture - netsh trace

echo =========================================
echo   ECG HTTP Request Capture Tool
echo   Method: netsh trace (Windows built-in)
echo =========================================
echo.
echo !! WARNING !!
echo    netsh trace has known issues on Windows 2008 R2.
echo    If it does not work, use Wireshark or RawCap instead.
echo    See README for details.
echo.

echo [PREP] Stopping any previous capture session...
netsh trace stop >nul 2>&1
echo [PREP] Done.
echo.

set SAVE_DIR=%~dp0captures
if not exist "%SAVE_DIR%" mkdir "%SAVE_DIR%"

for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DATESTR=%%a%%b%%c
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIMESTR=%%a%%b
set FILENAME=ecg_capture_%DATESTR%_%TIMESTR%

echo [INFO] Capture file: %SAVE_DIR%\%FILENAME%.etl
echo.

echo [START] Starting capture...
netsh trace start capture=yes tracefile="%SAVE_DIR%\%FILENAME%.etl" maxsize=512 overwrite=yes

if %errorLevel% neq 0 (
    echo.
    echo [ERROR] Failed! Please use Wireshark or RawCap instead.
    echo.
    pause
    exit /b 1
)

echo.
echo =========================================
echo   Capture is RUNNING!
echo   Press any key to STOP when done.
echo =========================================
pause

echo.
echo [STOP] Stopping capture...
netsh trace stop

echo.
echo [DONE] File saved: %SAVE_DIR%\%FILENAME%.etl
echo.
pause
