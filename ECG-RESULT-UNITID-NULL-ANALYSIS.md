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
    at BasePKGeneratorServiceImpl.getSerialType(BasePKGeneratorServiceImpl.java:125)
    at CodeGeneratorServiceImpl.generateCode(CodeGeneratorServiceImpl.java:47)
    at JyjcEcgResultServiceImpl.save(JyjcEcgResultServiceImpl.java:78)
    at JyjcEcgResultServiceImpl.saveOrUpdateUploadEcgResult(JyjcEcgResultServiceImpl.java:162)
```

**重要背景：该接口之前一直正常运行，最近突然出现此问题。**

---

## 深入分析

### 关键线索：saveOrUpdate 的 save 分支被触发

方法名为 `saveOrUpdateUploadEcgResult`，说明这是一个"保存或更新"逻辑：

- **Update 分支**：找到已有记录 → 更新字段 → 不需要生成新编码 → **不需要 unitId**
- **Save 分支**：没找到已有记录 → 新增记录 → 需要调用 `generateCode()` → **需要 unitId**

从堆栈可以看到调用链是 `saveOrUpdateUploadEcgResult(line 162) → save(line 78) → generateCode()`，说明走的是 **save（新增）分支**。

### 可能的根因场景（按可能性排序）

#### 场景一：请求体格式与 EcgResultVO 不匹配（调用方数据格式问题）

`EcgResultVO` 是一个**扁平结构**，期望接收的 JSON 字段：

```json
{
    "unitId": "机构编号",
    "code": "申请单号",
    "hzName": "患者姓名",
    "jcys": "检查医生",
    "bgZd": "诊断结论",
    ...
}
```

而发送的 JSON 是 ECG 外部平台的**深度嵌套**结构（`data.patient.name`、`data.examination.examinationOrgId` 等）。Jackson 反序列化时，VO 的几乎所有字段都会是 null（包括 `unitId`、`code`）。

**如果之前也是这个格式正常工作**，说明两种可能：
1. `gw-xtjc` 网关层有做数据转换（把嵌套格式转为扁平格式后再转发给实际服务），网关配置或代码近期被修改了
2. 之前不是直接发这个格式，中间有其他系统做了转换

#### 场景二：saveOrUpdate 匹配逻辑变化导致走了 save 分支

`saveOrUpdateUploadEcgResult` 内部逻辑大概率是这样的：

```
1. 根据某个条件（如 code 申请单号）查找已有记录
2. 如果找到 → 走 update 分支（不需要 generateCode）
3. 如果没找到 → 走 save 分支（需要 generateCode，需要 unitId）
```

以前可能因为以下原因走的是 update 分支：
- 申请单已经通过正常流程创建（ecgReq 接口先查询申请单，系统中已有 unitId 的记录）
- 报告回传时能匹配到已有记录 → update → 不触发 generateCode

**现在可能的变化**：
- 匹配条件变了（代码改动）
- 申请单数据不存在了（数据库迁移/清理）
- 传入的匹配字段值变了（如 code 字段值不再能匹配到已有记录）

#### 场景三：代码被改动，generateCode 或 save 逻辑新增了 unitId 校验

`BasePKGeneratorServiceImpl.getSerialType(line 125)` 中的 `Assert.notNull(unitId)` 可能是最近新增的校验逻辑。之前可能没有这个校验，unitId 为 null 不会报错。

#### 场景四：第三方发送内容变化

虽然可能性较小，但不能排除。如果第三方之前发送的格式中包含了必要的字段（如之前有 `unitId` 字段），最近改版后去掉了，也会导致此问题。

---

## 不改代码的调试方案

### 方案一：使用 Arthas 诊断（强烈推荐）

[Arthas](https://arthas.aliyun.com/) 是阿里开源的 Java 诊断工具，可以在**不修改代码、不重启服务**的情况下，实时观察方法调用参数和返回值。

#### 安装（在服务器 192.168.100.69 上执行）

```bash
# 下载 arthas
curl -O https://arthas.aliyun.com/arthas-boot.jar

# 启动 arthas，attach 到目标 Java 进程
java -jar arthas-boot.jar
# 选择对应的 Java 进程
```

#### 诊断命令

**1) 观察 Controller 接收到的 EcgResultVO 内容**

```bash
watch com.yrd.yljk.ggws.cgi.api.xtjc.jyjc.controller.XtjcEcgController ecgResult '{params[0], params[0].unitId, params[0].code, params[0].hzName}' -x 3
```

这会打印出 Controller 实际接收到的 VO 对象，可以看到 `unitId`、`code` 等字段的值。

**2) 观察 toEntity() 转换后实体的内容**

```bash
watch com.yrd.yljk.ggws.cgi.api.xtjc.jyjc.vo.EcgResultVO toEntity '{returnObj, returnObj.unitId, returnObj.code}' -x 3
```

**3) 观察 saveOrUpdateUploadEcgResult 的入参和内部走向**

```bash
watch com.yrd.his.cloud.jyjc.service.impl.JyjcEcgResultServiceImpl saveOrUpdateUploadEcgResult '{params[0].unitId, params[0].code, params[0].hzName}' -x 3
```

**4) 追踪完整调用链路**

```bash
trace com.yrd.his.cloud.jyjc.service.impl.JyjcEcgResultServiceImpl saveOrUpdateUploadEcgResult
```

这会显示 `saveOrUpdateUploadEcgResult` 内部调用了哪些方法，可以明确是直接走了 save 还是经过了 update 判断后走的 save。

**5) 反编译查看 saveOrUpdateUploadEcgResult 实际代码**

```bash
jad com.yrd.his.cloud.jyjc.service.impl.JyjcEcgResultServiceImpl saveOrUpdateUploadEcgResult
```

```bash
jad com.yrd.his.cloud.jyjc.service.impl.JyjcEcgResultServiceImpl save
```

这会反编译运行中的实际字节码，可以看到 `saveOrUpdateUploadEcgResult` 和 `save` 方法的完整逻辑，包括它怎么判断是 save 还是 update。

### 方案二：抓包验证网关是否做了数据转换

如果怀疑 `gw-xtjc` 网关在中间做了数据格式转换，可以在服务器上抓包看看网关转发给后端服务时的实际请求体：

```bash
# 在服务器上抓取内部端口的流量（需要知道后端服务实际端口）
sudo tcpdump -i lo -A -s 0 'tcp port <后端服务端口> and (((ip[2:2] - ((ip[0]&0xf)<<2)) - ((tcp[12]&0xf0)>>2)) != 0)' | strings
```

### 方案三：Postman Console 查看实际发送内容

在 Postman 中：
1. 点击底部的 **Console** 按钮
2. 发送请求
3. Console 中会显示完整的 HTTP 请求报文（headers + body）

这可以确认 Postman 实际发送的内容是否与预期一致。但这只能验证 Postman → 网关 的内容，无法看到网关 → 后端服务 的内容。

### 方案四：查看网关/Nginx 日志

如果 `gw-xtjc` 网关有请求日志记录，查看日志可以看到转发细节：

```bash
# 查看网关日志
tail -f /path/to/gateway/logs/access.log

# 查看是否有请求体记录
grep "ecg/result" /path/to/gateway/logs/*.log
```

---

## 建议的排查步骤

### 第一步（最重要）：用 Arthas 反编译 saveOrUpdateUploadEcgResult

```bash
jad com.yrd.his.cloud.jyjc.service.impl.JyjcEcgResultServiceImpl saveOrUpdateUploadEcgResult
jad com.yrd.his.cloud.jyjc.service.impl.JyjcEcgResultServiceImpl save
```

这能直接看到：
- `saveOrUpdateUploadEcgResult` 方法内部用什么条件判断是 save 还是 update
- `save` 方法第 78 行调用 `generateCode` 时传的 unitId 来自哪里
- 是否有最近新增的代码逻辑

### 第二步：用 Arthas watch 观察实际数据

```bash
# 观察 Controller 收到的 VO
watch com.yrd.yljk.ggws.cgi.api.xtjc.jyjc.controller.XtjcEcgController ecgResult '{params[0]}' -x 3

# 观察 service 收到的 entity
watch com.yrd.his.cloud.jyjc.service.impl.JyjcEcgResultServiceImpl saveOrUpdateUploadEcgResult '{params[0]}' -x 3
```

然后用 Postman 再发一次请求，Arthas 会实时打印出 Controller 和 Service 实际接收到的对象内容，一目了然。

### 第三步：对比历史

如果能访问代码仓库，查看最近的提交历史：

```bash
git log --oneline --since="2周前" -- "**/JyjcEcgResultServiceImpl.java" "**/EcgResultVO.java" "**/XtjcEcgController.java" "**/BasePKGeneratorServiceImpl.java"
```

---

## 总结

| 排查项 | 方法 | 目的 |
|--------|------|------|
| Controller 收到什么数据 | Arthas watch | 确认 unitId 到底是什么值 |
| saveOrUpdate 为什么走了 save | Arthas jad 反编译 | 看判断逻辑和匹配条件 |
| 网关是否做数据转换 | tcpdump / 网关日志 | 确认请求到达服务时的实际格式 |
| 代码是否被改动 | git log / Arthas jad | 对比当前运行代码与预期 |
| Postman 发了什么 | Postman Console | 确认发送内容正确性 |

**最推荐的做法**：直接在服务器上用 Arthas attach 到 Java 进程，执行 `jad` 和 `watch` 命令，无需改代码、无需重启，就能看到完整的运行时数据和实际代码逻辑。
