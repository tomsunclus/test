# 阿里云 Orthanc Worklist（申请单）查询指南

## 当前问题总结

| 现状 | 状态 |
|------|------|
| Orthanc 服务器已部署在阿里云 | ✅ |
| Java 后端已生成 `.wl` 文件到 `/opt/orthanc/worklists/` | ✅ |
| MicroDicom C-ECHO 连接已通 | ✅ |
| MicroDicom 查询到申请单（Worklist） | ❌ |

**根本原因：MicroDicom 是 DICOM 影像查看器，不是设备模拟器，所有版本都不支持 Worklist 查询。**

---

## 一、为什么 MicroDicom 不能查 Worklist

### 这是软件定位问题，不是版本问题

MicroDicom **所有版本**（包括最新的 2025.4）都不支持 Modality Worklist (MWL) 查询。这不是某个版本的缺失，而是这款软件的**产品定位**决定的：

| 软件类型 | 支持的 DICOM 服务 | 典型软件 |
|----------|-------------------|----------|
| **DICOM 影像查看器** | C-ECHO、C-FIND (Study)、C-GET、C-MOVE、C-STORE | MicroDicom、RadiAnt |
| **设备模拟器 / 模态工作站** | C-ECHO、**MWL C-FIND (Worklist)**、C-STORE、MPPS | DVTk Modality Emulator、真实 DR 设备 |

MicroDicom 的角色类似于「看片软件」，它能从 PACS 下载和查看影像，但它**不模拟设备行为**。

真实的 DR 设备工作流程是：
1. **查询 Worklist** → 获取待拍摄的申请单列表（MWL C-FIND）
2. **选择申请单** → 技师选择对应患者
3. **拍摄影像** → 设备采集 DICOM 影像
4. **上传影像** → 将影像发送到 PACS/Orthanc（C-STORE）
5. **上报状态** → 通知 RIS 检查完成（MPPS N-CREATE / N-SET）

MicroDicom 只能做第 4 步的反向操作（从 PACS 下载影像），不能做第 1 步（查询 Worklist）。

---

## 二、推荐：用于模拟 DR 设备的软件

如果你需要**模拟 DR 设备**来测试与 Orthanc 的完整工作流（Worklist 查询 → 影像上传），以下工具可以替代 MicroDicom：

### 方案一：DVTk Modality Emulator（强烈推荐）

**最接近真实 DR 设备行为的免费模拟器。**

- **官网**: https://www.dvtk.org
- **平台**: Windows（需要 .NET 4.0）
- **费用**: 免费开源
- **支持的 DICOM 服务**:
  - ✅ Worklist 查询 (MWL C-FIND SCU)
  - ✅ 影像存储 (C-STORE SCU)
  - ✅ MPPS（检查状态上报）
  - ✅ C-ECHO 验证

**操作步骤：**

1. 下载并安装 DVTk Modality Emulator
   - 下载地址: https://www.dvtk.org/dicom/modality-emulator/
2. 配置远程 DICOM 节点：
   - Remote AE Title: `ORTHANC`
   - Remote IP: `39.104.226.62`
   - Remote Port: `4242`
   - Local AE Title: `DR01`（与 Orthanc 中 DicomModalities 配置一致）
3. 点击 **Query Worklist** 按钮
4. 即可看到 Orthanc 上的申请单列表

### 方案二：Miele-WL Worklist Client

**轻量级 Worklist 查询客户端。**

- **来源**: Microsoft Store（搜索 "Miele-WL"）
- **平台**: Windows x64
- **费用**: 免费
- **功能**: 专门用于 Worklist C-FIND 查询，界面简洁

### 方案三：DCMTK findscu 命令行（快速验证）

**最快的验证方式，适合在服务器上直接测试。**

```bash
# 安装
sudo apt-get install dcmtk    # Ubuntu/Debian
sudo yum install dcmtk        # CentOS

# 查询 Orthanc 上的全部 Worklist
findscu -v -W \
  -k 0008,0050="" \
  -k 0010,0010="" \
  -k 0010,0020="" \
  -k 0020,000D="" \
  -k 0008,0060="" \
  -k 0040,0100="" \
  -aet DR01 -aec ORTHANC \
  39.104.226.62 4242
```

参数说明：
- `-W` — 使用 Worklist 模式（关键参数）
- `-k 0008,0050=""` — Accession Number
- `-k 0010,0010=""` — Patient Name
- `-k 0010,0020=""` — Patient ID
- `-k 0008,0060=""` — Modality
- `-k 0040,0100=""` — Scheduled Procedure Step Sequence

Windows 上可以下载 DCMTK 预编译包：https://dicom.offis.de/dcmtk.php.en

### 方案四：Python Modality Emulator（可定制）

GitHub 上有基于 pynetdicom 的开源模态设备模拟器，可以自定义完整的 DR 设备工作流：

- https://github.com/hendrapaiton/Modality-Emulator
- 支持 MWL 查询 (C-FIND)
- 支持影像上传 (C-STORE)
- MIT 开源协议，可自由修改

### 软件对比

| 软件 | Worklist 查询 | 影像上传 | MPPS | GUI | 适合场景 |
|------|:---:|:---:|:---:|:---:|----------|
| **DVTk Modality Emulator** | ✅ | ✅ | ✅ | ✅ | 完整模拟 DR 设备 |
| **Miele-WL** | ✅ | ❌ | ❌ | ✅ | 只需查询 Worklist |
| **DCMTK findscu** | ✅ | ❌ | ❌ | ❌ | 命令行快速验证 |
| **Python Emulator** | ✅ | ✅ | ❌ | ❌ | 自定义开发 |
| **MicroDicom** | ❌ | ❌ | ❌ | ✅ | 仅查看影像 |

---

## 三、修正 Orthanc Worklist 插件配置（服务器端）

不论使用哪个客户端，都需要确保 Orthanc 服务器端的 Worklist 配置正确。

### 3.1 你当前的配置（可能有问题）

```json
"Worklists": {
    "Enable": true,
    "Directory": "/var/lib/orthanc/worklists"
}
```

### 3.2 正确的配置

Orthanc 官方 Worklist 插件使用的键名是 `"Database"`，不是 `"Directory"`：

```json
"Worklists": {
    "Enable": true,
    "Database": "/var/lib/orthanc/worklists",
    "FilterIssuerAet": false
}
```

> `FilterIssuerAet` 设为 `false` 表示所有客户端查询都能获取全部 Worklist，不按 AET 过滤。

### 3.3 修改后重启 Orthanc

```bash
docker restart orthanc
```

### 3.4 验证 Worklist 插件是否正常加载

```bash
# 查看已加载的插件列表
curl -u admin:StrongPassword_123456 http://localhost:8042/plugins

# 查看 worklists 插件详情
curl -u admin:StrongPassword_123456 http://localhost:8042/plugins/worklists
```

### 3.5 确认 .wl 文件路径映射（Docker 环境）

你的 `.wl` 文件在宿主机的 `/opt/orthanc/worklists/`，`orthanc.json` 中配置的是容器内路径 `/var/lib/orthanc/worklists`。

确保 Docker Volume 映射正确：

```bash
# 检查容器内是否能看到 .wl 文件
docker exec orthanc ls -la /var/lib/orthanc/worklists/

# 查看 Volume 映射
docker inspect orthanc | grep -A 10 Mounts
```

如果容器内看不到文件，需要添加 Volume 映射：

```bash
-v /opt/orthanc/worklists:/var/lib/orthanc/worklists
```

---

## 四、完整排查步骤

### 步骤 1：修正 orthanc.json

将 `"Directory"` 改为 `"Database"`，添加 `"FilterIssuerAet": false`。重启 Orthanc。

### 步骤 2：确认 Volume 映射和文件存在

```bash
docker exec orthanc ls -la /var/lib/orthanc/worklists/
```

### 步骤 3：验证插件加载

```bash
curl -u admin:StrongPassword_123456 http://localhost:8042/plugins
```

### 步骤 4：用 findscu 测试 Worklist 查询

```bash
findscu -v -W -k 0008,0050="" -k 0010,0010="" \
  -aet DR01 -aec ORTHANC localhost 4242
```

能查到数据 → Orthanc Worklist 配置正确 → 换用 DVTk Modality Emulator 即可。

### 步骤 5：安装 DVTk Modality Emulator 模拟 DR 设备

下载安装后，配置 Orthanc 连接信息，即可查询 Worklist 并模拟完整的 DR 设备工作流。

---

## 五、各软件的角色定位

```
                        你的系统架构
                        
  ┌──────────────┐    Worklist    ┌──────────────┐    REST API    ┌──────────────┐
  │  DR 设备/模拟器 │ ──C-FIND──→ │   Orthanc    │ ←──────────── │  Java 后端    │
  │ (DVTk/真实DR) │              │  (阿里云)     │               │ (生成.wl文件)  │
  │              │    C-STORE    │              │               │              │
  │              │ ────────────→ │              │               │              │
  └──────────────┘   (上传影像)    └──────────────┘               └──────────────┘
                                       │
                                       │ C-FIND (Study) + C-GET
                                       ▼
                                ┌──────────────┐
                                │  MicroDicom   │
                                │ (查看影像)     │
                                └──────────────┘
```

| 角色 | 软件 | 功能 |
|------|------|------|
| **申请单生成** | Java 后端 | 创建 `.wl` 文件写入 Orthanc |
| **PACS 服务器** | Orthanc | 存储 Worklist 和 DICOM 影像 |
| **DR 设备模拟** | DVTk Modality Emulator | 查询 Worklist → 模拟拍片 → 上传影像 |
| **影像查看** | MicroDicom | 从 Orthanc 下载并查看已拍摄的影像 |

---

## 六、配置参考

本仓库中的 `orthanc.json` 是基于你实际配置修正后的版本，主要改动：

| 配置项 | 原值 | 修正值 | 说明 |
|--------|------|--------|------|
| `Worklists` 键名 | `"Directory"` | `"Database"` | Orthanc Worklist 插件使用 `Database` 作为键名 |
| `Worklists.FilterIssuerAet` | 未设置 | `false` | 允许所有客户端查询全部 Worklist |
| `DicomAlwaysAllowFindWorklist` | 未设置 | `true` | 允许任意 DICOM 节点查询 Worklist |
