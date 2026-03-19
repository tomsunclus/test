# 心电系统 HTTP 请求抓包工具（Windows Server 2008 R2）

用于在服务器 `192.168.100.69`（Windows Server 2008 R2）上**旁路抓取**第三方心电系统发送到接口 `http://192.168.100.69:8280/gw-xtjc/ecg/result` 的 HTTP 请求。

**完全不影响原程序的正常运行**，只是在网络层面"旁听"经过的数据包。

## 问题背景

第三方心电系统通过 HTTP POST 向我方服务器回传心电检查结果数据。当前数据无法正常回传，第三方称其系统无问题。需要从服务端抓包来验证：

1. 第三方是否真的发送了请求到我们服务器
2. 请求到达时的完整内容（Headers、Body/JSON 参数）
3. 服务器返回了什么响应

## 工具清单

| 文件 | 说明 |
|------|------|
| `capture_check.ps1` | **环境检查脚本** - 检查端口、防火墙、可用工具（先运行这个） |
| `netsh_capture_start.bat` | **方案一** - netsh trace 抓包（Windows 内置，无需安装任何软件） |
| `netsh_capture_stop.bat` | 停止 netsh trace 抓包 |
| `wireshark_capture.bat` | **方案二** - Wireshark/tshark 抓包（需安装 Wireshark） |
| `analyze_with_tshark.bat` | 分析抓包文件，提取 HTTP 请求详情 |

## 快速开始

### 第零步：环境检查

把所有文件复制到服务器 `192.168.100.69` 上的任意目录，右键 `capture_check.ps1` → "使用 PowerShell 运行"（或以管理员身份运行 PowerShell 后执行）：

```powershell
powershell -ExecutionPolicy Bypass -File capture_check.ps1
```

确认端口 8280 在监听、防火墙已放行。

---

### 方案一：netsh trace（推荐，无需安装任何软件）

Windows Server 2008 R2 **自带**此功能，直接用即可。

**第一步：开始抓包**

右键 `netsh_capture_start.bat` → **以管理员身份运行**

或在管理员命令提示符中手动执行：

```cmd
netsh trace start capture=yes tracefile=C:\ecg_capture.etl protocol=TCP IPv4.Address=192.168.100.69 maxsize=512 overwrite=yes
```

**第二步：等待第三方发送数据**

抓包在后台静默运行，**不影响任何程序**。让第三方发送一次或多次测试数据。

**第三步：停止抓包**

运行 `netsh_capture_stop.bat`，或在管理员命令提示符中：

```cmd
netsh trace stop
```

**第四步：查看抓包文件**

生成的 `.etl` 文件用以下工具打开：

- **Microsoft Network Monitor 3.4**（推荐，免费）
  - 下载：https://www.microsoft.com/en-us/download/details.aspx?id=4865
  - 打开 .etl 文件后，在过滤栏输入：`TCP.Port == 8280`
  - 找到 HTTP POST 请求，展开查看完整的请求体

- **Microsoft Message Analyzer**（功能更强）
  - 下载：https://www.microsoft.com/en-us/download/details.aspx?id=44226

---

### 方案二：Wireshark（功能最强，需要安装）

Wireshark 是最专业的抓包工具，GUI 操作更直观，能直接看到 HTTP 请求体的 JSON 内容。

**安装 Wireshark：**

下载：https://www.wireshark.org/download.html （选择 Windows 64-bit Installer）

安装时勾选所有默认组件（包括 TShark）。

**方式A：图形界面抓包**

1. 打开 Wireshark
2. 选择网卡，开始抓包
3. 在上方过滤栏输入过滤规则：

```
tcp.port == 8280
```

4. 让第三方发送数据
5. 在抓到的数据包中找到 HTTP POST 请求
6. 右键点击 → **Follow** → **HTTP Stream**，即可看到完整的请求和响应内容

**常用 Wireshark 过滤器：**

```
# 只看端口 8280 的流量
tcp.port == 8280

# 只看 HTTP 请求
http.request and tcp.port == 8280

# 只看发到 /ecg/result 的请求
http.request.uri contains "ecg/result"

# 只看 POST 请求
http.request.method == "POST" and tcp.port == 8280

# 查看请求和响应
(http.request or http.response) and tcp.port == 8280
```

**方式B：命令行抓包（tshark）**

运行 `wireshark_capture.bat`，或手动执行：

```cmd
:: 实时显示 HTTP 请求
"C:\Program Files\Wireshark\tshark.exe" -i any -f "tcp port 8280" -Y "http.request" -T fields -e frame.time -e ip.src -e http.request.method -e http.request.uri

:: 保存为 pcap 文件
"C:\Program Files\Wireshark\tshark.exe" -i any -f "tcp port 8280" -w C:\ecg_capture.pcap
```

**方式C：分析已有抓包文件**

运行 `analyze_with_tshark.bat`，会自动提取所有 HTTP 请求的摘要信息。

---

## 方案对比

| 方案 | 是否需安装 | 查看请求体 | 易用性 | 推荐度 |
|------|-----------|-----------|--------|--------|
| **netsh trace** | 不需要（系统内置） | 需配合 Network Monitor 查看 | ★★★★ | ⭐ 首选 |
| **Wireshark GUI** | 需安装 | 可直接查看 JSON 内容 | ★★★★★ | ⭐ 最佳体验 |
| **tshark 命令行** | 需安装 Wireshark | 可导出 HTTP 对象 | ★★★ | 适合批量分析 |

## 排查步骤建议

### 1. 确认端口在监听

```cmd
netstat -ano | findstr "8280"
```

正常应显示 `LISTENING` 状态。如果没有，说明 gw-xtjc 服务未启动。

### 2. 确认防火墙放行

```cmd
netsh advfirewall firewall show rule name=all dir=in | findstr "8280"
```

如果没有规则，添加放行：

```cmd
netsh advfirewall firewall add rule name="ECG Port 8280" dir=in action=allow protocol=TCP localport=8280
```

### 3. 抓包确认请求是否到达

用上述方案一或方案二抓包，让第三方发送测试数据。

### 4. 分析抓包结果

| 抓包结果 | 说明 | 下一步 |
|----------|------|--------|
| **完全没有数据包** | 第三方根本没发送请求，或被网络/防火墙拦截 | 让第三方确认目标地址和网络连通性 |
| **有 SYN 包但连接被拒** | 端口无服务监听，或被防火墙 REJECT | 检查服务和防火墙 |
| **有 HTTP 请求但返回 404** | 请求到了，但路径不对 | 检查 `/gw-xtjc/ecg/result` 路由是否注册正确 |
| **有 HTTP 请求但返回 500** | 请求到了，服务端处理报错 | 查看应用日志，检查业务代码 |
| **有 HTTP 请求且返回 200** | 请求成功处理了 | 检查数据是否入库，可能是业务逻辑问题 |
| **请求体格式不对** | 第三方发的数据格式有误 | 对比抓到的 JSON 和预期格式 |

## 常见问题

**Q: 抓包会影响原程序吗？**

A: 完全不会。无论是 netsh trace 还是 Wireshark，都是在网络驱动层面"旁路镜像"数据包，原始数据包照常传递给应用程序，不做任何拦截或修改。

**Q: etl 文件怎么转成 pcap 给 Wireshark 看？**

A: 安装 Microsoft Message Analyzer，打开 .etl 文件，然后导出为 .cap 格式，Wireshark 即可打开。或者直接用方案二的 Wireshark 抓包，生成的就是 pcap 格式。

**Q: 抓包文件会很大吗？**

A: netsh trace 默认限制 512MB（脚本中已设置 maxsize=512）。如果只抓端口 8280 的流量，数据量通常很小。心电数据单次请求 JSON 约几 KB，即使运行一整天也不会超过几十 MB。

**Q: 能看到完整的 JSON 请求体吗？**

A: 可以。在 Wireshark 中找到 HTTP POST 数据包，右键 → Follow → HTTP Stream，就能看到完整的 JSON 内容，包括 patient、examination、diagnosisResult 等所有字段。
