#!/bin/bash
#
# 使用 tcpdump 抓取发往端口 8280 的 HTTP 请求
# 适用于快速确认第三方是否有请求到达服务器
#
# 用法:
#   sudo bash capture_tcpdump.sh              # 实时打印到终端
#   sudo bash capture_tcpdump.sh --save       # 同时保存 pcap 文件
#   sudo bash capture_tcpdump.sh --save --duration 3600  # 抓取1小时

PORT=8280
IFACE="any"
SAVE_MODE=false
DURATION=0
OUTPUT_DIR="./captures"

while [[ $# -gt 0 ]]; do
    case $1 in
        --port)     PORT="$2";     shift 2 ;;
        --iface)    IFACE="$2";    shift 2 ;;
        --save)     SAVE_MODE=true; shift ;;
        --duration) DURATION="$2"; shift 2 ;;
        --help|-h)
            echo "用法: sudo bash capture_tcpdump.sh [选项]"
            echo ""
            echo "选项:"
            echo "  --port PORT       监听端口 (默认: 8280)"
            echo "  --iface IFACE     网卡接口 (默认: any)"
            echo "  --save            保存 pcap 文件到 ./captures/ 目录"
            echo "  --duration SEC    抓取持续时间(秒), 0=不限 (默认: 0)"
            echo "  --help            显示帮助信息"
            exit 0
            ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

echo "========================================="
echo "  HTTP 请求抓取工具 (tcpdump)"
echo "========================================="
echo "监听端口: $PORT"
echo "网卡接口: $IFACE"
echo "保存模式: $SAVE_MODE"
if [ "$DURATION" -gt 0 ]; then
    echo "持续时间: ${DURATION}秒"
fi
echo "按 Ctrl+C 停止抓取"
echo "========================================="
echo ""

TCPDUMP_OPTS="-i $IFACE -nn -A -s 0 'tcp port $PORT'"

if [ "$SAVE_MODE" = true ]; then
    mkdir -p "$OUTPUT_DIR"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    PCAP_FILE="${OUTPUT_DIR}/capture_port${PORT}_${TIMESTAMP}.pcap"
    echo "PCAP 文件保存到: $PCAP_FILE"
    echo ""

    if [ "$DURATION" -gt 0 ]; then
        eval timeout "$DURATION" tcpdump -i "$IFACE" -nn -A -s 0 -w "$PCAP_FILE" "tcp port $PORT"
    else
        eval tcpdump -i "$IFACE" -nn -A -s 0 -w "$PCAP_FILE" "tcp port $PORT"
    fi

    echo ""
    echo "抓包完成，文件已保存到: $PCAP_FILE"
    echo "使用以下命令查看内容:"
    echo "  tcpdump -r $PCAP_FILE -A | less"
    echo "  tcpdump -r $PCAP_FILE -A | grep -A 50 'POST /gw-xtjc/ecg/result'"
else
    if [ "$DURATION" -gt 0 ]; then
        eval timeout "$DURATION" tcpdump -i "$IFACE" -nn -A -s 0 "tcp port $PORT"
    else
        eval tcpdump -i "$IFACE" -nn -A -s 0 "tcp port $PORT"
    fi
fi
