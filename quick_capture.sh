#!/bin/bash
#
# 快速抓取方案 - 一行命令即可运行的多种方式
# 在 192.168.100.69 服务器上运行以下任意一种方案
#

echo "========================================="
echo "  HTTP 请求快速抓取方案"
echo "  目标: 端口 8280 /gw-xtjc/ecg/result"
echo "========================================="
echo ""

echo "方案1: tcpdump (最通用，大多数 Linux 自带)"
echo "---------------------------------------------"
echo '  sudo tcpdump -i any -nn -A -s 0 "tcp port 8280" | tee /tmp/ecg_capture_$(date +%Y%m%d).log'
echo ""
echo "  只看 POST 请求:"
echo '  sudo tcpdump -i any -nn -A -s 0 "tcp port 8280 and tcp[((tcp[12:1] & 0xf0) >> 2):4] = 0x504F5354"'
echo ""

echo "方案2: ngrep (更友好的输出，需要安装)"
echo "---------------------------------------------"
echo "  安装: sudo yum install -y ngrep  或  sudo apt install -y ngrep"
echo '  sudo ngrep -q -W byline -d any "POST /gw-xtjc/ecg/result" port 8280'
echo ""

echo "方案3: tshark (Wireshark 命令行版本)"
echo "---------------------------------------------"
echo "  安装: sudo yum install -y wireshark  或  sudo apt install -y tshark"
echo '  sudo tshark -i any -f "tcp port 8280" -Y "http.request" -T fields -e ip.src -e http.request.method -e http.request.uri -e http.request.body'
echo ""

echo "方案4: Python 日志代理 (本仓库提供，无需额外依赖)"
echo "---------------------------------------------"
echo "  仅记录模式 (监听 8281，不转发):"
echo "  python3 http_request_logger.py --port 8281"
echo ""
echo "  代理模式 (监听新端口，记录后转发到原服务):"
echo "  步骤: 先把原服务端口改为 8281，然后:"
echo "  python3 http_request_logger.py --port 8280 --forward http://127.0.0.1:8281"
echo ""

echo "方案5: iptables 日志 (内核级别，最轻量)"
echo "---------------------------------------------"
echo "  开启日志:"
echo '  sudo iptables -I INPUT -p tcp --dport 8280 -j LOG --log-prefix "ECG_REQUEST: " --log-level 4'
echo ""
echo "  查看日志:"
echo "  sudo tail -f /var/log/messages | grep ECG_REQUEST"
echo '  或: sudo journalctl -f | grep ECG_REQUEST'
echo ""
echo "  关闭日志:"
echo '  sudo iptables -D INPUT -p tcp --dport 8280 -j LOG --log-prefix "ECG_REQUEST: " --log-level 4'
echo ""

echo "方案6: ss/netstat 检查端口连接状态"
echo "---------------------------------------------"
echo "  查看 8280 端口是否在监听:"
echo "  ss -tlnp | grep 8280"
echo ""
echo "  查看 8280 端口的当前连接:"
echo "  ss -tnp | grep 8280"
echo ""

echo "========================================="
echo "推荐: 先用方案1(tcpdump)快速确认是否有请求到达"
echo "      如需详细分析请求内容，使用方案4(Python代理)"
echo "========================================="
