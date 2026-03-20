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
    "microdicom": ["MICRODICOM", "你的本地IP", 11112]
  }
}
```

参数说明：
- `"microdicom"` — 自定义的标识名称
- `"MICRODICOM"` — MicroDicom 的 AE Title（需与 MicroDicom 中设置的一致）
- `"你的本地IP"` — 运行 MicroDicom 的电脑的公网 IP 地址
- `11112` — MicroDicom 本地监听的 DICOM 端口（与 MicroDicom 中 Port 设置一致）

### 2.2 另一种配置格式（Orthanc 新版本推荐）

```json
{
  "DicomModalities": {
    "microdicom": {
      "AET": "MICRODICOM",
      "Host": "你的本地IP",
      "Port": 11112,
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

### 4.1 打开 DICOM Nodes 设置

1. 打开 MicroDicom DICOM Viewer
2. 点击菜单栏：**Tools** → **Options** → 左侧选择 **DICOM Nodes**

### 4.2 设置本地 AE Title

在 Client 区域配置：

| 参数 | 值 |
|------|------|
| **AE Title** | `MICRODICOM` |
| **Port** | `11112` |

> **重要：** 勾选 **Accept receiving studies** 以允许接收数据。

### 4.3 添加远程 DICOM Node

在 DICOM Nodes 区域点击添加按钮，配置 Orthanc 服务器：

| 参数 | 值 | 说明 |
|------|------|------|
| **Address** | `39.104.226.62` | 阿里云 ECS 公网 IP |
| **Port** | `4242` | Orthanc 的 DICOM 端口 |
| **AE Title** | `ORTHANC` | Orthanc 的 AE Title |
| **Protocol** | `C-GET` 或 `C-MOVE` | 获取影像的方式 |
| **Description** | `Orthanc` | 自定义名称 |

### 4.4 测试连接 (C-ECHO)

配置完成后，列表最右侧应出现绿色 ✅ 图标，表示 Echo 通过。

## 五、查询 Worklist 申请单信息（重点）

> **⚠️ 重要区分：Worklist 查询 ≠ 影像查询（Study Query）**
>
> - MicroDicom 主界面的 **Image** 选项卡执行的是 **Study 级别的 C-FIND** 查询，用于查询已存储的 DICOM 影像/检查。
> - **Worklist（申请单）** 使用的是完全不同的 DICOM 服务——**Modality Worklist (MWL)**，使用的 SOP Class 不同。
> - 你必须使用 MicroDicom 的 **Worklist 查询功能**，而不是 Image 查询来获取申请单。

### 5.1 MicroDicom 中查询 Worklist 的操作步骤

1. 点击菜单栏：**Network** → **DICOM Worklist**
2. 在弹出的 Worklist 查询窗口中：
   - 选择目标 DICOM Node（你配置的 `Orthanc`）
   - 可设置查询过滤条件（日期、Modality 等），也可留空查询全部
3. 点击 **Query** 或 **Search** 按钮
4. 查询结果会列出 Orthanc 服务器上的申请单信息，包含：
   - 患者姓名、患者 ID、性别、出生日期
   - 检查类型（Modality）、检查描述
   - Accession Number（申请号）
   - 预约日期和时间

### 5.2 为什么 Image 查询看不到申请单

你在截图中使用的 Image 选项卡执行的是影像级别查询，它查询的是已经存储在 Orthanc 中的 DICOM 影像（Study/Series/Instance），而 **Worklist 是预约/申请信息，还没有产生影像**，所以用影像查询当然查不到。

## 六、Orthanc Worklist 插件配置（服务器端关键配置）

> **⚠️ 这一步最为关键！** 如果 Orthanc 服务器没有正确启用和配置 Worklist 插件，即使 `.wl` 文件存在于磁盘上，MicroDicom 的 Worklist 查询也不会返回任何结果。

### 6.1 确认 Worklist 插件已加载

在 Orthanc 的 `orthanc.json` 中，必须包含以下配置：

```json
{
  "Plugins": [
    "/usr/share/orthanc/plugins/libModalityWorklists.so"
  ],
  "Worklists": {
    "Enable": true,
    "Database": "/opt/orthanc/worklists",
    "FilterIssuerAet": false
  }
}
```

**参数说明：**
- `Plugins` — 指定 Worklist 插件的 `.so` 文件路径
- `Worklists.Database` — 指向存放 `.wl` 文件的目录（与你截图中的 `/opt/orthanc/worklists` 一致）
- `Worklists.FilterIssuerAet` — 设为 `false` 表示不按 AET 过滤，所有客户端都能查到所有 Worklist

### 6.2 如果使用 Docker 部署

如果 Orthanc 运行在 Docker 容器中，需要注意：

**方式一：Docker run 命令**

```bash
docker run -d --name orthanc \
  -p 4242:4242 \
  -p 8042:8042 \
  -v /opt/orthanc/config:/etc/orthanc:ro \
  -v /opt/orthanc/data/db:/var/lib/orthanc/db \
  -v /opt/orthanc/worklists:/var/lib/orthanc/worklists \
  orthancteam/orthanc
```

**方式二：Docker Compose**

```yaml
version: '3'
services:
  orthanc:
    image: orthancteam/orthanc
    ports:
      - "4242:4242"
      - "8042:8042"
    volumes:
      - /opt/orthanc/config/orthanc.json:/etc/orthanc/orthanc.json:ro
      - /opt/orthanc/data/db:/var/lib/orthanc/db
      - /opt/orthanc/worklists:/var/lib/orthanc/worklists
    environment:
      - WORKLISTS_PLUGIN_ENABLED=true
```

> **关键点：** `orthanc.json` 中 `Worklists.Database` 的路径必须是**容器内**的路径，且该路径通过 Volume 挂载到宿主机的 `/opt/orthanc/worklists`。

### 6.3 确认插件路径正确

不同 Orthanc 版本/安装方式的插件路径不同：

| 安装方式 | 插件路径 |
|----------|----------|
| **Docker (orthancteam/orthanc)** | `/usr/share/orthanc/plugins/libModalityWorklists.so` |
| **Docker (jodogne/orthanc-plugins)** | `/usr/share/orthanc/plugins/libModalityWorklists.so` |
| **apt 安装 (Debian/Ubuntu)** | `/usr/lib/orthanc/plugins/libModalityWorklists.so` 或 `/usr/share/orthanc/plugins/libModalityWorklists.so` |
| **手动编译** | 自定义路径 |

可在服务器上执行以下命令查找：

```bash
find / -name "libModalityWorklists.so" 2>/dev/null
```

### 6.4 验证插件是否加载成功

重启 Orthanc 后，通过 REST API 检查插件是否已加载：

```bash
curl http://39.104.226.62:8042/plugins
```

返回结果中应包含 `"worklists"` 或 `"modality-worklists"`。

也可以查看 Orthanc 启动日志：

```bash
# Docker
docker logs orthanc | grep -i worklist

# systemd
journalctl -u orthanc | grep -i worklist
```

应能看到类似：`Registering plugin: worklists` 的日志。

### 6.5 通过 REST API 验证 Worklist 数据

```bash
curl http://39.104.226.62:8042/modalities/microdicom/find-worklist -X POST -d '{}'
```

如果返回 Worklist 数据，说明服务器端配置正确。

## 七、查询和获取 DICOM 影像

### 7.1 查询影像 (C-FIND / Query)

1. 在 MicroDicom 主界面选择 **Image** 选项卡
2. 设置查询条件（可选）：
   - 日期范围、Modality 类型等
3. 点击搜索
4. 查询结果会显示 Orthanc 上存储的检查列表

### 7.2 获取影像 (C-GET / C-MOVE)

- 如果使用 **C-GET**（你当前的配置）：MicroDicom 直接从 Orthanc 拉取数据，不需要反向连接
- 如果使用 **C-MOVE**：Orthanc 需要主动推送数据回 MicroDicom，需要确保网络可达

## 八、完整排查流程（针对你当前的问题）

根据你的截图，当前配置为：
- MicroDicom AE Title: `MICRODICOM`，Port: `11112`
- Orthanc: `39.104.226.62:4242`，AE Title: `ORTHANC`
- Echo 已通过 ✅
- Worklist 文件已存在于 `/opt/orthanc/worklists/` ✅
- 但查不到申请单 ❌

### 排查步骤：

#### 步骤 1：检查 Orthanc Worklist 插件是否启用

登录阿里云服务器，执行：

```bash
# 检查插件是否加载
curl -u orthanc:orthanc http://localhost:8042/plugins

# 查看插件列表中是否有 worklists
curl -u orthanc:orthanc http://localhost:8042/plugins/worklists
```

如果 **没有** `worklists` 插件，说明 **Worklist 插件未启用**，这是根本原因。

#### 步骤 2：启用 Worklist 插件

在 Orthanc 的配置文件中添加（参见上面第六节的配置），然后重启 Orthanc。

#### 步骤 3：确认 Worklist 文件路径一致

确保 `orthanc.json` 中 `Worklists.Database` 的路径指向 `.wl` 文件所在的目录。

如果用 Docker，注意区分宿主机路径和容器内路径：
- 宿主机路径：`/opt/orthanc/worklists/`（你截图中看到的）
- 容器内路径：取决于 Volume 映射配置

可以进入容器检查：

```bash
docker exec -it orthanc ls -la /var/lib/orthanc/worklists/
# 或者你实际映射的容器内路径
```

#### 步骤 4：在 MicroDicom 中使用 Worklist 查询

**不要**使用 Image 选项卡查询，请使用：

**Network** → **DICOM Worklist**

#### 步骤 5：检查 Orthanc 日志

查看 Orthanc 收到 Worklist 查询时的日志：

```bash
docker logs -f orthanc
```

然后在 MicroDicom 发起 Worklist 查询，观察日志中是否有相关请求和错误信息。

## 九、常见问题排查

### 9.1 C-ECHO 失败

| 可能原因 | 解决方案 |
|----------|----------|
| 安全组未放行端口 | 检查阿里云安全组是否放行 `4242` 端口 |
| Orthanc 服务未运行 | 登录服务器检查 Orthanc 进程状态 |
| AE Title 不匹配 | 确保 MicroDicom 和 Orthanc 配置的 AE Title 完全一致 |
| IP 地址错误 | 确认使用的是阿里云 ECS 的公网 IP |
| 防火墙阻拦 | 检查本地防火墙和服务器防火墙设置 |

### 9.2 Worklist 查询无结果（重点）

| 可能原因 | 解决方案 |
|----------|----------|
| **Worklist 插件未启用** | 检查 `orthanc.json` 是否配置了 `Plugins` 和 `Worklists` 段（最常见原因） |
| **插件 .so 文件路径错误** | 用 `find / -name "libModalityWorklists.so"` 确认实际路径 |
| **Worklist 文件目录不对** | 确认 `Worklists.Database` 指向 `.wl` 文件所在目录 |
| **Docker 路径映射问题** | 容器内路径与宿主机路径不同，确认 Volume 映射正确 |
| **使用了 Image 查询而非 Worklist 查询** | 在 MicroDicom 中使用 Network → DICOM Worklist |
| **.wl 文件格式错误** | 用 `dcmdump` 工具验证 .wl 文件内容 |
| **DicomAlwaysAllowFindWorklist 为 false** | 在 `orthanc.json` 中设为 `true` |

### 9.3 影像下载显示 0/1（下载失败）

从你截图的 Network Activity 中看到 "Downloading images" 显示 `0/1`，表示找到了 1 条记录但下载了 0 个文件。可能原因：

| 可能原因 | 解决方案 |
|----------|----------|
| C-GET 未在 Orthanc 启用 | 确保 `DicomAlwaysAllowGet` 设为 `true` |
| Orthanc 上没有实际影像文件 | Worklist 是申请信息，不包含影像；影像需要设备拍摄后上传 |
| 传输语法不兼容 | 尝试将 MicroDicom 的 Preferred transfer syntax 改为 `Implicit VR LE` |

### 9.4 C-MOVE 的网络要求

C-MOVE 是由 Orthanc 服务器**主动推送**影像到 MicroDicom，如果你的电脑在 NAT/内网环境下，需要：

1. 在路由器上设置端口转发（将外网端口映射到 MicroDicom 的本地端口）
2. 在 Orthanc 的 `DicomModalities` 中填写你的公网 IP 和映射后的端口
3. 或者改用 **C-GET** 协议（你当前已选择 C-GET，这是正确的选择）

## 十、使用 Orthanc Web 界面验证数据

如果 DICOM 协议连接遇到困难，可以通过 Orthanc 的 Web 界面和 REST API 验证数据是否存在：

```bash
# 查看已存储的影像
curl -u orthanc:orthanc http://39.104.226.62:8042/studies

# 查看 Worklist 插件状态
curl -u orthanc:orthanc http://39.104.226.62:8042/plugins/worklists

# 通过浏览器访问 Web 界面
# http://39.104.226.62:8042
```

## 十一、快速检查清单

**服务器端（Orthanc）：**

- [ ] Worklist 插件 (`libModalityWorklists.so`) 已在 `orthanc.json` 的 `Plugins` 中声明
- [ ] `Worklists.Database` 指向 `.wl` 文件所在目录
- [ ] `DicomAlwaysAllowFindWorklist` 设为 `true`
- [ ] 重启 Orthanc 服务使配置生效
- [ ] `curl http://localhost:8042/plugins` 返回结果中包含 `worklists`

**客户端（MicroDicom）：**

- [ ] 使用 **Network → DICOM Worklist** 查询（而非 Image 查询）
- [ ] DICOM Node 配置中 AE Title、IP、Port 正确
- [ ] C-ECHO 测试通过

**网络：**

- [ ] 阿里云安全组已放行 `4242` 端口
- [ ] 如使用 C-MOVE，本地端口 `11112` 可被 Orthanc 访问到
