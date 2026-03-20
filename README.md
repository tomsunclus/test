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

#### DVTk Modality Emulator 详细操作步骤

##### 第一步：启动软件

安装完成后，打开 `Modality Emulator.exe`。软件主界面有多个选项卡，主要关注：
- **Configuration** — 配置本地和远程连接信息
- **Worklist** — 查询 Worklist 申请单
- **Storage** — 上传影像到 PACS
- **MPPS** — 检查状态上报

##### 第二步：配置 Emulator（Configuration 选项卡）

点击 **Configuration** 选项卡，配置以下信息：

**1) Emulator（本地 / SCU）配置：**

| 参数 | 值 | 说明 |
|------|------|------|
| **AE Title** | `DR01` | 本地设备的 AE Title，需与 Orthanc `DicomModalities` 中配置的一致 |
| **Port** | `11112` | 本地监听端口 |

**2) Remote System（远程 Orthanc 服务器 / SCP）配置：**

| 参数 | 值 | 说明 |
|------|------|------|
| **AE Title** | `ORTHANC` | Orthanc 的 AE Title |
| **IP Address** | `39.104.226.62` | 阿里云 ECS 公网 IP |
| **Port** | `4242` | Orthanc 的 DICOM 端口 |

> 你的 Orthanc `DicomModalities` 中已经配置了 `"DR01": ["DR01", "192.168.1.29", 11112]`，
> 所以本地 AE Title 建议使用 `DR01` 保持一致。

##### 第三步：测试连接（Ping / Echo）

1. 在 **Configuration** 或主界面找到 **Ping** 或 **DICOM Verification (C-ECHO)** 按钮
2. 点击后，如果显示 **Success** / **Passed**，说明网络连通且 AE Title 匹配

##### 第四步：查询 Worklist 申请单（核心操作）

1. 点击 **Worklist** 选项卡
2. 配置查询参数（可选，留空查全部）：
   - **Scheduled Date** — 可设置日期范围过滤
   - **Modality** — 可选 `DR`、`CR`、`DX` 等
   - **Scheduled Station AE Title** — 可留空或设为 `DR01`
3. 点击 **Query Worklist** 按钮
4. 下方列表会显示从 Orthanc 查到的申请单信息：
   - **Patient Name** — 患者姓名
   - **Patient ID** — 患者 ID
   - **Accession Number** — 申请号（对应你 `.wl` 文件名中的 ACC 号）
   - **Scheduled Date/Time** — 预约日期时间
   - **Modality** — 检查设备类型
   - **Procedure Description** — 检查描述
   - **Referring Physician** — 申请医生

> 如果查询结果为空，请先按照本文档第三节排查 Orthanc 服务器端的配置。

##### 第五步：模拟拍片并上传影像（可选）

查询到 Worklist 后，可以继续模拟完整的 DR 设备工作流：

1. 在 Worklist 查询结果中**选择一条申请单**
2. 点击 **Storage** 选项卡
3. 选择一个本地 DICOM 文件作为"拍摄的影像"（或使用 DVTk 自带的测试文件）
4. 点击 **Store** 按钮，将影像通过 C-STORE 上传到 Orthanc
5. 上传后在 Orthanc Web 界面 `http://39.104.226.62:8042` 可以看到新增的影像

##### 第六步：查看结果

操作完成后，主界面底部的 **Results** / **Activity Logging** 区域会显示详细的 DICOM 通信日志，包括：
- C-FIND Request/Response（Worklist 查询请求和响应）
- 返回的 DICOM 数据集内容
- 通信状态（Success / Failure）

如果有错误，可以从日志中看到具体的失败原因。

##### 常见问题

| 问题 | 解决方案 |
|------|----------|
| Ping/Echo 失败 | 检查 IP、端口、AE Title 是否正确；检查阿里云安全组是否放行 4242 端口 |
| Query Worklist 返回空 | 1. 检查 Orthanc 的 Worklist 插件配置（`Database` vs `Directory`）<br>2. 检查 Docker Volume 映射是否正确<br>3. 检查 `.wl` 文件是否在容器内可见 |
| 提示 "Association Rejected" | AE Title 不匹配，确保 DVTk 的本地 AE Title 在 Orthanc 的 `DicomModalities` 中已配置 |
| 提示 "Connection Refused" | Orthanc 服务未运行，或端口/IP 不正确 |
| 查到 Worklist 但字段为空 | `.wl` 文件生成时缺少必要的 DICOM Tag，检查 Java 后端生成逻辑 |

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
