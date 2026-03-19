@echo off
chcp 65001 >nul 2>&1
title 分析抓包文件 - 提取 HTTP 请求详情

echo =========================================
echo   分析抓包文件 - 提取 HTTP 请求详情
echo =========================================
echo.

:: 寻找 tshark
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
        echo [错误] 未找到 tshark，请先安装 Wireshark
        pause
        exit /b 1
    )
)

if "%~1"=="" (
    echo 用法: analyze_with_tshark.bat [抓包文件路径]
    echo.
    echo 示例:
    echo   analyze_with_tshark.bat captures\ecg_wireshark_20240903.pcap
    echo.

    :: 列出 captures 目录中的文件
    if exist "%~dp0captures" (
        echo 当前 captures 目录下的文件:
        echo -----------------------------------------
        dir /b "%~dp0captures\*.pcap" "%~dp0captures\*.etl" 2>nul
        echo.
    )

    set /p PCAP_FILE="请输入抓包文件路径: "
) else (
    set PCAP_FILE=%~1
)

if not exist "%PCAP_FILE%" (
    echo [错误] 文件不存在: %PCAP_FILE%
    pause
    exit /b 1
)

set SAVE_DIR=%~dp0captures
if not exist "%SAVE_DIR%" mkdir "%SAVE_DIR%"

echo.
echo [分析] 文件: %PCAP_FILE%
echo.

echo =========================================
echo   1. 所有 HTTP 请求概览
echo =========================================
"%TSHARK%" -r "%PCAP_FILE%" -Y "http.request" -T fields -E header=y -E separator="  |  " -e frame.time -e ip.src -e ip.dst -e http.request.method -e http.request.uri -e http.content_length

echo.
echo =========================================
echo   2. 针对 /gw-xtjc/ecg/result 的请求
echo =========================================
"%TSHARK%" -r "%PCAP_FILE%" -Y "http.request.uri contains \"ecg/result\"" -T fields -E header=y -E separator="  |  " -e frame.time -e ip.src -e http.request.method -e http.request.uri -e http.content_type -e http.content_length

echo.
echo =========================================
echo   3. HTTP 请求和响应配对
echo =========================================
"%TSHARK%" -r "%PCAP_FILE%" -Y "http.request or http.response" -T fields -E header=y -E separator="  |  " -e frame.time -e ip.src -e ip.dst -e http.request.method -e http.request.uri -e http.response.code -e http.response.phrase

echo.
echo =========================================
echo   4. 导出完整 HTTP 请求体到文件
echo =========================================
echo 正在导出到 %SAVE_DIR%\http_export\ ...
if not exist "%SAVE_DIR%\http_export" mkdir "%SAVE_DIR%\http_export"
"%TSHARK%" -r "%PCAP_FILE%" --export-objects "http,%SAVE_DIR%\http_export" >nul 2>&1
echo 导出完成，请查看: %SAVE_DIR%\http_export\
dir /b "%SAVE_DIR%\http_export\" 2>nul

echo.
echo =========================================
echo   分析完成
echo =========================================
echo.
echo 提示: 如需查看完整的 HTTP 请求体(JSON)，请用 Wireshark 打开文件，
echo       在过滤栏输入: http.request.uri contains "ecg/result"
echo       然后右键点击数据包 -^> Follow -^> HTTP Stream
echo.
pause
