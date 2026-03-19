# 心电系统 HTTP 请求抓取工具

用于在服务器 `192.168.100.69` 上抓取第三方心电系统发送到接口 `http://192.168.100.69:8280/gw-xtjc/ecg/result` 的 HTTP 请求，以排查数据回传问题。

## 问题背景

第三方心电系统通过 HTTP POST 向我方服务器回传心电检查结果数据，接口地址为 `/gw-xtjc/ecg/result`。当前数据无法正常回传，第三方称其系统无问题，需要从服务端抓取请求来验证：

1. 第三方是否真的发送了请求
2. 请求到达时的完整参数和内容

## 快速开始

### 最快方案：tcpdump（推荐先用这个确认请求是否到达）

```bash
# SSH 登录到 192.168.100.69 后执行：
sudo tcpdump -i any -nn -A -s 0 'tcp port 8280' | tee /tmp/ecg_capture.log
```

然后让第三方发送一次测试数据，观察终端是否有输出。如果有输出，说明请求到达了服务器；如果没有，说明请求根本没有到达。

### 详细方案：Python 请求日志代理

这个方案能清晰记录每个请求的完整信息（来源IP、Headers、Body），并格式化输出。

**方式A - 仅记录模式**（不影响现有服务，监听另一个端口）：

```bash
python3 http_request_logger.py --port 8281
# 然后让第三方临时把接口地址改为 http://192.168.100.69:8281/gw-xtjc/ecg/result
```

**方式B - 透明代理模式**（不需要第三方改地址）：

```bash
# 1. 先把原有的 gw-xtjc 服务端口从 8280 改到 8281
# 2. 启动代理，监听原端口，记录后转发到新端口
python3 http_request_logger.py --port 8280 --forward http://127.0.0.1:8281
```

日志文件默认保存在 `./logs/http_requests.log`，可用 `--log` 参数指定路径。

## 工具清单

| 文件 | 说明 |
|------|------|
| `quick_capture.sh` | 汇总了 6 种快速抓取方案的命令，直接复制粘贴即可 |
| `capture_tcpdump.sh` | tcpdump 抓包脚本，支持保存 pcap 文件 |
| `http_request_logger.py` | Python HTTP 请求日志记录代理，无第三方依赖 |
| `nginx_capture.conf` | Nginx 反向代理配置参考，通过 Nginx 记录请求 |

## 各方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **tcpdump** | 系统自带，无需安装 | 输出原始，需要人工识别 | 快速确认请求是否到达 |
| **Python 代理** | 输出清晰，完整记录 Body | 需要 Python3 环境 | 详细分析请求内容 |
| **Nginx 代理** | 生产级可靠 | 配置较复杂，需安装 Nginx | 长期监控 |
| **ngrep** | 输出友好，过滤方便 | 需要额外安装 | 快速过滤特定请求 |
| **iptables** | 内核级，最轻量 | 只能看到连接信息，看不到 Body | 仅确认是否有连接 |

## 排查步骤建议

### 第一步：确认端口是否在监听

```bash
ss -tlnp | grep 8280
```

如果没有输出，说明 8280 端口上没有服务在运行，请先启动 `gw-xtjc` 服务。

### 第二步：确认防火墙是否放行

```bash
# CentOS/RHEL
sudo firewall-cmd --list-all | grep 8280
# 或
sudo iptables -L -n | grep 8280

# 临时放行端口
sudo firewall-cmd --add-port=8280/tcp
# 或
sudo iptables -I INPUT -p tcp --dport 8280 -j ACCEPT
```

### 第三步：tcpdump 抓包确认

```bash
sudo tcpdump -i any -nn -A -s 0 'tcp port 8280' 2>&1 | tee /tmp/ecg_capture.log
```

让第三方发送测试请求，观察是否有数据包到达。

### 第四步：如需详细分析

```bash
python3 http_request_logger.py --port 8280 --forward http://127.0.0.1:8281 --log ./logs/ecg.log
```

查看日志文件中记录的完整请求头和请求体。

### 第五步：常见问题排查

| 现象 | 可能原因 |
|------|----------|
| tcpdump 完全没有输出 | 第三方没有发送请求，或网络不通（防火墙/路由） |
| tcpdump 有 SYN 包但无数据 | 端口无服务监听，或服务拒绝连接 |
| 有请求但返回 404 | 路径不匹配，检查 `/gw-xtjc/ecg/result` 是否正确注册 |
| 有请求但返回 500 | 服务端处理异常，检查应用日志 |
| 有请求且返回 200 但数据未入库 | 应用逻辑问题，检查业务代码 |
