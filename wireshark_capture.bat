@echo off
title ECG HTTP Capture - Wireshark/tshark

echo =========================================
echo   ECG HTTP Request Capture
echo   Method: Wireshark tshark (command line)
echo   Target: Port 8280
echo   Passive capture, NO impact on services
echo =========================================
echo.

set TSHARK=
if exist "C:\Program Files\Wireshark\tshark.exe" (
    set "TSHARK=C:\Program Files\Wireshark\tshark.exe"
) else if exist "C:\Program Files (x86)\Wireshark\tshark.exe" (
    set "TSHARK=C:\Program Files (x86)\Wireshark\tshark.exe"
) else (
    where tshark.exe >nul 2>&1
    if %errorLevel% equ 0 (
        set TSHARK=tshark.exe
    ) else (
        echo [ERROR] Wireshark / tshark not found!
        echo.
        echo Please install Wireshark first:
        echo   https://www.wireshark.org/download.html
        echo   Make sure to check "TShark" during installation.
        echo.
        echo Or use netsh_capture_start.bat instead (no install needed).
        echo.
        pause
        exit /b 1
    )
)

echo [INFO] tshark path: %TSHARK%

set SAVE_DIR=%~dp0captures
if not exist "%SAVE_DIR%" mkdir "%SAVE_DIR%"

for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DATESTR=%%a%%b%%c
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIMESTR=%%a%%b
set FILENAME=ecg_wireshark_%DATESTR%_%TIMESTR%

echo.
echo Select capture mode:
echo   1. Live display - show HTTP requests in real-time
echo   2. Save to file - save as .pcap for later analysis
echo   3. Both - live display + save to file
echo.
set /p MODE="Enter choice (1/2/3): "

echo.
echo =========================================
echo   Capture started. Press Ctrl+C to stop.
echo =========================================
echo.

if "%MODE%"=="1" (
    echo [MODE] Live display
    echo.
    "%TSHARK%" -i any -f "tcp port 8280" -Y "http.request or http.response" -T fields -e frame.time -e ip.src -e ip.dst -e http.request.method -e http.request.uri -e http.response.code -e http.content_type -e data.text
) else if "%MODE%"=="2" (
    echo [MODE] Save to file: %SAVE_DIR%\%FILENAME%.pcap
    echo.
    "%TSHARK%" -i any -f "tcp port 8280" -w "%SAVE_DIR%\%FILENAME%.pcap"
    echo.
    echo [DONE] File saved: %SAVE_DIR%\%FILENAME%.pcap
    echo   Open with Wireshark, filter: http.request.uri contains "ecg/result"
) else (
    echo [MODE] Live display + Save to file
    echo [INFO] File: %SAVE_DIR%\%FILENAME%.pcap
    echo.
    "%TSHARK%" -i any -f "tcp port 8280" -w "%SAVE_DIR%\%FILENAME%.pcap" -P
)

echo.
pause
