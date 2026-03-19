# Orthanc + OHIF Viewer 部署方案

## 问题分析

访问 `http://IP:8042/ohif/` 返回 404 的原因是：**Orthanc 服务器没有安装 OHIF 插件**。

### 当前状态

| 组件 | 状态 | 说明 |
|------|------|------|
| Orthanc 核心 | ✅ 正常 | HTTP API 可访问 (8042) |
| DICOMweb 插件 | ✅ 正常 | `/dicom-web/studies` 可正常查询 |
| OHIF 插件 | ❌ 缺失 | `/ohif/` 返回 404 |

### 根因

Orthanc 本身**不自带** OHIF Viewer。OHIF 是一个**独立的插件** (`libOrthancOHIF.so`)，需要单独安装并在配置文件中启用。你的 Orthanc 安装只包含了核心功能和 DICOMweb 插件，但没有包含 OHIF 插件。

---

## 解决方案

提供两种方式，推荐使用 **方案一（Docker 方式）**。

### 方案一：Docker 方式部署（推荐）

使用 `orthancteam/orthanc` Docker 镜像，该镜像已内置 OHIF 插件。

详见 [`orthanc-config/docker/`](orthanc-config/docker/) 目录。

```bash
cd orthanc-config/docker
docker-compose up -d
```

### 方案二：原生安装方式

在现有的 Orthanc 安装上手动添加 OHIF 插件。

详见 [`orthanc-config/native/`](orthanc-config/native/) 目录。

---

## 快速验证

部署完成后，访问以下地址验证：

| 地址 | 说明 |
|------|------|
| `http://IP:8042/` | Orthanc Explorer（管理界面） |
| `http://IP:8042/ohif/` | OHIF Viewer（医学影像查看器） |
| `http://IP:8042/dicom-web/studies` | DICOMweb API |
