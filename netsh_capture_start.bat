@echo off
title ECG HTTP Capture - netsh trace

echo =========================================
echo   ECG HTTP Request Capture Tool
echo   Method: netsh trace (Windows built-in)
echo   Target: Port 8280
echo   Passive capture, NO impact on services
echo =========================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Please run as Administrator!
    echo         Right-click this file, select "Run as administrator"
    echo.
    pause
    exit /b 1
)

set SAVE_DIR=%~dp0captures
if not exist "%SAVE_DIR%" mkdir "%SAVE_DIR%"

for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DATESTR=%%a%%b%%c
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIMESTR=%%a%%b
set FILENAME=ecg_capture_%DATESTR%_%TIMESTR%

echo [INFO] Capture file: %SAVE_DIR%\%FILENAME%.etl
echo [INFO] Capturing TCP traffic on port 8280
echo.

echo [START] Starting capture...
netsh trace start capture=yes tracefile="%SAVE_DIR%\%FILENAME%.etl" protocol=TCP IPv4.Address=192.168.100.69 maxsize=512 overwrite=yes

if %errorLevel% neq 0 (
    echo.
    echo [ERROR] Failed to start capture!
    echo   Possible reasons:
    echo   1. Another capture session is already running.
    echo      Run netsh_capture_stop.bat first.
    echo   2. Insufficient permissions.
    echo.
    pause
    exit /b 1
)

echo.
echo =========================================
echo   Capture is RUNNING!
echo =========================================
echo.
echo   You can now ask the ECG system to send
echo   test data. The capture runs in background
echo   and does NOT affect any running services.
echo.
echo   When done, press any key here to stop,
echo   or run netsh_capture_stop.bat separately.
echo.
echo =========================================
pause

echo.
echo [STOP] Stopping capture...
netsh trace stop

echo.
echo =========================================
echo   Capture Complete!
echo =========================================
echo   File saved: %SAVE_DIR%\%FILENAME%.etl
echo.
echo   How to view:
echo     1. Open .etl file with Microsoft Network Monitor 3.4
echo        Download: https://www.microsoft.com/en-us/download/details.aspx?id=4865
echo     2. Or use Microsoft Message Analyzer
echo     3. Or install Wireshark and use wireshark_capture.bat
echo =========================================
echo.
pause
