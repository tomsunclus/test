@echo off
:: Clean Tomcat multipart temp files (older than 10 minutes)
:: Schedule this script to run every 5 minutes via Windows Task Scheduler
::
:: Usage:
::   clean_tomcat_temp.bat
::
:: Task Scheduler setup:
::   1. Open Task Scheduler (taskschd.msc)
::   2. Create Basic Task
::   3. Trigger: Repeat every 5 minutes
::   4. Action: Start a program -> this bat file

set TEMP_DIR=E:\projects\tomcat9-ggws\work\Catalina\localhost\gw-xtjc
set LOG_FILE=E:\projects\tomcat9-ggws\logs\temp_cleanup.log

if not exist "%TEMP_DIR%" (
    mkdir "%TEMP_DIR%"
    exit /b 0
)

:: Delete .tmp files older than 10 minutes
forfiles /p "%TEMP_DIR%" /m *.tmp /d 0 /c "cmd /c if @fsize GTR 0 del @path" >nul 2>&1

:: Also use PowerShell to delete files older than 10 minutes (more precise)
powershell -Command "Get-ChildItem '%TEMP_DIR%' -Filter '*.tmp' -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt (Get-Date).AddMinutes(-10) } | ForEach-Object { Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue }"

:: Log cleanup action
echo %date% %time% - Cleanup done, remaining files: >> "%LOG_FILE%"
dir /b "%TEMP_DIR%\*.tmp" 2>nul | find /c /v "" >> "%LOG_FILE%"
