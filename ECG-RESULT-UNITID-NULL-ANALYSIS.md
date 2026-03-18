# ECG Result 接口返回 -1 问题分析：unitId must not be null

## 问题现象

调用 `POST http://192.168.100.69:8280/gw-xtjc/ecg/result` 接口，返回：

```json
{
    "code": -1,
    "msg": "failure",
    "data": null
}
```

Tomcat 日志报错：

```
java.lang.IllegalArgumentException: unitId must not be null
    at org.springframework.util.Assert.notNull(Assert.java:201)
    at com.yrd.healthcare.sys.impl.BasePKGeneratorServiceImpl.getSerialType(BasePKGeneratorServiceImpl.java:125)
    at com.yrd.his.cloud.sys.service.impl.CodeGeneratorServiceImpl.generateCode(CodeGeneratorServiceImpl.java:47)
    at com.yrd.his.cloud.jyjc.service.impl.JyjcEcgResultServiceImpl.save(JyjcEcgResultServiceImpl.java:78)
    at com.yrd.his.cloud.jyjc.service.impl.JyjcEcgResultServiceImpl.saveOrUpdateUploadEcgResult(JyjcEcgResultServiceImpl.java:162)
```

---

## 确定的根因

### 请求体格式与接口期望的格式完全不匹配

#### 接口期望的请求格式（EcgResultVO 的字段定义）

`EcgResultVO`（`com.yrd.yljk.ggws.cgi.api.xtjc.jyjc.vo`）是一个扁平结构的 VO，期望接收如下格式的 JSON：

```json
{
    "unitId": "机构编号",
    "code": "申请单号",
    "hisId": "门诊病历/住院号",
    "hzName": "患者姓名",
    "hzSex": "患者性别",
    "hzAge": 79,
    "ecgBgUrl": "检查报告浏览地址",
    "ecgBgPath": "检查报告文件(Base64编码)",
    "ecgBgType": "pdf",
    "jcdh": "检查单号",
    "jcks": "检查科室",
    "jcys": "检查医生",
    "jcsj": "2024-09-03 09:18:29",
    "jcdl": "检查导联",
    "zbHr": "83",
    "zbXfl": "心房率",
    "zbXsl": "心室率",
    "zbPr": "144",
    "zbQrs": "83",
    "zbQtQtc": "362/426",
    "zbPQrsT": "64/42/5",
    "zbRv5Sv1": "1.29/0.08",
    "zbXdz": "42",
    "bgTz": "心电图特征",
    "bgZd": "窦性心律；室性早搏",
    "bgKs": "心电图室",
    "bgYs": "王建",
    "bgRq": "2024-09-03 09:19:03"
}
```

#### 实际发送的请求格式

调用方发送的是外部 ECG 平台的原始响应数据，这是一个深度嵌套的复杂结构：

```json
{
    "data": {
        "id": 7151467715662526,
        "reportBizStatus": 90,
        "patient": { "name": "樊良生", "gender": 1, ... },
        "examination": { "examinationOrgId": 1234567899876551, ... },
        "acquisitionFiles": [ ... ],
        "diagnosisResult": { ... }
    },
    "code": 0,
    "msg": "",
    "serverTime": 638609647599748257
}
```

#### Jackson 反序列化的实际结果

当 Spring 的 `@RequestBody` 将上述嵌套 JSON 反序列化到扁平的 `EcgResultVO` 时：

| EcgResultVO 字段 | 请求 JSON 中的对应 | 反序列化结果 |
|---|---|---|
| `unitId` | **不存在** | **`null`** ← 直接原因 |
| `code` | 根级 `"code": 0`（整数） | `"0"` 或 `null`（类型不匹配） |
| `hzName` | 不存在（在 `data.patient.name` 中） | `null` |
| `hzSex` | 不存在（在 `data.patient.gender` 中） | `null` |
| `hzAge` | 不存在（在 `data.patient.age` 中） | `null` |
| `ecgBgUrl` | 不存在 | `null` |
| `jcks` | 不存在 | `null` |
| `jcys` | 不存在 | `null` |
| `bgZd` | 不存在 | `null` |
| 所有其他字段 | 不存在 | `null` |

**结论：EcgResultVO 的几乎所有字段都是 null，不仅仅是 `unitId`。**

#### toEntity() 方法分析

```java
public JyjcEcgResult toEntity() {
    JyjcEcgResult entity = new JyjcEcgResult();
    BeanUtils.copyProperties(this, entity);  // 将 VO 的属性拷贝到实体
    return entity;
}
```

`BeanUtils.copyProperties` 按同名同类型字段拷贝。由于 `EcgResultVO.unitId` 和 `JyjcEcgResult.unitId` 都是 `String` 类型且同名，拷贝逻辑本身没有问题。**问题在于 VO 中 `unitId` 本身就是 `null`**（因为请求 JSON 中没有这个字段），所以拷贝后实体的 `unitId` 自然也是 `null`。

#### 后续报错链路

```
XtjcEcgController.ecgResult(@RequestBody EcgResultVO)
  ↓ Jackson 反序列化：unitId = null（JSON 中无此字段）
EcgResultVO.toEntity()
  ↓ BeanUtils.copyProperties：entity.unitId = null
ecgResultService.saveOrUpdateUploadEcgResult(entity)  // line 162
  ↓
  save(entity)  // line 78
    ↓
    generateCode(entity.getUnitId(), ...)  // unitId = null
      ↓
      getSerialType(null, ...)  // line 125
        ↓
        Assert.notNull(unitId, "unitId must not be null")  // 💥 抛异常
```

---

## 两个 Controller 对比

| 特征 | EcgController | XtjcEcgController |
|---|---|---|
| 路径 | `/ecg/result` | `/xtjc/ecg/result`（本次调用） |
| VO 包路径 | `com.yrd.yljk.ggws.cgi.api.ecg.vo.EcgResultVO` | `com.yrd.yljk.ggws.cgi.api.xtjc.jyjc.vo.EcgResultVO` |
| 转换方式 | `BeanCopyUtils.copy(ecgResultVO, JyjcEcgResult::new)` | `ecgResultVO.toEntity()`（BeanUtils.copyProperties） |
| 权限 | 无特殊权限注解 | `@RequestCgiApiPermissions(V1_0, AuthKeyType.his)` |

两个 Controller 使用的是**不同包**下的 `EcgResultVO`，但根据已确认的源码，`xtjc` 包下的 `EcgResultVO` 也是扁平结构，也有 `unitId` 字段。

---

## 解决方案

### 方案一（推荐，无需改代码）：调用方修改请求体格式

既然无法修改服务端代码，调用方应按照 `EcgResultVO` 期望的扁平结构发送请求。需要在调用前将外部 ECG 平台的嵌套数据转换为 VO 期望的格式。

对照 ECG 平台原始数据 → EcgResultVO 的字段映射：

```
unitId         ← examination.examinationOrgId（"1234567899876551"）
code           ← 需要从业务系统获取申请单号（不是外层的 code=0）
hisId          ← patient.sourceNo 或 patient.admissionId
hzName         ← patient.name（"樊良生"）
hzSex          ← patient.gender（"1" → 需转为系统约定的性别编码）
hzAge          ← patient.age（79）
ecgBgUrl       ← acquisitionFiles[0].metaData.fileUrl
ecgBgType      ← 根据文件格式设置（如 "pdf"）
jcdh           ← 检查单号
jcks           ← examination.examinationDepartment（"心电图室"）
jcys           ← examination.examinationDoctorName（"王建"）
jcsj           ← examination.examinationTime（"2024-09-03 09:18:29"）
zbHr           ← acquisitionFiles[0].measurements.HR（"83"）
zbXfl          ← acquisitionFiles[0].measurements.AtrialRate（"83"）
zbXsl          ← acquisitionFiles[0].measurements.VentricularRate（"83"）
zbPr           ← acquisitionFiles[0].measurements.PR（"144"）
zbQrs          ← acquisitionFiles[0].measurements.QRS（"83"）
zbQtQtc        ← 拼接 QT/QTc（"362/426"）
zbPQrsT        ← 拼接 P/QRS/T axis（"64/42/5"）
zbRv5Sv1       ← 拼接 RV5/SV1（"1.29/0.08"）
zbXdz          ← acquisitionFiles[0].measurements.QRSaxis（"42"）
bgTz           ← diagnosisResult.diagnosis.diagnosisResult.diagnosisResult.diagnosisDescriptionText
bgZd           ← diagnosisResult.diagnosis.diagnosisResult.diagnosisResult.diagnosisText（"窦性心律；室性早搏"）
bgKs           ← examination.examinationDepartment
bgYs           ← diagnosisResult.diagnosis.diagnosisDoctorName（"王建"）
bgRq           ← diagnosisResult.diagnosis.diagnosisTime（"2024-09-03 09:19:03"）
```

正确的请求体示例：

```json
{
    "unitId": "1234567899876551",
    "code": "申请单号（需从业务系统获取）",
    "hisId": "2409030815000015",
    "hzName": "樊良生",
    "hzSex": "1",
    "hzAge": 79,
    "ecgBgUrl": "http://111.235.156.203:8004/v1/files/aecg-cloud-default/report/...",
    "ecgBgType": "7z",
    "jcks": "呼和浩特市太平庄中心卫生院心电图室",
    "jcys": "王建",
    "jcsj": "2024-09-03 09:18:29",
    "zbHr": "83",
    "zbXfl": "83",
    "zbXsl": "83",
    "zbPr": "144",
    "zbQrs": "83",
    "zbQtQtc": "362/426",
    "zbPQrsT": "64/42/5",
    "zbRv5Sv1": "1.29/0.08",
    "zbXdz": "42",
    "bgZd": "窦性心律；室性早搏",
    "bgKs": "呼和浩特市太平庄中心卫生院心电图室",
    "bgYs": "王建",
    "bgRq": "2024-09-03 09:19:03"
}
```

### 方案二（需改代码）：服务端增加数据转换层

如果需要直接接收 ECG 平台的原始格式，需要修改服务端代码：
1. 新建一个接收外部平台格式的 VO 类
2. 在 Controller 或 Service 层增加从外部格式到内部 `JyjcEcgResult` 的转换逻辑

### 方案三（需改代码）：在 Service 层增加 unitId 兜底

在 `JyjcEcgResultServiceImpl.saveOrUpdateUploadEcgResult()` 中根据 `code`（申请单号）查询申请单获取 `unitId`。但这不能解决其他字段全为 null 的问题。

---

## 总结

**根本原因**：调用方发送的请求体格式（ECG 外部平台的嵌套 JSON 响应）与服务端 `EcgResultVO` 期望的扁平 JSON 格式完全不匹配。Jackson 反序列化时，`EcgResultVO` 的几乎所有字段都为 `null`（包括 `unitId`），导致后续生成业务编码时抛出 `unitId must not be null` 异常。

**即使 `unitId` 问题被修复，由于其他字段（`hzName`、`bgZd` 等）也全部为 null，数据也无法正确保存。** 必须按照 `EcgResultVO` 的字段定义重新构造请求体。
