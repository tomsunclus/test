@echo off
title Stop Capture - netsh trace

echo =========================================
echo   Stop netsh trace capture
echo =========================================
echo.

echo [RUNNING] Stopping capture...
netsh trace stop

echo.
echo [DONE] Capture stopped.
echo        Check .etl files in the "captures" folder.
echo.
pause
