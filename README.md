# MicroDicom DICOM Viewer 连接阿里云 Orthanc 服务器操作指南

## 前提条件

- 阿里云上的 Orthanc 服务器已部署并运行
- 已安装 MicroDicom DICOM Viewer (64-bit)
- 阿里云安全组已放行 Orthanc 的 DICOM 端口（默认 `4242`）

## 一、确认 Orthanc 服务器信息

在开始配置 MicroDicom 之前，你需要确认以下 Orthanc 服务器信息：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| **服务器 IP** | 阿里云 ECS 的公网 IP 地址 | - |
| **DICOM 端口** | Orthanc 的 DICOM 协议端口 | `4242` |
| **HTTP 端口** | Orthanc 的 REST API / Web 界面端口 | `8042` |
| **AET (AE Title)** | Orthanc 的 Application Entity Title | `ORTHANC` |

> 这些值在 Orthanc 的配置文件 `orthanc.json` 中设定。

## 二、Orthanc 服务器端配置（重要）

Orthanc 默认**只允许已知的 DICOM 节点**进行连接。你需要在服务器端的 `orthanc.json` 中添加 MicroDicom 作为已知的 Modality（模态设备）。

### 2.1 修改 orthanc.json

在 Orthanc 服务器的配置文件中，找到 `DicomModalities` 部分，添加 MicroDicom 的配置：

```json
{
  "DicomModalities": {
    "microdicom": ["MICRODICOM", "你的本地IP", 104]
  }
}
```

参数说明：
- `"microdicom"` — 自定义的标识名称
- `"MICRODICOM"` — MicroDicom 的 AE Title（需与 MicroDicom 中设置的一致）
- `"你的本地IP"` — 运行 MicroDicom 的电脑的公网 IP 地址
- `104` — MicroDicom 本地监听的 DICOM 端口（默认 104）

### 2.2 另一种配置格式（Orthanc 新版本推荐）

```json
{
  "DicomModalities": {
    "microdicom": {
      "AET": "MICRODICOM",
      "Host": "你的本地IP",
      "Port": 104,
      "AllowEcho": true,
      "AllowFind": true,
      "AllowFindWorklist": true,
      "AllowGet": true,
      "AllowMove": true,
      "AllowStore": true,
      "AllowTranscoding": true
    }
  }
}
```

### 2.3 如果不想限制连接来源

可以在 `orthanc.json` 中设置：

```json
{
  "DicomCheckCalledAet": false,
  "DicomAlwaysAllowEcho": true,
  "DicomAlwaysAllowFind": true,
  "DicomAlwaysAllowFindWorklist": true,
  "DicomAlwaysAllowGet": true,
  "DicomAlwaysAllowMove": true,
  "DicomAlwaysAllowStore": true
}
```

> **注意：** 这种方式会允许任何 DICOM 节点连接，仅建议在测试环境使用。

### 2.4 重启 Orthanc 服务

修改配置后需要重启 Orthanc 服务使配置生效：

```bash
# 如果使用 Docker
docker restart orthanc

# 如果使用 systemd
sudo systemctl restart orthanc
```

## 三、阿里云安全组配置

确保阿里云 ECS 的安全组规则中已放行以下端口：

| 端口 | 协议 | 用途 |
|------|------|------|
| `4242` | TCP | Orthanc DICOM 服务端口 |
| `8042` | TCP | Orthanc Web 管理界面（可选） |

操作步骤：
1. 登录 [阿里云控制台](https://ecs.console.aliyun.com/)
2. 找到对应的 ECS 实例
3. 点击「安全组」→ 「配置规则」
4. 添加入方向规则，放行 TCP 端口 `4242`

## 四、MicroDicom 客户端配置

### 4.1 打开 PACS 服务器设置

1. 打开 MicroDicom DICOM Viewer
2. 点击菜单栏：**Network** → **PACS Server Settings**（或按快捷键）

### 4.2 设置本地 AE Title

在 PACS 设置窗口中，配置本地（Local）信息：

| 参数 | 值 |
|------|------|
| **Local AE Title** | `MICRODICOM`（需与 Orthanc 服务器端配置的一致） |
| **Local Port** | `104`（或其他未被占用的端口） |

### 4.3 添加远程 PACS 服务器

点击 **Add** 按钮，添加 Orthanc 服务器：

| 参数 | 值 | 说明 |
|------|------|------|
| **Description** | `Orthanc-Aliyun`（自定义名称） | 用于标识服务器 |
| **AE Title** | `ORTHANC` | Orthanc 的 AE Title |
| **IP / Hostname** | 阿里云 ECS 的公网 IP | 例如 `47.xxx.xxx.xxx` |
| **Port** | `4242` | Orthanc 的 DICOM 端口 |

### 4.4 测试连接 (C-ECHO)

1. 选中刚添加的 Orthanc 服务器
2. 点击 **Echo** 或 **Verify** 按钮
3. 如果显示 **Success** 或 **Echo OK**，说明连接成功

## 五、查询和获取 DICOM 影像（申请信息）

### 5.1 查询影像 (C-FIND / Query)

1. 点击菜单栏：**Network** → **Query/Retrieve**（或 **PACS Query**）
2. 选择目标服务器（刚配置的 `Orthanc-Aliyun`）
3. 设置查询条件（可选）：
   - **Patient Name** — 患者姓名
   - **Patient ID** — 患者 ID
   - **Study Date** — 检查日期（格式：`YYYYMMDD`，支持范围如 `20260101-20260320`）
   - **Modality** — 设备类型（如 `CT`、`MR`、`DR`、`CR` 等）
   - **Accession Number** — 检查号
4. 点击 **Search** 或 **Query** 按钮
5. 查询结果会显示 Orthanc 上存储的检查列表

### 5.2 获取影像 (C-MOVE / Retrieve)

1. 在查询结果中选择要获取的检查
2. 右键点击 → 选择 **Retrieve** 或点击 **Retrieve** 按钮
3. MicroDicom 会通过 C-MOVE 从 Orthanc 下载选中的影像数据
4. 下载完成后，影像会自动在 MicroDicom 中打开

### 5.3 查询 Worklist（申请/预约信息）

如果 Orthanc 配置了 Worklist 插件，可以查询申请信息：

1. 点击菜单栏：**Network** → **Worklist Query**（如果有此选项）
2. 选择目标服务器
3. 点击 **Query** 查询
4. 结果会显示待检查的申请信息列表，包含：
   - 患者信息（姓名、ID、性别、出生日期）
   - 检查信息（检查类型、检查描述）
   - 预约信息（预约日期、时间）
   - 申请号（Accession Number）

## 六、常见问题排查

### 6.1 C-ECHO 失败

| 可能原因 | 解决方案 |
|----------|----------|
| 安全组未放行端口 | 检查阿里云安全组是否放行 `4242` 端口 |
| Orthanc 服务未运行 | 登录服务器检查 Orthanc 进程状态 |
| AE Title 不匹配 | 确保 MicroDicom 和 Orthanc 配置的 AE Title 完全一致 |
| IP 地址错误 | 确认使用的是阿里云 ECS 的公网 IP |
| 防火墙阻拦 | 检查本地防火墙和服务器防火墙设置 |

### 6.2 C-FIND 查询无结果

- 确认 Orthanc 服务器上确实有 DICOM 数据
- 可通过浏览器访问 `http://阿里云IP:8042` 确认数据是否存在
- 放宽查询条件（留空所有条件查询全部数据）

### 6.3 C-MOVE 获取失败

- C-MOVE 需要 Orthanc **主动连接回** MicroDicom，因此：
  - MicroDicom 所在电脑必须有公网 IP 或端口映射
  - Orthanc 的 `DicomModalities` 中配置的 IP 和端口必须是 Orthanc 能访问到的地址
- **替代方案**：使用 C-GET（如果 MicroDicom 支持），C-GET 不需要反向连接

### 6.4 C-MOVE 的网络要求

由于 C-MOVE 是由 Orthanc 服务器**主动推送**影像到 MicroDicom，如果你的电脑在 NAT/内网环境下，需要：

1. 在路由器上设置端口转发（将外网端口映射到 MicroDicom 的本地端口）
2. 在 Orthanc 的 `DicomModalities` 中填写你的公网 IP 和映射后的端口
3. 或者改用 Orthanc Web 界面直接下载 DICOM 文件

## 七、使用 Orthanc Web 界面作为备选方案

如果 DICOM 协议连接遇到困难，可以通过 Orthanc 的 Web 界面查看和下载数据：

1. 在浏览器中访问 `http://阿里云公网IP:8042`
2. 输入用户名和密码（默认通常是 `orthanc` / `orthanc`）
3. 在 Web 界面中可以：
   - 浏览所有检查
   - 搜索患者
   - 下载 DICOM 文件
   - 使用内置 DICOM Viewer 查看影像

## 八、快速检查清单

- [ ] 阿里云安全组已放行 `4242` 端口
- [ ] Orthanc 服务正在运行
- [ ] Orthanc 的 `orthanc.json` 中已配置 MicroDicom 的 Modality 信息（或开放了免验证模式）
- [ ] MicroDicom 中设置了正确的 Local AE Title
- [ ] MicroDicom 中添加了 Orthanc 服务器（IP、端口、AE Title）
- [ ] C-ECHO 测试连接成功
- [ ] 如需 C-MOVE，确保 Orthanc 能反向连接到 MicroDicom
