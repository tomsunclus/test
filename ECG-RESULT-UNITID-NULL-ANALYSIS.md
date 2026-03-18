# ECG Result 接口返回 -1 问题分析：unitId must not be null

## 问题现象

调用 `POST http://192.168.100.69:8280/gw-xtjc/ecg/result` 接口，返回：

```json
{"code": -1, "msg": "failure", "data": null}
```

Tomcat 日志报错：

```
java.lang.IllegalArgumentException: unitId must not be null
    at BasePKGeneratorServiceImpl.getSerialType(BasePKGeneratorServiceImpl.java:125)
    at CodeGeneratorServiceImpl.generateCode(CodeGeneratorServiceImpl.java:47)
    at JyjcEcgResultServiceImpl.save(JyjcEcgResultServiceImpl.java:78)
    at JyjcEcgResultServiceImpl.saveOrUpdateUploadEcgResult(JyjcEcgResultServiceImpl.java:162)
```

**重要背景：该接口之前一直正常运行，最近突然出现此问题。**

---

## Postman Console 确认的事实

通过 Postman Console 截取的完整 HTTP 报文已确认以下事实：

### 事实一：请求体是嵌套的 ECG 平台格式

```
POST /gw-xtjc/ecg/result HTTP/1.1
Content-Type: application/json
Content-Length: 6855

{"data":{"id":7151467715662526,...},"code":0,"msg":"","serverTime":638609647599748257}
```

请求 JSON 的**顶层字段**为 `data`、`code`（整数 0）、`msg`、`serverTime`。

### 事实二：EcgResultVO 期望的是扁平格式

```java
@Data
public class EcgResultVO {
    private String unitId;    // 期望顶层有 "unitId"
    private String code;      // 期望顶层有 "code"（字符串，申请单号）
    private String hzName;    // 期望顶层有 "hzName"
    // ...
}
```

### 事实三：Jackson 反序列化结果

| 请求 JSON 顶层字段 | EcgResultVO 字段 | 匹配结果 |
|---|---|---|
| `"data": {...}` | 无 data 字段 | 被忽略 |
| `"code": 0`（整数） | `String code` | 可能变为 `"0"` 或 null |
| `"msg": ""` | 无 msg 字段 | 被忽略 |
| `"serverTime": 638...` | 无 serverTime 字段 | 被忽略 |
| — | `unitId` | **null**（请求中不存在） |
| — | `hzName` | null（请求中不存在） |
| — | 其他所有字段 | null（请求中不存在） |

**结论：当前发送的嵌套格式与 EcgResultVO 的扁平结构完全不匹配，反序列化后几乎所有字段为 null。**

---

## 根因推断

既然接口之前是正常运行的，那么必然是以下其中一种情况发生了变化：

### 可能性一（最可能）：第三方发送的数据格式变了

之前第三方 ECG 平台发送的是 EcgResultVO 所期望的扁平格式：

```json
{
    "unitId": "1234567899876551",
    "code": "ECG20240903001",
    "hzName": "樊良生",
    "bgZd": "窦性心律；室性早搏",
    ...
}
```

近期第三方做了系统升级或接口改版，改为了当前这种嵌套格式（带 `data`/`code`/`msg`/`serverTime` 包装层）。你用 Postman 复制的就是第三方新格式的数据，所以也复现了同样的错误。

**验证方法**：查看服务器上更早之前成功请求的日志，对比请求体格式是否一致。

### 可能性二：服务端代码被升级，EcgResultVO 不再适配

有人更新了服务端代码，但新版 `EcgResultVO` 仍然是扁平结构，没有适配第三方的新数据格式。

或者更可能的场景：之前用的是**另一个版本**的 `EcgResultVO`（可能是能解析嵌套格式的版本），代码回滚或重新部署后换成了当前的扁平版本。

**验证方法**：用 Arthas 反编译当前运行的 EcgResultVO，确认实际结构。

### 可能性三：网关 gw-xtjc 之前有数据转换，现在没了

网关 `gw-xtjc` 之前可能有一层拦截器/过滤器，将嵌套的 ECG 平台格式转换为扁平的 EcgResultVO 格式后再转发给后端服务。近期网关配置或代码变更导致这个转换层失效了。

**验证方法**：检查网关配置或代码的变更历史。

---

## 不改代码的排查方案

### 方案一：Arthas 无侵入诊断（推荐）

在服务器 192.168.100.69 上执行：

```bash
curl -O https://arthas.aliyun.com/arthas-boot.jar
java -jar arthas-boot.jar
```

#### 1) 反编译确认当前运行的 EcgResultVO 结构

```bash
jad com.yrd.yljk.ggws.cgi.api.xtjc.jyjc.vo.EcgResultVO
```

确认运行中的 VO 是否就是我们看到的扁平结构。如果不是，说明代码有变化。

#### 2) 反编译 saveOrUpdateUploadEcgResult 的完整逻辑

```bash
jad com.yrd.his.cloud.jyjc.service.impl.JyjcEcgResultServiceImpl saveOrUpdateUploadEcgResult
jad com.yrd.his.cloud.jyjc.service.impl.JyjcEcgResultServiceImpl save
```

#### 3) watch 观察 Controller 实际接收到的 VO 数据

```bash
watch com.yrd.yljk.ggws.cgi.api.xtjc.jyjc.controller.XtjcEcgController ecgResult '{params[0].unitId, params[0].code, params[0].hzName}' -x 3
```

然后用 Postman 再发一次请求，Arthas 会实时显示 Controller 收到的 VO 各字段的值。

### 方案二：用正确格式的请求体测试

如果只是为了验证接口是否可用，可以用 Postman 按 EcgResultVO 期望的扁平格式重新构造请求体发送测试：

```json
{
    "unitId": "1234567899876551",
    "code": "测试申请单号",
    "hisId": "2409030815000015",
    "hzName": "樊良生",
    "hzSex": "1",
    "hzAge": 79,
    "ecgBgUrl": "http://111.235.156.203:8004/v1/files/aecg-cloud-default/report/1234567899876551/1/2/1/2024-09-03/7151467715662526/7151474324624094.7z",
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

> 注意：`code`（申请单号）需要填写系统中真实存在的申请单号，否则可能走 save 分支，但至少不会报 `unitId must not be null` 的错误。

如果这个格式能通过，就说明问题确实是第三方数据格式变了。

### 方案三：查看历史成功请求的日志

```bash
# 在服务器上查找之前成功的请求日志
grep -B5 "ecg/result" /path/to/tomcat/logs/catalina.out | head -100

# 或查看更早的日志文件
zgrep "ecg/result" /path/to/tomcat/logs/catalina.*.gz
```

如果日志中记录了历史请求体，就能直接对比之前成功时发送的是什么格式。

---

## 总结

| 已确认的事实 | 说明 |
|---|---|
| Postman 发送的请求体 | 嵌套的 ECG 平台格式（顶层为 `data`/`code`/`msg`/`serverTime`） |
| EcgResultVO 期望的格式 | 扁平结构（顶层为 `unitId`/`code`/`hzName` 等直接字段） |
| 两者是否匹配 | **完全不匹配**，反序列化后 VO 几乎所有字段为 null |
| 报错直接原因 | `unitId` 为 null，`generateCode()` 校验失败 |

| 需要进一步确认的问题 | 排查方法 |
|---|---|
| 第三方之前发的是什么格式？ | 查历史成功日志 / 问第三方 |
| 网关有没有做数据转换？ | Arthas watch Controller 入参 / 查网关配置 |
| 当前运行的代码是否和源码一致？ | Arthas jad 反编译对比 |

**最快的验证方式**：用上面"方案二"的扁平格式 JSON 通过 Postman 发一次请求。如果成功了，就证明是数据格式问题；如果还是失败，就说明服务端逻辑也有变化，需要用 Arthas 进一步排查。
