@echo off
chcp 65001 >nul 2>&1
title 心电系统 HTTP 请求抓包 - netsh trace

echo =========================================
echo   心电系统 HTTP 请求抓包工具
echo   方案: netsh trace (Windows 内置)
echo   目标: 端口 8280
echo   完全旁路抓取，不影响原程序运行
echo =========================================
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [错误] 请右键选择"以管理员身份运行"此脚本！
    echo.
    pause
    exit /b 1
)

:: 创建保存目录
set SAVE_DIR=%~dp0captures
if not exist "%SAVE_DIR%" mkdir "%SAVE_DIR%"

:: 生成带时间戳的文件名
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DATESTR=%%a%%b%%c
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIMESTR=%%a%%b
set FILENAME=ecg_capture_%DATESTR%_%TIMESTR%

echo [信息] 抓包文件将保存到: %SAVE_DIR%\%FILENAME%.etl
echo [信息] 仅抓取端口 8280 的 TCP 流量
echo.

:: 启动 netsh trace 抓包
echo [启动] 正在开始抓包...
netsh trace start capture=yes tracefile="%SAVE_DIR%\%FILENAME%.etl" protocol=TCP IPv4.Address=192.168.100.69 maxsize=512 overwrite=yes

if %errorLevel% neq 0 (
    echo.
    echo [错误] 启动抓包失败！可能的原因:
    echo   1. 已经有一个抓包会话在运行，请先执行 netsh_capture_stop.bat
    echo   2. 权限不足
    echo.
    pause
    exit /b 1
)

echo.
echo =========================================
echo   抓包已启动！
echo =========================================
echo.
echo   现在可以让第三方心电系统发送数据了。
echo   抓包在后台运行，不影响任何程序。
echo.
echo   完成后请运行 netsh_capture_stop.bat 停止抓包。
echo   或者直接在此窗口按任意键停止。
echo.
echo =========================================
pause

:: 用户按键后自动停止
echo.
echo [停止] 正在停止抓包...
netsh trace stop

echo.
echo =========================================
echo   抓包已完成！
echo =========================================
echo   文件保存在: %SAVE_DIR%\%FILENAME%.etl
echo.
echo   查看方式:
echo     1. 用 Microsoft Network Monitor 3.4 打开 .etl 文件
echo        下载: https://www.microsoft.com/en-us/download/details.aspx?id=4865
echo     2. 用 Microsoft Message Analyzer 打开
echo     3. 转换后用 Wireshark 打开 (见 README)
echo =========================================
echo.
pause
