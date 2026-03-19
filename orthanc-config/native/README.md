# 原生安装方式 - 为现有 Orthanc 添加 OHIF 插件

适用于已通过 yum/rpm 或编译方式安装了 Orthanc 的服务器。

## 步骤一：下载 OHIF 插件

```bash
# 创建插件目录（如不存在）
mkdir -p /usr/share/orthanc/plugins

# 下载最新的 OHIF 插件预编译二进制
# 访问 https://orthanc.uclouvain.be/downloads/linux-standard-base/orthanc-ohif/index.html
# 选择最新版本下载

# 示例（请替换为实际最新版本号）：
cd /tmp
wget https://orthanc.uclouvain.be/downloads/linux-standard-base/orthanc-ohif/2.4/libOrthancOHIF.so

# 复制到插件目录
cp /tmp/libOrthancOHIF.so /usr/share/orthanc/plugins/
chmod 644 /usr/share/orthanc/plugins/libOrthancOHIF.so
```

## 步骤二：修改 Orthanc 配置文件

找到你的 Orthanc 配置文件（通常在 `/etc/orthanc/` 或 `/etc/orthanc/orthanc.json`）：

```bash
# 查找配置文件
find / -name "orthanc.json" 2>/dev/null
```

编辑配置文件，确保包含以下内容：

```json
{
  "Plugins": [
    "/usr/share/orthanc/plugins"
  ],

  "DicomWeb": {
    "Enable": true,
    "Root": "/dicom-web/",
    "EnableWado": true,
    "WadoRoot": "/wado",
    "Ssl": false,
    "StudiesMetadata": "Full",
    "SeriesMetadata": "Full"
  },

  "OHIF": {
    "DataSource": "dicom-json",
    "RouterBasename": "/ohif/"
  }
}
```

本目录中提供了完整的配置文件 `orthanc.json` 可以参考。

## 步骤三：安装依赖库（如有缺失）

OHIF 插件 (LSB 版本) 可能依赖一些系统库：

```bash
# CentOS / RHEL
yum install -y glibc libstdc++ openssl-libs

# 如果报 LSB 相关错误
yum install -y redhat-lsb-core
```

## 步骤四：重启 Orthanc

```bash
systemctl restart orthanc

# 或者如果是手动启动的
kill $(pgrep Orthanc)
Orthanc /etc/orthanc/orthanc.json &
```

## 步骤五：验证

```bash
# 检查 OHIF 插件是否加载
curl -u admin:StrongPassword_123456 http://127.0.0.1:8042/system | python3 -m json.tool

# 输出中应包含 "ohif" 在 InstalledPlugins 列表里

# 访问 OHIF
curl -u admin:StrongPassword_123456 http://127.0.0.1:8042/ohif/
```

## 故障排查

### 1. 检查插件是否被识别

```bash
# 查看 Orthanc 日志
journalctl -u orthanc -f

# 或查看日志文件
tail -f /var/log/orthanc/orthanc.log
```

日志中应该看到类似：
```
Registering plugin 'ohif'
```

如果看到：
```
Error loading plugin: /usr/share/orthanc/plugins/libOrthancOHIF.so
```

说明插件文件不兼容或缺少依赖。

### 2. 检查插件依赖

```bash
ldd /usr/share/orthanc/plugins/libOrthancOHIF.so
```

如果有 `not found` 的依赖库，需要安装对应的包。

### 3. 确认 DICOMweb 插件也已加载

OHIF 使用 `dicom-json` 数据源时不需要 DICOMweb，但如果配置为 `dicom-web` 数据源则需要：

```bash
# 检查 DICOMweb 插件
ls /usr/share/orthanc/plugins/libOrthancDicomWeb.so
```
