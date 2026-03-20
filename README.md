# 阿里云 Orthanc Worklist（申请单）完整部署指南

## 系统架构

```
  ┌──────────────┐    C-FIND(MWL)   ┌──────────────┐    REST API    ┌──────────────┐
  │  DR 设备/模拟器 │ ─────────────→ │   Orthanc    │ ←──────────── │  Java 后端    │
  │  (DVTk/真实DR)  │               │  (阿里云)     │               │ (生成Worklist) │
  │              │    C-STORE       │              │               │              │
  │              │ ────────────→    │              │               │              │
  └──────────────┘   (上传影像)      └──────────────┘               └──────────────┘
                                         │
                                         │ C-FIND(Study) + C-GET
                                         ▼
                                  ┌──────────────┐
                                  │  MicroDicom   │
                                  │  (查看影像)    │
                                  └──────────────┘
```

| 角色 | 软件 | 功能 |
|------|------|------|
| 申请单生成 | Java 后端 | 通过 REST API 上传 Worklist DICOM 到 Orthanc |
| PACS 服务器 | Orthanc | 存储 Worklist 和 DICOM 影像 |
| DR 设备模拟 | DVTk Modality Emulator | 查询 Worklist → 模拟拍片 → 上传影像 |
| 影像查看 | MicroDicom | 从 Orthanc 下载并查看已拍摄的影像 |

> **MicroDicom 不支持 Worklist 查询**（所有版本都不支持，这是软件定位决定的）。需要用 DVTk 或 DCMTK 查询。

---

## 一、服务器部署

### 1.1 目录结构

```
/opt/orthanc/
├── config/
│   └── orthanc.json          # Orthanc 配置文件
├── data/
│   ├── db/                   # Orthanc 数据库
│   ├── storage/              # DICOM 影像存储
│   └── worklists/            # Worklist .wl 文件（重要！）
├── docker-compose.yml
└── export-worklists.sh       # Worklist 导出脚本
```

### 1.2 docker-compose.yml

```yaml
services:
  orthanc:
    image: orthancteam/orthanc:latest
    container_name: orthanc
    restart: unless-stopped
    ports:
      - "8042:8042"
      - "4242:4242"
    volumes:
      - ./data:/var/lib/orthanc
      - ./config/orthanc.json:/etc/orthanc/orthanc.json:ro
    environment:
      - OHIF_PLUGIN_ENABLED=true
      - DICOM_WEB_PLUGIN_ENABLED=true
      - WORKLISTS_PLUGIN_ENABLED=true
```

**关键点：**
- `./data:/var/lib/orthanc` — 只用一个 Volume 映射，不要重叠映射子目录
- Worklist 文件放在 `./data/worklists/` 下，自动映射到容器内 `/var/lib/orthanc/worklists/`
- 通过环境变量启用 OHIF、DicomWeb、Worklists 插件

### 1.3 orthanc.json 关键配置

#### Worklist 插件

```json
"Worklists": {
    "Enable": true,
    "Database": "/var/lib/orthanc/worklists",
    "FilterIssuerAet": false
}
```

> **注意：** 键名必须是 `"Database"`，不是 `"Directory"`。`FilterIssuerAet` 设为 `false` 允许所有客户端查询。

#### 开放 DICOM 访问

```json
"DicomAlwaysAllowEcho": true,
"DicomAlwaysAllowFind": true,
"DicomAlwaysAllowFindWorklist": true,
"DicomAlwaysAllowStore": true,
"DicomAlwaysAllowGet": true,
"DicomAlwaysAllowMove": true
```

#### 设备配置

```json
"DicomModalities": {
    "DR01": ["DR01", "192.168.1.29", 11112],
    "MICRODICOM": ["MICRODICOM", "192.168.1.29", 11112]
}
```

---

## 二、Worklist 导出（从 Orthanc 实例导出为 .wl 文件）

Java 后端通过 REST API 将 Worklist 上传为 Orthanc 实例后，需要导出为 `.wl` 文件供 Worklist 插件读取：

```bash
#!/bin/bash
ORTHANC_URL="http://localhost:8042"
AUTH="admin:your_password"
WORKLISTS_DIR="/opt/orthanc/data/worklists"

mkdir -p $WORKLISTS_DIR

for ID in $(curl -s -u $AUTH -X POST \
  -H "Content-Type: application/json" \
  -d '{"Level":"Instance","Query":{"SOPClassUID":"1.2.840.10008.5.1.4.31"}}' \
  $ORTHANC_URL/tools/find | python3 -c "import sys,json;print('\n'.join(json.load(sys.stdin)))"); do
  ACC=$(curl -s -u $AUTH "$ORTHANC_URL/instances/$ID/content/00080050" | tr -d ' "')
  [ -n "$ACC" ] && curl -s -u $AUTH "$ORTHANC_URL/instances/$ID/file" -o "$WORKLISTS_DIR/${ACC}.wl" && echo "导出: $ACC"
done
```

> **路径必须是 `/opt/orthanc/data/worklists`**（在 `data` 目录下），因为 Docker Volume 映射的是 `./data:/var/lib/orthanc`。

---

## 三、DVTk Modality Emulator 操作

### 3.1 Configure Remote Systems 选项卡

**RIS System（Worklist 查询目标 = Orthanc）：**

| 参数 | 值 |
|------|------|
| IP Address | `39.104.226.62`（阿里云公网 IP） |
| Remote Port | `4242` |
| AE Title | `ORTHANC` |

**PACS/Workstation Systems（影像上传目标 = Orthanc）：**

| 参数 | 值 |
|------|------|
| IP Address | `39.104.226.62` |
| Remote Port | `4242` |
| AE Title | `ORTHANC` |

### 3.2 Control 选项卡操作

1. **Request Worklist** — 查询申请单列表
2. **Store Image** — 模拟拍片后上传影像到 Orthanc

---

## 四、验证命令

```bash
# 检查插件加载
curl -u admin:your_password http://localhost:8042/plugins

# 检查容器内 worklist 文件
docker exec orthanc ls -la /var/lib/orthanc/worklists/

# Python 测试 DICOM Echo
python3 -c "
from pynetdicom import AE
ae = AE(ae_title=b'DR01')
ae.add_requested_context('1.2.840.10008.1.1')
assoc = ae.associate('localhost', 4242, ae_title=b'ORTHANC')
if assoc.is_established:
    status = assoc.send_c_echo()
    print('Echo 成功! Status:', hex(status.Status))
    assoc.release()
"

# Python 测试 Worklist 查询
python3 -c "
from pynetdicom import AE
from pynetdicom.sop_class import ModalityWorklistInformationFind
from pydicom.dataset import Dataset
ae = AE(ae_title=b'DR01')
ae.add_requested_context(ModalityWorklistInformationFind)
assoc = ae.associate('localhost', 4242, ae_title=b'ORTHANC')
if assoc.is_established:
    ds = Dataset()
    ds.PatientName = ''
    ds.PatientID = ''
    ds.AccessionNumber = ''
    responses = assoc.send_c_find(ds, ModalityWorklistInformationFind)
    count = 0
    for status, identifier in responses:
        if status and status.Status in (0xFF00, 0xFF01):
            count += 1
            name = identifier.PatientName if 'PatientName' in identifier else '?'
            acc = identifier.AccessionNumber if 'AccessionNumber' in identifier else '?'
            print('申请单%d: %s / %s' % (count, name, acc))
    print('共查到 %d 条' % count)
    assoc.release()
"
```

---

## 五、踩坑记录

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| MicroDicom 查不到 Worklist | MicroDicom 不支持 MWL 查询（软件定位问题） | 使用 DVTk Modality Emulator |
| Worklist 配置不生效 | `orthanc.json` 中用了 `"Directory"` | 改为 `"Database"` |
| 容器内看不到 .wl 文件 | Docker Volume 映射重叠冲突 | 只用 `./data:/var/lib/orthanc` 一个映射 |
| .wl 文件写入后消失 | 两个 Volume 映射 (`./data` 和 `./worklists`) 指向同一容器路径的不同子目录 | 去掉 `./worklists` 映射，文件写到 `./data/worklists/` |
| Worklist 查询返回 0 条 | `.wl` 文件不在容器可见的目录中 | 确保文件在 `/opt/orthanc/data/worklists/` |
| DVTk DICOM Echo 失败 | DVTk 发送的 PDU 与 Orthanc 不兼容（DVTk 问题） | 不影响 Worklist 查询，可忽略 |
| OHIF 插件消失 | docker-compose.yml 缺少环境变量 | 添加 `OHIF_PLUGIN_ENABLED=true` |
