@echo off
title Port 8280 Connectivity Test

echo =========================================
echo   Port 8280 Connectivity Test
echo   Run this on server 192.168.100.69
echo =========================================
echo.

echo [Test 1] Check if port 8280 is listening
echo -----------------------------------------
netstat -ano | findstr "8280"
echo.

echo [Test 2] Windows Firewall status
echo -----------------------------------------
netsh advfirewall show allprofiles | findstr "State"
echo.

echo [Test 3] Firewall rules for port 8280
echo -----------------------------------------
netsh advfirewall firewall show rule name=all dir=in | findstr /C:"8280"
if %errorLevel% neq 0 (
    echo   No inbound rule found for port 8280!
    echo.
    echo   To add a firewall rule, run:
    echo   netsh advfirewall firewall add rule name="ECG 8280" dir=in action=allow protocol=TCP localport=8280
)
echo.

echo [Test 4] Try to reach port 8280 locally
echo -----------------------------------------
powershell -Command "try { $c = New-Object System.Net.Sockets.TcpClient('192.168.100.69', 8280); Write-Host '  [OK] Port 8280 is reachable!'; $c.Close() } catch { Write-Host '  [FAIL] Cannot connect to port 8280:' $_.Exception.Message }"
echo.

echo =========================================
echo   Test Complete
echo =========================================
echo.
pause
