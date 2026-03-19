@echo off
chcp 65001 >nul 2>&1
title 停止抓包 - netsh trace

echo =========================================
echo   停止 netsh trace 抓包
echo =========================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [错误] 请右键选择"以管理员身份运行"此脚本！
    echo.
    pause
    exit /b 1
)

echo [执行] 正在停止抓包...
netsh trace stop

echo.
echo [完成] 抓包已停止，请查看 captures 目录下的 .etl 文件
echo.
pause
