# 阿里云 Orthanc Worklist（申请单）查询指南

## 当前问题总结

| 现状 | 状态 |
|------|------|
| Orthanc 服务器已部署在阿里云 | ✅ |
| Java 后端已生成 `.wl` 文件到 `/opt/orthanc/worklists/` | ✅ |
| MicroDicom C-ECHO 连接已通 | ✅ |
| MicroDicom 查询到申请单（Worklist） | ❌ |

**根本原因有两个：**

1. **MicroDicom 2025.4 不支持 Modality Worklist (MWL) 查询** — 它只是一个 DICOM 影像查看器，Network 菜单中没有 Worklist 查询功能
2. **Orthanc 的 `orthanc.json` 中 Worklist 配置的键名可能有误** — 应使用 `"Database"` 而非 `"Directory"`

---

## 一、修正 Orthanc Worklist 插件配置（服务器端）

### 1.1 你当前的配置（可能有问题）

```json
"Worklists": {
    "Enable": true,
    "Directory": "/var/lib/orthanc/worklists"
}
```

### 1.2 正确的配置

Orthanc 官方 Worklist 插件使用的键名是 `"Database"`，不是 `"Directory"`：

```json
"Worklists": {
    "Enable": true,
    "Database": "/var/lib/orthanc/worklists",
    "FilterIssuerAet": false
}
```

> `FilterIssuerAet` 设为 `false` 表示所有客户端查询都能获取全部 Worklist，不按 AET 过滤。

### 1.3 修改后重启 Orthanc

```bash
# Docker 方式
docker restart orthanc

# 或 Docker Compose 方式
docker compose restart orthanc
```

### 1.4 验证 Worklist 插件是否正常加载

```bash
# 查看已加载的插件列表
curl -u admin:StrongPassword_123456 http://localhost:8042/plugins

# 查看 worklists 插件详情
curl -u admin:StrongPassword_123456 http://localhost:8042/plugins/worklists
```

如果返回中包含 `worklists`，说明插件已正确加载。

### 1.5 确认 .wl 文件路径映射

你的 `.wl` 文件在宿主机的 `/opt/orthanc/worklists/` 目录，`orthanc.json` 中配置的是容器内路径 `/var/lib/orthanc/worklists`。

确保 Docker 的 Volume 映射正确：

```bash
# 检查容器内是否能看到 .wl 文件
docker exec orthanc ls -la /var/lib/orthanc/worklists/
```

如果看不到文件，说明 Volume 映射缺失，需要在 Docker 启动命令中添加：

```bash
-v /opt/orthanc/worklists:/var/lib/orthanc/worklists
```

---

## 二、MicroDicom 不支持 Worklist 查询

从你的截图可以确认，MicroDicom 2025.4 (64-bit) 的 Network 菜单只有以下选项：

- Download from DICOM server... (Shift+F)
- Accept receiving studies
- Send to PACS
- Auto-add to local database
- Network activity

**没有 DICOM Worklist / MWL 查询功能。** MicroDicom 是一款 DICOM 影像查看器，支持 Study 级别的 C-FIND（查影像）和 C-GET/C-MOVE（取影像），但不支持 Modality Worklist (MWL) 查询。

"Download from DICOM server" (Shift+F) 执行的是 Study 级别 C-FIND，只能查到已经存储在 Orthanc 中的影像数据，而 **Worklist 是待检查的申请单信息，不是已存储的影像**。

---

## 三、查询 Worklist 的替代方案

### 方案一：使用 DCMTK 的 findscu 命令行工具（推荐验证）

`findscu` 是 DCMTK 提供的 DICOM C-FIND 客户端，可以直接查询 Orthanc 的 Worklist。

#### 安装 DCMTK

```bash
# Ubuntu / Debian
sudo apt-get install dcmtk

# CentOS / RHEL
sudo yum install dcmtk

# Windows：下载 DCMTK 预编译包
# https://dicom.offis.de/dcmtk.php.en
```

#### 查询 Worklist

```bash
# 查询 Orthanc 上的全部 Worklist
findscu -v -W -k 0008,0050="" -k 0010,0010="" -k 0010,0020="" \
  -k 0020,000D="" -k 0008,0060="" -k 0040,0100="" \
  -aet MICRODICOM -aec ORTHANC \
  39.104.226.62 4242
```

**参数说明：**
- `-W` — 指定使用 Worklist 模式（Modality Worklist Information Model）
- `-k 0008,0050=""` — 查询 Accession Number
- `-k 0010,0010=""` — 查询 Patient Name
- `-k 0010,0020=""` — 查询 Patient ID
- `-k 0020,000D=""` — 查询 Study Instance UID
- `-k 0008,0060=""` — 查询 Modality
- `-k 0040,0100=""` — 查询 Scheduled Procedure Step Sequence
- `-aet MICRODICOM` — 本地 AE Title
- `-aec ORTHANC` — 远程 Orthanc 的 AE Title

#### 查询特定日期的 Worklist

```bash
# 查询今天 (2026-03-20) 的 Worklist
findscu -v -W -k 0008,0050="" -k 0010,0010="" -k 0010,0020="" \
  -k 0040,0100[0].0040,0002="20260320" \
  -aet MICRODICOM -aec ORTHANC \
  39.104.226.62 4242
```

#### 查询特定患者的 Worklist

```bash
# 查询患者 ID 为 "P001" 的 Worklist
findscu -v -W -k 0010,0020="P001" -k 0010,0010="" -k 0008,0050="" \
  -aet MICRODICOM -aec ORTHANC \
  39.104.226.62 4242
```

如果 `findscu` 能查到结果，说明 Orthanc 的 Worklist 配置是正确的，问题仅出在 MicroDicom 不支持 MWL 查询。

### 方案二：使用 Orthanc REST API 查询（最简单）

直接通过 HTTP 请求查询 Worklist 数据：

```bash
# 查询所有 Worklist
curl -u admin:StrongPassword_123456 \
  http://39.104.226.62:8042/dicom-web/studies

# 通过 tools/find 查询
curl -u admin:StrongPassword_123456 \
  -X POST http://39.104.226.62:8042/tools/find \
  -d '{"Level":"Study","Query":{}}'
```

### 方案三：使用支持 MWL 的 DICOM 软件

以下软件支持 Modality Worklist 查询：

| 软件 | 平台 | 费用 | MWL 支持 |
|------|------|------|----------|
| **RadiAnt DICOM Viewer** | Windows | 免费试用 | ✅ 支持 |
| **Horos** | macOS | 免费 | ✅ 支持 |
| **3D Slicer** | 跨平台 | 免费开源 | ✅ 支持 |
| **Conquest DICOM** | Windows/Linux | 免费 | ✅ 支持 |
| **DCMTK findscu** | 跨平台 | 免费开源 | ✅ 支持（命令行） |

### 方案四：Java 后端直接提供 Worklist 查询接口

既然你已经用 Java 后端将申请单写入了 Orthanc，最实用的方案是直接在 Java 后端提供查询接口：

```java
// 通过 Orthanc REST API 查询 Worklist
// 或直接从你的业务数据库查询申请单数据
// 这样前端就可以直接显示申请单列表，无需依赖 DICOM 客户端
```

### 方案五：在 Orthanc 服务器上直接验证

登录阿里云服务器，使用 Docker 容器内的工具验证：

```bash
# 进入 Orthanc 容器
docker exec -it orthanc bash

# 查看 worklist 文件
ls -la /var/lib/orthanc/worklists/

# 如果容器内有 dcmtk，可以直接 dump 查看 .wl 文件内容
dcmdump /var/lib/orthanc/worklists/ACC1773973392199*.wl
```

或者在宿主机上查看：

```bash
# 安装 dcmtk
apt-get install dcmtk

# 查看 .wl 文件内容
dcmdump /opt/orthanc/worklists/ACC1773973392199*.wl

# 本地查询 Worklist
findscu -v -W -k 0008,0050="" -k 0010,0010="" \
  -aet TEST -aec ORTHANC localhost 4242
```

---

## 四、完整排查步骤

按以下顺序逐步排查：

### 步骤 1：修正 orthanc.json 配置

将 `"Directory"` 改为 `"Database"`，添加 `"FilterIssuerAet": false`。

### 步骤 2：确认 Docker Volume 映射

```bash
docker inspect orthanc | grep -A 5 "Mounts"
```

确保 `/opt/orthanc/worklists` 映射到容器内 `/var/lib/orthanc/worklists`。

### 步骤 3：重启 Orthanc 并检查日志

```bash
docker restart orthanc
docker logs orthanc 2>&1 | grep -i worklist
```

应看到类似日志：
```
W0320 ... Worklist plugin is using directory: /var/lib/orthanc/worklists
```

### 步骤 4：验证插件加载

```bash
curl -u admin:StrongPassword_123456 http://39.104.226.62:8042/plugins
```

### 步骤 5：用 findscu 测试 Worklist 查询

```bash
findscu -v -W -k 0008,0050="" -k 0010,0010="" \
  -aet MICRODICOM -aec ORTHANC 39.104.226.62 4242
```

如果这一步能查到数据，说明 Orthanc Worklist 工作正常，问题纯粹是 MicroDicom 不支持 MWL。

---

## 五、MicroDicom 仍然有用

虽然 MicroDicom 不能查询 Worklist（申请单），但它仍然可以用于：

- **查看和下载 DICOM 影像** — 当设备拍摄完成并将影像上传到 Orthanc 后，用 MicroDicom 的 `Shift+F`（Download from DICOM server）查询和下载影像
- **浏览本地 DICOM 文件** — 打开本地的 `.dcm` 文件进行查看
- **影像测量和标注** — 对 DICOM 影像进行距离、角度等测量

---

## 六、配置参考

本仓库中的 `orthanc.json` 是基于你实际配置修正后的版本，主要改动：

| 配置项 | 你的原值 | 修正值 | 说明 |
|--------|----------|--------|------|
| `Worklists.Directory` | `"Directory"` | `"Database"` | Orthanc Worklist 插件使用 `Database` 作为键名 |
| `Worklists.FilterIssuerAet` | 未设置 | `false` | 允许所有客户端查询全部 Worklist |
