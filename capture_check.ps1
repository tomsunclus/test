<#
.SYNOPSIS
    ECG System - Server Environment Check Tool
    For Windows Server 2008 R2

.DESCRIPTION
    Checks server environment before packet capture:
    - Is port 8280 listening?
    - Is Windows Firewall allowing traffic?
    - What capture tools are available?

.NOTES
    Run as Administrator:
    powershell -ExecutionPolicy Bypass -File capture_check.ps1
#>

$port = 8280
$targetIP = "192.168.100.69"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  ECG System - Server Environment Check" -ForegroundColor Cyan
Write-Host "  Target: ${targetIP}:${port}" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check 1: Port listening
Write-Host "[Check 1] Port $port listening status" -ForegroundColor Yellow
Write-Host "-----------------------------------------"
$listeners = netstat -ano | Select-String ":$port "
if ($listeners) {
    Write-Host "  [OK] Port $port is LISTENING:" -ForegroundColor Green
    $listeners | ForEach-Object { Write-Host "  $_" }

    $pids = $listeners | ForEach-Object {
        if ($_ -match '\s+(\d+)\s*$') { $matches[1] }
    } | Sort-Object -Unique

    foreach ($pid in $pids) {
        if ($pid -and $pid -ne "0") {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "  Process: PID=$pid  Name=$($proc.ProcessName)  Path=$($proc.Path)" -ForegroundColor Green
            }
        }
    }
} else {
    Write-Host "  [WARN] Port $port is NOT listening!" -ForegroundColor Red
    Write-Host "  Please check if gw-xtjc service is running." -ForegroundColor Red
}
Write-Host ""

# Check 2: Firewall
Write-Host "[Check 2] Windows Firewall status" -ForegroundColor Yellow
Write-Host "-----------------------------------------"
$fwStatus = netsh advfirewall show allprofiles state
Write-Host $fwStatus

$fwRules = netsh advfirewall firewall show rule name=all dir=in | Select-String -Pattern "$port" -Context 3,0
if ($fwRules) {
    Write-Host "  [OK] Found firewall rule for port $port :" -ForegroundColor Green
    $fwRules | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "  [WARN] No inbound rule found for port $port" -ForegroundColor Red
    Write-Host "  If firewall is ON, you may need to add a rule:" -ForegroundColor Red
    Write-Host '  netsh advfirewall firewall add rule name="ECG Port 8280" dir=in action=allow protocol=TCP localport=8280' -ForegroundColor Yellow
}
Write-Host ""

# Check 3: Active connections
Write-Host "[Check 3] Active connections on port $port" -ForegroundColor Yellow
Write-Host "-----------------------------------------"
$connections = netstat -an | Select-String ":$port " | Select-String -NotMatch "LISTENING"
if ($connections) {
    Write-Host "  Active connections:" -ForegroundColor Green
    $connections | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "  No active connections at this moment" -ForegroundColor Gray
}
Write-Host ""

# Check 4: IP config
Write-Host "[Check 4] Network adapter IP configuration" -ForegroundColor Yellow
Write-Host "-----------------------------------------"
$ipConfig = ipconfig | Select-String -Pattern "IPv4|Address|Ethernet"
$ipConfig | ForEach-Object { Write-Host "  $_" }
Write-Host ""

# Check 5: Available capture tools
Write-Host "[Check 5] Available capture tools" -ForegroundColor Yellow
Write-Host "-----------------------------------------"

Write-Host "  [OK] netsh trace    - Windows built-in (RECOMMENDED)" -ForegroundColor Green

$wireshark = Get-Command tshark.exe -ErrorAction SilentlyContinue
if ($wireshark) {
    Write-Host "  [OK] Wireshark      - Installed: $($wireshark.Source)" -ForegroundColor Green
} else {
    $wiresharkPaths = @(
        "C:\Program Files\Wireshark\tshark.exe",
        "C:\Program Files (x86)\Wireshark\tshark.exe"
    )
    $found = $false
    foreach ($p in $wiresharkPaths) {
        if (Test-Path $p) {
            Write-Host "  [OK] Wireshark      - Installed: $p" -ForegroundColor Green
            $found = $true
            break
        }
    }
    if (-not $found) {
        Write-Host "  [--] Wireshark      - Not installed (optional)" -ForegroundColor Gray
        Write-Host "       Download: https://www.wireshark.org/download.html" -ForegroundColor Gray
    }
}

$netmon = Test-Path "C:\Program Files\Microsoft Network Monitor 3\nmcap.exe"
if ($netmon) {
    Write-Host "  [OK] Network Monitor - Installed" -ForegroundColor Green
} else {
    Write-Host "  [--] Network Monitor - Not installed (optional, for viewing .etl files)" -ForegroundColor Gray
    Write-Host "       Download: https://www.microsoft.com/en-us/download/details.aspx?id=4865" -ForegroundColor Gray
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Check Complete" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. If port not listening -> Start gw-xtjc service first" -ForegroundColor White
Write-Host "  2. If firewall blocking -> Add allow rule" -ForegroundColor White
Write-Host "  3. All OK -> Run netsh_capture_start.bat to start capture" -ForegroundColor White
Write-Host ""
