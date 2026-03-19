#!/bin/bash
#
# 为现有 Orthanc 安装 OHIF 插件的自动化脚本
# 适用于 CentOS / RHEL 系统
#
# 用法: sudo bash install-ohif-plugin.sh

set -e

PLUGIN_DIR="/usr/share/orthanc/plugins"
DOWNLOAD_URL="https://orthanc.uclouvain.be/downloads/linux-standard-base/orthanc-ohif"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Orthanc OHIF 插件安装脚本${NC}"
echo -e "${GREEN}========================================${NC}"

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}请使用 root 用户运行此脚本: sudo bash $0${NC}"
  exit 1
fi

echo ""
echo -e "${YELLOW}[1/5] 检查 Orthanc 是否已安装...${NC}"
if command -v Orthanc &> /dev/null || [ -f /usr/sbin/Orthanc ] || [ -f /usr/local/sbin/Orthanc ]; then
  echo -e "${GREEN}  ✓ Orthanc 已安装${NC}"
else
  echo -e "${RED}  ✗ 未检测到 Orthanc，请先安装 Orthanc${NC}"
  exit 1
fi

echo ""
echo -e "${YELLOW}[2/5] 创建插件目录...${NC}"
mkdir -p "$PLUGIN_DIR"
echo -e "${GREEN}  ✓ 插件目录: $PLUGIN_DIR${NC}"

echo ""
echo -e "${YELLOW}[3/5] 下载 OHIF 插件...${NC}"

echo "  正在从 $DOWNLOAD_URL 获取版本列表..."
LATEST_VERSION=$(curl -s "$DOWNLOAD_URL/" | grep -oP 'href="\K[0-9]+\.[0-9]+' | sort -V | tail -1)

if [ -z "$LATEST_VERSION" ]; then
  echo -e "${YELLOW}  ⚠ 无法自动检测最新版本，使用默认版本 2.4${NC}"
  LATEST_VERSION="2.4"
fi

echo "  最新版本: $LATEST_VERSION"

DOWNLOAD_FILE="$DOWNLOAD_URL/$LATEST_VERSION/libOrthancOHIF.so"
echo "  下载地址: $DOWNLOAD_FILE"

cd /tmp
if curl -fSL -o libOrthancOHIF.so "$DOWNLOAD_FILE"; then
  echo -e "${GREEN}  ✓ 下载成功${NC}"
else
  echo -e "${RED}  ✗ 下载失败，请手动从以下地址下载:${NC}"
  echo "    $DOWNLOAD_URL"
  exit 1
fi

cp /tmp/libOrthancOHIF.so "$PLUGIN_DIR/"
chmod 644 "$PLUGIN_DIR/libOrthancOHIF.so"
echo -e "${GREEN}  ✓ 插件已安装到 $PLUGIN_DIR/libOrthancOHIF.so${NC}"

echo ""
echo -e "${YELLOW}[4/5] 检查依赖...${NC}"
MISSING_DEPS=$(ldd "$PLUGIN_DIR/libOrthancOHIF.so" 2>/dev/null | grep "not found" || true)
if [ -n "$MISSING_DEPS" ]; then
  echo -e "${RED}  ⚠ 缺少以下依赖库:${NC}"
  echo "$MISSING_DEPS"
  echo ""
  echo "  尝试安装 LSB 依赖..."
  yum install -y redhat-lsb-core glibc libstdc++ 2>/dev/null || true
else
  echo -e "${GREEN}  ✓ 所有依赖已满足${NC}"
fi

echo ""
echo -e "${YELLOW}[5/5] 检查配置文件...${NC}"

ORTHANC_CONF=$(find /etc -name "orthanc.json" 2>/dev/null | head -1)

if [ -n "$ORTHANC_CONF" ]; then
  echo "  找到配置文件: $ORTHANC_CONF"

  if grep -q '"OHIF"' "$ORTHANC_CONF"; then
    echo -e "${GREEN}  ✓ OHIF 配置已存在${NC}"
  else
    echo -e "${YELLOW}  ⚠ 配置文件中没有 OHIF 配置段${NC}"
    echo ""
    echo "  请在 $ORTHANC_CONF 中添加以下内容:"
    echo ""
    echo '  "Plugins": ['
    echo "    \"$PLUGIN_DIR\""
    echo '  ],'
    echo ''
    echo '  "OHIF": {'
    echo '    "DataSource": "dicom-json",'
    echo '    "RouterBasename": "/ohif/"'
    echo '  }'
  fi

  if grep -q "$PLUGIN_DIR" "$ORTHANC_CONF"; then
    echo -e "${GREEN}  ✓ 插件目录已在配置中${NC}"
  else
    echo -e "${YELLOW}  ⚠ 请确保 Plugins 配置包含: \"$PLUGIN_DIR\"${NC}"
  fi
else
  echo -e "${YELLOW}  ⚠ 未找到 orthanc.json 配置文件${NC}"
  echo "  请参考 native/orthanc.json 模板创建配置文件"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  安装完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "  后续步骤:"
echo "  1. 确认 orthanc.json 配置文件包含 OHIF 和 Plugins 配置"
echo "  2. 重启 Orthanc: systemctl restart orthanc"
echo "  3. 浏览器访问: http://你的IP:8042/ohif/"
echo ""
