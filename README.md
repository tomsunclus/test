# ECG HTTP Request Capture Tool (Windows Server 2008 R2)

Capture third-party ECG system HTTP requests to `http://192.168.100.69:8280/gw-xtjc/ecg/result` for troubleshooting.

Passive capture only - **NO impact on running services**.

---

## Recommended: Wireshark (BEST option)

Wireshark is the most reliable capture tool on Windows 2008 R2. It has a GUI, shows packets in real-time, and can display full HTTP request body (JSON).

### Step 1: Install Wireshark

Download: https://www.wireshark.org/download.html

Choose **Windows x64 Installer** (or x86 for 32-bit). Install with all default options.

> For Windows 2008 R2 use **Wireshark 3.6.x** (last version supporting Windows 7/2008R2):
> https://www.wireshark.org/download/win64/all-versions/

### Step 2: Start Capture

1. Open **Wireshark**
2. Select your network adapter (the one with IP `192.168.100.69`)
3. In the **Capture Filter** box (top), type:

```
port 8280
```

4. Click the blue shark fin button (Start) to begin capture

### Step 3: Wait for Requests

Ask the ECG vendor to send test data, or send a Postman POST from your own PC to:

```
http://192.168.100.69:8280/gw-xtjc/ecg/result
```

Wireshark will show packets in real-time as they arrive.

### Step 4: Analyze

In the **Display Filter** bar (green bar, top), type:

```
http.request.uri contains "ecg/result"
```

This shows only the ECG requests. To see full request content:

1. Click on the HTTP POST packet
2. Right-click -> **Follow** -> **HTTP Stream**
3. A window pops up showing the **complete HTTP request and response**, including the full JSON body

### Key Wireshark Filters

| Filter | What it shows |
|--------|--------------|
| `tcp.port == 8280` | All traffic on port 8280 |
| `http.request` | All HTTP requests |
| `http.request.uri contains "ecg/result"` | Only ECG result requests |
| `http.request.method == "POST"` | Only POST requests |
| `ip.src == x.x.x.x` | Requests from specific IP |

### Step 5: Save Capture

File -> Save As -> choose a location. The `.pcapng` file can be shared and reopened later.

---

## Alternative: RawCap (No install needed)

RawCap is a single `.exe` file (48KB), no installation required. It captures packets to `.pcap` files.

### Step 1: Download RawCap

Go to: https://www.netresec.com/?page=RawCap

Download `RawCap.exe` and put it in the same folder as the scripts.

### Step 2: Run

Double-click `rawcap_capture.bat`, or run manually:

```cmd
RawCap.exe 192.168.100.69 ecg_capture.pcap
```

Press `Ctrl+C` to stop.

### Step 3: View Results

Open the `.pcap` file with Wireshark on any PC (doesn't have to be the server).

---

## Troubleshooting: Check Port First

Before capturing, verify port 8280 is accessible. Run `port_test.bat` on the server, or manually:

```cmd
:: Is port 8280 listening?
netstat -ano | findstr "8280"

:: Is firewall blocking?
netsh advfirewall firewall show rule name=all dir=in | findstr "8280"

:: Add firewall rule if needed
netsh advfirewall firewall add rule name="ECG 8280" dir=in action=allow protocol=TCP localport=8280
```

**If `netstat` shows nothing on port 8280**, the gw-xtjc service is not running.

**If firewall has no rule for 8280**, external requests will be blocked silently.

---

## If Nothing is Captured

| Situation | Meaning | Action |
|-----------|---------|--------|
| Port 8280 not listening | gw-xtjc service not running | Start the service |
| Firewall blocks 8280 | Requests rejected before reaching app | Add firewall allow rule |
| Wireshark shows no packets | Requests never reach this server | Check network routing, ask vendor to verify target IP |
| Wireshark shows SYN but no HTTP | TCP connection fails | Check if service is healthy |
| Wireshark shows HTTP 404 | Wrong URL path | Verify API route registration |
| Wireshark shows HTTP 500 | Server error processing request | Check application logs |
| Wireshark shows HTTP 200 | Request succeeds | Data issue is in business logic, not network |

---

## File List

| File | Description |
|------|-------------|
| `port_test.bat` | Check port 8280 status and firewall rules |
| `rawcap_capture.bat` | Capture with RawCap (needs RawCap.exe) |
| `netsh_capture_start.bat` | Capture with netsh trace (unreliable on 2008 R2) |
| `netsh_capture_stop.bat` | Stop netsh trace |
| `wireshark_capture.bat` | Capture with tshark command line |
| `analyze_with_tshark.bat` | Analyze .pcap file with tshark |
| `capture_check.ps1` | PowerShell environment check |
