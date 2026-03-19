@echo off
chcp 65001 >nul 2>&1
title 心电系统 HTTP 请求抓包 - Wireshark/tshark

echo =========================================
echo   心电系统 HTTP 请求抓包
echo   方案: Wireshark tshark (命令行)
echo   目标: 端口 8280
echo   完全旁路抓取，不影响原程序运行
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
        echo [错误] 未找到 Wireshark / tshark
        echo.
        echo 请先安装 Wireshark:
        echo   https://www.wireshark.org/download.html
        echo   安装时勾选 "TShark" 组件
        echo.
        echo 或者使用 netsh_capture_start.bat (无需额外安装)
        echo.
        pause
        exit /b 1
    )
)

echo [信息] tshark 路径: %TSHARK%

:: 创建保存目录
set SAVE_DIR=%~dp0captures
if not exist "%SAVE_DIR%" mkdir "%SAVE_DIR%"

for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DATESTR=%%a%%b%%c
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIMESTR=%%a%%b
set FILENAME=ecg_wireshark_%DATESTR%_%TIMESTR%

echo.
echo [选择] 请选择抓包模式:
echo   1. 实时显示 HTTP 请求内容 (适合快速查看)
echo   2. 保存为 pcap 文件 (适合事后详细分析)
echo   3. 两者都要 (实时显示 + 保存文件)
echo.
set /p MODE="请输入选择 (1/2/3): "

echo.
echo =========================================
echo   抓包已启动，按 Ctrl+C 停止
echo =========================================
echo.

if "%MODE%"=="1" (
    echo [模式] 实时显示 HTTP 请求内容
    echo.
    "%TSHARK%" -i any -f "tcp port 8280" -Y "http.request or http.response" -T fields -e frame.time -e ip.src -e ip.dst -e http.request.method -e http.request.uri -e http.response.code -e http.content_type -e data.text
) else if "%MODE%"=="2" (
    echo [模式] 保存到文件: %SAVE_DIR%\%FILENAME%.pcap
    echo.
    "%TSHARK%" -i any -f "tcp port 8280" -w "%SAVE_DIR%\%FILENAME%.pcap"
    echo.
    echo [完成] 文件已保存: %SAVE_DIR%\%FILENAME%.pcap
    echo   用 Wireshark 打开此文件，过滤器输入: http.request.uri contains "ecg/result"
) else (
    echo [模式] 实时显示 + 保存文件
    echo [信息] 文件: %SAVE_DIR%\%FILENAME%.pcap
    echo.
    "%TSHARK%" -i any -f "tcp port 8280" -w "%SAVE_DIR%\%FILENAME%.pcap" -P
)

echo.
pause
