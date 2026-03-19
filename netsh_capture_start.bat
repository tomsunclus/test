@echo off
title ECG HTTP Capture - netsh trace

echo =========================================
echo   ECG HTTP Request Capture Tool
echo   Method: netsh trace (Windows built-in)
echo   Target: Port 8280
echo   Passive capture, NO impact on services
echo =========================================
echo.

echo !! IMPORTANT !!
echo    netsh trace CANNOT capture localhost/127.0.0.1 traffic.
echo    You MUST send test requests from ANOTHER machine,
echo    not from this server itself.
echo.

set SAVE_DIR=%~dp0captures
if not exist "%SAVE_DIR%" mkdir "%SAVE_DIR%"

for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DATESTR=%%a%%b%%c
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIMESTR=%%a%%b
set FILENAME=ecg_capture_%DATESTR%_%TIMESTR%

echo [INFO] Capture file: %SAVE_DIR%\%FILENAME%.etl
echo [INFO] Capturing ALL network traffic (no filter)
echo.

echo [START] Starting capture...
netsh trace start capture=yes tracefile="%SAVE_DIR%\%FILENAME%.etl" maxsize=512 overwrite=yes

if %errorLevel% neq 0 (
    echo.
    echo [ERROR] Failed to start capture!
    echo   Possible reasons:
    echo   1. Another capture session is already running.
    echo      Run netsh_capture_stop.bat first.
    echo   2. Not running as Administrator.
    echo      Right-click this file, select "Run as administrator".
    echo.
    pause
    exit /b 1
)

echo.
echo =========================================
echo   Capture is RUNNING!
echo =========================================
echo.
echo   Now send test requests from ANOTHER PC:
echo     - Use Postman on your own PC (not this server)
echo     - POST to http://192.168.100.69:8280/gw-xtjc/ecg/result
echo     - Or ask the ECG vendor to send test data
echo.
echo   Press any key to STOP capture when done.
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
echo        Filter in Network Monitor: TCP.Port == 8280
echo     2. Or use Microsoft Message Analyzer
echo     3. Or install Wireshark and use wireshark_capture.bat
echo =========================================
echo.
pause
