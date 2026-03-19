# Docker 方式部署 Orthanc + OHIF

## 前提条件

- 已安装 Docker 和 Docker Compose
- 服务器 8042 和 4242 端口未被占用

## 如果当前已有 Orthanc 在运行

**先停止已有的 Orthanc 服务**，避免端口冲突：

```bash
# 如果 Orthanc 是通过 systemd 运行的
systemctl stop orthanc
systemctl disable orthanc

# 如果是通过 yum 安装的，停止服务即可，不需要卸载
```

## 迁移已有数据（可选）

如果你的 Orthanc 已经有 DICOM 数据，可以迁移：

```bash
# 查看当前 Orthanc 的存储目录（通常在 /var/lib/orthanc/db 或配置文件中指定的路径）
# 将数据目录挂载到 Docker 容器中

# 修改 docker-compose.yml 中的 volumes，将：
#   - orthanc-storage:/var/lib/orthanc/db
# 改为：
#   - /你的现有数据目录:/var/lib/orthanc/db
```

## 部署步骤

### 1. 修改密码

编辑 `orthanc.json` 和 `docker-compose.yml`，将 `StrongPassword_123456` 改为你的实际密码。

### 2. 启动服务

```bash
cd orthanc-config/docker
docker-compose up -d
```

### 3. 查看日志

```bash
docker logs -f orthanc-ohif
```

确认日志中出现以下内容说明 OHIF 插件加载成功：

```
W0101 00:00:00.000000 PluginsManager.cpp:169] Registering plugin 'ohif' (version ...)
```

### 4. 验证访问

```bash
# 测试 Orthanc API
curl -u admin:你的密码 http://127.0.0.1:8042/system

# 测试 DICOMweb
curl -u admin:你的密码 http://127.0.0.1:8042/dicom-web/studies

# 测试 OHIF（浏览器访问）
# http://你的IP:8042/ohif/
```

## 阿里云安全组配置

确保阿里云安全组放行以下端口：

| 端口 | 协议 | 说明 |
|------|------|------|
| 8042 | TCP | Orthanc HTTP API + OHIF Viewer |
| 4242 | TCP | DICOM 传输（如需外部设备推送影像） |

## 常见问题

### OHIF 页面空白或加载失败

检查浏览器控制台是否有 CORS 错误，如有，在 `orthanc.json` 中添加：

```json
{
  "HttpCorsAllowed": true
}
```

### 需要关闭认证（仅测试环境）

```json
{
  "AuthenticationEnabled": false,
  "RemoteAccessAllowed": true
}
```
