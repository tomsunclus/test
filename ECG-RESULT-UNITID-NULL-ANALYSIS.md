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

## 根因分析

### 1. 请求路由到哪个 Controller

请求 URL 为 `http://192.168.100.69:8280/gw-xtjc/ecg/result`，其中 `gw-xtjc` 是网关前缀，实际路由到服务内部路径为 `/xtjc/ecg/result`。

对应的是 **`XtjcEcgController`**（`@RequestMapping("/xtjc/ecg")`），而 **不是** `EcgController`（`@RequestMapping("/ecg")`）。

```java
// com.yrd.yljk.ggws.cgi.api.xtjc.jyjc.controller.XtjcEcgController
@PostMapping("/result")
public boolean ecgResult(@RequestBody EcgResultVO ecgResultVO) {
    JyjcEcgResult entity = ecgResultVO.toEntity();
    entity.setStatus(JyjcReportCheckStatus.CHECKED);
    entity.setUploadStatus(UploadSign.THIRD_SYSTEM);
    return ecgResultService.saveOrUpdateUploadEcgResult(entity);
}
```

### 2. 调用链路梳理

```
请求进入 XtjcEcgController.ecgResult()
  → EcgResultVO.toEntity()  // VO 转换为 JyjcEcgResult 实体
  → ecgResultService.saveOrUpdateUploadEcgResult(entity)  // line 162
    → save(entity)  // line 78
      → codeGeneratorService.generateCode(...)  // 生成业务编码，需要 unitId
        → basePKGeneratorService.getSerialType(unitId, ...)  // line 125
          → Assert.notNull(unitId, "unitId must not be null")  // 💥 异常抛出
```

### 3. 核心问题：JyjcEcgResult 实体的 unitId 为 null

在 `JyjcEcgResultServiceImpl.save()` 方法第 78 行调用 `generateCode()` 时，需要传入 `unitId`（机构编号）来生成业务流水号。但此时实体对象的 `unitId` 为 `null`。

**unitId 为 null 的原因**：`EcgResultVO.toEntity()` 转换过程中没有正确填充 `unitId` 字段。

### 4. 请求数据结构分析

请求体的结构为外部 ECG 平台的标准响应格式：

```json
{
  "data": {
    "id": 7151467715662526,
    "reportBizStatus": 90,
    "reportStatus": 99003,
    "patient": { ... },
    "examination": {
      "examinationOrgId": 1234567899876551,    // ← 这可能是 unitId 的来源
      "examinationOrgName": "呼和浩特太平庄乡卫生院",
      ...
    },
    ...
  },
  "code": 0,
  "msg": "",
  "serverTime": 638609647599748257
}
```

**关键发现**：请求 JSON 中没有直接名为 `unitId` 的字段。机构信息嵌套在 `data.examination.examinationOrgId` 中。

### 5. 可能的具体原因（按可能性排序）

#### 原因一（最可能）：EcgResultVO 的 toEntity() 方法没有将 examinationOrgId 映射到 unitId

`XtjcEcgController` 使用的 `EcgResultVO`（包路径：`com.yrd.yljk.ggws.cgi.api.xtjc.jyjc.vo.EcgResultVO`）的 `toEntity()` 方法在将 VO 转换为 `JyjcEcgResult` 实体时，可能没有从嵌套的 `examination` 对象中提取 `examinationOrgId` 并映射到实体的 `unitId` 字段。

#### 原因二：请求体结构与 EcgResultVO 不匹配

发送的请求体是整个外部平台的响应（包含 `data`、`code`、`msg`、`serverTime` 外层包装），而 `EcgResultVO` 可能只期望接收内层 `data` 部分的内容。如果 VO 的结构与请求体不匹配，Jackson 反序列化时会导致大量字段为 null，包括最终影响 `unitId` 的字段。

#### 原因三：EcgResultVO 需要显式传入 unitId 字段

`EcgResultVO` 可能设计为需要在请求 JSON 中包含一个顶层的 `unitId` 字段（类似于另一个 `EcgController` 的 `EcgResultVO` 可能有 `unitId` 属性），但发送方没有在 JSON 中提供这个字段。

---

## 对比两个 Controller 的差异

| 特征 | EcgController | XtjcEcgController |
|------|---------------|-------------------|
| 路径 | `/ecg/result` | `/xtjc/ecg/result` |
| VO 包路径 | `com.yrd.yljk.ggws.cgi.api.ecg.vo.EcgResultVO` | `com.yrd.yljk.ggws.cgi.api.xtjc.jyjc.vo.EcgResultVO` |
| 转换方式 | `BeanCopyUtils.copy(ecgResultVO, JyjcEcgResult::new)` | `ecgResultVO.toEntity()` |
| 权限 | 无特殊权限注解 | `@RequestCgiApiPermissions(V1_0, AuthKeyType.his)` |

注意：两个 Controller 使用的是**不同包**下的 `EcgResultVO`，它们的字段定义和转换逻辑可能不同。

---

## 建议修复方向

### 方案一：修复 EcgResultVO.toEntity() 映射逻辑

在 `com.yrd.yljk.ggws.cgi.api.xtjc.jyjc.vo.EcgResultVO` 的 `toEntity()` 方法中，确保从请求数据中提取机构 ID 并设置到 `JyjcEcgResult.unitId`：

```java
public JyjcEcgResult toEntity() {
    JyjcEcgResult entity = new JyjcEcgResult();
    // ... 其他字段映射 ...

    // 需要确保 unitId 被正确设置
    // 可能来源于 examination.examinationOrgId
    if (this.examination != null) {
        entity.setUnitId(String.valueOf(this.examination.getExaminationOrgId()));
    }

    return entity;
}
```

### 方案二：在 Controller 层补充 unitId

如果 `toEntity()` 方法不方便修改，可在 Controller 中补充：

```java
@PostMapping("/result")
public boolean ecgResult(@RequestBody EcgResultVO ecgResultVO) {
    JyjcEcgResult entity = ecgResultVO.toEntity();
    entity.setStatus(JyjcReportCheckStatus.CHECKED);
    entity.setUploadStatus(UploadSign.THIRD_SYSTEM);

    // 补充设置 unitId（如果为空，从 examination 中提取）
    if (entity.getUnitId() == null && ecgResultVO.getExamination() != null) {
        entity.setUnitId(String.valueOf(ecgResultVO.getExamination().getExaminationOrgId()));
    }

    return ecgResultService.saveOrUpdateUploadEcgResult(entity);
}
```

### 方案三：在 Service 层增加 unitId 的兜底逻辑

在 `JyjcEcgResultServiceImpl.saveOrUpdateUploadEcgResult()` 或 `save()` 方法中，在调用 `generateCode()` 之前检查并补充 `unitId`。

---

## 排查建议

1. **确认 EcgResultVO 的完整定义**：查看 `com.yrd.yljk.ggws.cgi.api.xtjc.jyjc.vo.EcgResultVO` 类的源码，确认其字段定义和 `toEntity()` 方法的映射逻辑。
2. **确认请求体结构是否正确**：对比 `EcgResultVO` 的字段定义与实际发送的 JSON 结构，检查是否存在嵌套层级不匹配的问题。
3. **确认 unitId 的数据来源**：与部署方确认 `JyjcEcgResult.unitId` 应该从请求的哪个字段映射。
4. **添加日志**：如可修改代码，在 `toEntity()` 方法和 `saveOrUpdateUploadEcgResult()` 方法入口处打印实体对象的关键字段值，确认数据流转情况。

---

## 总结

**根本原因**：请求通过网关 `/gw-xtjc/ecg/result` 路由到 `XtjcEcgController`，该 Controller 调用 `EcgResultVO.toEntity()` 将请求体转换为 `JyjcEcgResult` 实体对象。在转换过程中，`unitId` 字段没有被正确赋值（值为 null）。随后在保存时，系统需要根据 `unitId` 生成业务编码，因此抛出 `unitId must not be null` 异常。

最可能的原因是 `EcgResultVO.toEntity()` 的映射逻辑中缺少对 `unitId` 的映射，或者请求 JSON 的数据结构与 `EcgResultVO` 的字段定义不匹配（例如外层包装了 `data`/`code`/`msg` 层级）。
