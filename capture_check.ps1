<#
.SYNOPSIS
    Windows Server 2008 R2 心电系统接口排查工具

.DESCRIPTION
    在开始抓包前，先用此脚本检查服务器环境：
    - 端口 8280 是否在监听
    - 防火墙是否放行
    - 网络连通性

.NOTES
    以管理员身份运行 PowerShell，然后执行：
    powershell -ExecutionPolicy Bypass -File capture_check.ps1
#>

$port = 8280
$targetIP = "192.168.100.69"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  心电系统接口环境检查" -ForegroundColor Cyan
Write-Host "  目标: ${targetIP}:${port}" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# 检查1: 端口是否在监听
Write-Host "[检查1] 端口 $port 监听状态" -ForegroundColor Yellow
Write-Host "-----------------------------------------"
$listeners = netstat -ano | Select-String ":$port "
if ($listeners) {
    Write-Host "  [OK] 端口 $port 正在监听:" -ForegroundColor Green
    $listeners | ForEach-Object { Write-Host "  $_" }

    $pids = $listeners | ForEach-Object {
        if ($_ -match '\s+(\d+)\s*$') { $matches[1] }
    } | Sort-Object -Unique

    foreach ($pid in $pids) {
        if ($pid -and $pid -ne "0") {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "  进程: PID=$pid  名称=$($proc.ProcessName)  路径=$($proc.Path)" -ForegroundColor Green
            }
        }
    }
} else {
    Write-Host "  [警告] 端口 $port 没有服务在监听！" -ForegroundColor Red
    Write-Host "  请先确认 gw-xtjc 服务是否已启动。" -ForegroundColor Red
}
Write-Host ""

# 检查2: 防火墙状态
Write-Host "[检查2] Windows 防火墙状态" -ForegroundColor Yellow
Write-Host "-----------------------------------------"
$fwStatus = netsh advfirewall show allprofiles state
Write-Host $fwStatus

$fwRules = netsh advfirewall firewall show rule name=all dir=in | Select-String -Pattern "$port" -Context 3,0
if ($fwRules) {
    Write-Host "  [OK] 找到包含端口 $port 的防火墙规则:" -ForegroundColor Green
    $fwRules | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "  [警告] 未找到端口 $port 的入站规则" -ForegroundColor Red
    Write-Host "  如果防火墙开启，可能需要添加规则:" -ForegroundColor Red
    Write-Host "  netsh advfirewall firewall add rule name=`"ECG Port 8280`" dir=in action=allow protocol=TCP localport=8280" -ForegroundColor Yellow
}
Write-Host ""

# 检查3: 当前到 8280 端口的连接
Write-Host "[检查3] 当前到端口 $port 的活跃连接" -ForegroundColor Yellow
Write-Host "-----------------------------------------"
$connections = netstat -an | Select-String ":$port " | Select-String -NotMatch "LISTENING"
if ($connections) {
    Write-Host "  当前活跃连接:" -ForegroundColor Green
    $connections | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "  当前没有活跃连接" -ForegroundColor Gray
}
Write-Host ""

# 检查4: IP 配置
Write-Host "[检查4] 网卡 IP 配置" -ForegroundColor Yellow
Write-Host "-----------------------------------------"
$ipConfig = ipconfig | Select-String -Pattern "IPv4|地址|Address|Ethernet|以太网" -Context 0,1
$ipConfig | ForEach-Object { Write-Host "  $_" }
Write-Host ""

# 检查5: 是否有抓包工具
Write-Host "[检查5] 可用的抓包工具" -ForegroundColor Yellow
Write-Host "-----------------------------------------"

$hasNetsh = $true
Write-Host "  [OK] netsh trace    - Windows 内置 (推荐)" -ForegroundColor Green

$wireshark = Get-Command tshark.exe -ErrorAction SilentlyContinue
if ($wireshark) {
    Write-Host "  [OK] Wireshark      - 已安装: $($wireshark.Source)" -ForegroundColor Green
} else {
    $wiresharkPaths = @(
        "C:\Program Files\Wireshark\tshark.exe",
        "C:\Program Files (x86)\Wireshark\tshark.exe"
    )
    $found = $false
    foreach ($p in $wiresharkPaths) {
        if (Test-Path $p) {
            Write-Host "  [OK] Wireshark      - 已安装: $p" -ForegroundColor Green
            $found = $true
            break
        }
    }
    if (-not $found) {
        Write-Host "  [--] Wireshark      - 未安装 (可选)" -ForegroundColor Gray
    }
}

$netmon = Test-Path "C:\Program Files\Microsoft Network Monitor 3\nmcap.exe"
if ($netmon) {
    Write-Host "  [OK] Network Monitor - 已安装" -ForegroundColor Green
} else {
    Write-Host "  [--] Network Monitor - 未安装 (可选)" -ForegroundColor Gray
}

$rawcap = Test-Path "$PSScriptRoot\RawCap.exe"
if ($rawcap) {
    Write-Host "  [OK] RawCap         - 已存在" -ForegroundColor Green
} else {
    Write-Host "  [--] RawCap         - 未下载 (可选, 单文件无需安装)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  检查完成" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步:" -ForegroundColor Yellow
Write-Host "  1. 如果端口未监听 -> 先启动 gw-xtjc 服务" -ForegroundColor White
Write-Host "  2. 如果防火墙拦截 -> 添加放行规则" -ForegroundColor White
Write-Host "  3. 环境正常 -> 运行 netsh_capture_start.bat 开始抓包" -ForegroundColor White
Write-Host ""
