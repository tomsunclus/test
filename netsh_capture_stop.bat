@echo off
title Stop Capture - netsh trace

echo =========================================
echo   Stop netsh trace capture
echo =========================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Please run as Administrator!
    echo.
    pause
    exit /b 1
)

echo [RUNNING] Stopping capture...
netsh trace stop

echo.
echo [DONE] Capture stopped.
echo        Check .etl files in the "captures" folder.
echo.
pause
