@echo off
title Analyze Capture File - Extract HTTP Details

echo =========================================
echo   Analyze Capture File
echo   Extract HTTP Request Details
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
        echo [ERROR] tshark not found. Please install Wireshark first.
        pause
        exit /b 1
    )
)

if "%~1"=="" (
    echo Usage: analyze_with_tshark.bat [capture_file_path]
    echo.
    echo Example:
    echo   analyze_with_tshark.bat captures\ecg_wireshark_20240903.pcap
    echo.

    if exist "%~dp0captures" (
        echo Files in captures folder:
        echo -----------------------------------------
        dir /b "%~dp0captures\*.pcap" "%~dp0captures\*.etl" 2>nul
        echo.
    )

    set /p PCAP_FILE="Enter capture file path: "
) else (
    set PCAP_FILE=%~1
)

if not exist "%PCAP_FILE%" (
    echo [ERROR] File not found: %PCAP_FILE%
    pause
    exit /b 1
)

set SAVE_DIR=%~dp0captures
if not exist "%SAVE_DIR%" mkdir "%SAVE_DIR%"

echo.
echo [ANALYZE] File: %PCAP_FILE%
echo.

echo =========================================
echo   1. All HTTP Requests Overview
echo =========================================
"%TSHARK%" -r "%PCAP_FILE%" -Y "http.request" -T fields -E header=y -E separator="  |  " -e frame.time -e ip.src -e ip.dst -e http.request.method -e http.request.uri -e http.content_length

echo.
echo =========================================
echo   2. Requests to /gw-xtjc/ecg/result
echo =========================================
"%TSHARK%" -r "%PCAP_FILE%" -Y "http.request.uri contains \"ecg/result\"" -T fields -E header=y -E separator="  |  " -e frame.time -e ip.src -e http.request.method -e http.request.uri -e http.content_type -e http.content_length

echo.
echo =========================================
echo   3. HTTP Request-Response Pairs
echo =========================================
"%TSHARK%" -r "%PCAP_FILE%" -Y "http.request or http.response" -T fields -E header=y -E separator="  |  " -e frame.time -e ip.src -e ip.dst -e http.request.method -e http.request.uri -e http.response.code -e http.response.phrase

echo.
echo =========================================
echo   4. Export HTTP Objects to Files
echo =========================================
echo Exporting to %SAVE_DIR%\http_export\ ...
if not exist "%SAVE_DIR%\http_export" mkdir "%SAVE_DIR%\http_export"
"%TSHARK%" -r "%PCAP_FILE%" --export-objects "http,%SAVE_DIR%\http_export" >nul 2>&1
echo Export done. Check: %SAVE_DIR%\http_export\
dir /b "%SAVE_DIR%\http_export\" 2>nul

echo.
echo =========================================
echo   Analysis Complete
echo =========================================
echo.
echo Tip: To view full HTTP body (JSON), open the file in Wireshark,
echo      filter: http.request.uri contains "ecg/result"
echo      then right-click packet -^> Follow -^> HTTP Stream
echo.
pause
