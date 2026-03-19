@echo off
title ECG HTTP Capture - RawCap

echo =========================================
echo   ECG HTTP Request Capture Tool
echo   Method: RawCap (lightweight, no install)
echo   Passive capture, NO impact on services
echo =========================================
echo.

set SAVE_DIR=%~dp0captures
if not exist "%SAVE_DIR%" mkdir "%SAVE_DIR%"

:: Check if RawCap.exe exists
if not exist "%~dp0RawCap.exe" (
    echo [ERROR] RawCap.exe not found!
    echo.
    echo Please download RawCap.exe first:
    echo   https://www.netresec.com/?page=RawCap
    echo.
    echo   1. Go to the website above
    echo   2. Download RawCap.exe (only 48KB, single file)
    echo   3. Put RawCap.exe in the same folder as this script
    echo   4. Run this script again
    echo.
    pause
    exit /b 1
)

for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DATESTR=%%a%%b%%c
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIMESTR=%%a%%b
set FILENAME=ecg_rawcap_%DATESTR%_%TIMESTR%.pcap

echo [INFO] Capture file: %SAVE_DIR%\%FILENAME%
echo.

echo Available network interfaces:
echo -----------------------------------------
"%~dp0RawCap.exe" --help 2>&1 | findstr /N "."
echo.
echo -----------------------------------------
echo.
echo Typical choices:
echo   Enter the IP of the network adapter (e.g. 192.168.100.69)
echo   Or enter 0.0.0.0 to capture on ALL interfaces
echo.

echo [START] Starting RawCap...
echo         Press Ctrl+C to stop capture.
echo.

"%~dp0RawCap.exe" 192.168.100.69 "%SAVE_DIR%\%FILENAME%"

echo.
echo =========================================
echo   Capture Complete!
echo =========================================
echo   File saved: %SAVE_DIR%\%FILENAME%
echo.
echo   Open this .pcap file with Wireshark:
echo     Filter: tcp.port == 8280
echo     Then find HTTP POST, right-click
echo     -> Follow -> HTTP Stream
echo =========================================
echo.
pause
