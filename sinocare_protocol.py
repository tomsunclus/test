#!/usr/bin/env python3
"""
三诺 iPOCT 仪器数据简单协议 - 全面测试帧生成器
已确认: CRC16-MODBUS, 帧格式: SN(2)+Length(2)+OpType(2)+Data(N)+CRC(2)

分析:
- P1-P5 (全部 POST + url/fhir JSON 变体) 均 E56-D
- CRC16-MODBUS 已验证正确
- 说明问题可能在: 操作类型不是POST, 或 JSON结构不是url/fhir格式, 或响应帧格式本身不同
"""
import struct
import json


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def build_frame(operation_type: int, data_content: bytes) -> bytes:
    """标准帧: SN + length + op_type + data + CRC"""
    op_bytes = struct.pack(">H", operation_type)
    crc_input = op_bytes + data_content
    crc = crc16_modbus(crc_input)
    crc_bytes = struct.pack("<H", crc)
    frame_length = 2 + len(data_content) + 2  # op + data + crc
    length_bytes = struct.pack(">H", frame_length)
    return b'\x53\x4E' + length_bytes + op_bytes + data_content + crc_bytes


def build_frame_no_optype(data_content: bytes) -> bytes:
    """变体帧(无操作类型): SN + length + data + CRC"""
    crc = crc16_modbus(data_content)
    crc_bytes = struct.pack("<H", crc)
    frame_length = len(data_content) + 2  # data + crc
    length_bytes = struct.pack(">H", frame_length)
    return b'\x53\x4E' + length_bytes + data_content + crc_bytes


def build_frame_crc_all(operation_type: int, data_content: bytes) -> bytes:
    """变体帧(CRC覆盖全部): SN + length + op + data + CRC, CRC计算包含header+length"""
    op_bytes = struct.pack(">H", operation_type)
    frame_length = 2 + len(data_content) + 2
    length_bytes = struct.pack(">H", frame_length)
    header = b'\x53\x4E'
    crc_input = header + length_bytes + op_bytes + data_content
    crc = crc16_modbus(crc_input)
    crc_bytes = struct.pack("<H", crc)
    return header + length_bytes + op_bytes + data_content + crc_bytes


def fmt(frame: bytes) -> str:
    return frame.hex(' ').upper()


def print_frame(label: str, frame: bytes, json_str: str = ""):
    print(f"\n  [{label}]")
    if json_str:
        print(f"  数据: {json_str}")
    print(f"  长度: {len(frame)}字节")
    print(f"  HEX: {fmt(frame)}")


def gen(op: int, data: dict, label: str):
    """生成标准帧并打印"""
    js = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    frame = build_frame(op, js.encode('utf-8'))
    print_frame(label, frame, js)
    return frame


def gen_raw(op: int, raw_bytes: bytes, label: str, desc: str = ""):
    """用原始字节生成帧"""
    frame = build_frame(op, raw_bytes)
    print_frame(label, frame, desc or repr(raw_bytes))
    return frame


if __name__ == "__main__":
    OP_GET = 0
    OP_POST = 1
    OP_PUT = 2
    OP_DEL = 3

    PAT = "https://example.com/path/Patient"
    OBS = "https://example.com/path/Observation"

    print("=" * 72)
    print("  三诺 iPOCT 协议 - 全面排查响应帧生成器")
    print("  已知: CRC16-MODBUS ✓, POST+url/fhir 全部 E56-D")
    print("=" * 72)

    # =========================================================================
    print("\n\n" + "█" * 72)
    print("  第1组: PUT (0x02) 操作类型 - 最高优先级")
    print("  理由: POST是仪器→服务器, PUT可能是服务器→仪器的确认")
    print("█" * 72)

    gen(OP_PUT, {"fhir":{"id":"1"},"url":PAT}, "PUT-1: fhir{id}+url")
    gen(OP_PUT, {"url":PAT,"fhir":{"id":"1"}}, "PUT-2: url+fhir{id}")
    gen(OP_PUT, {"url":PAT,"fhir":{}}, "PUT-3: url+fhir{}")
    gen(OP_PUT, {"url":PAT}, "PUT-4: 仅url")
    gen(OP_PUT, {"fhir":{}}, "PUT-5: 仅fhir{}")

    # =========================================================================
    print("\n\n" + "█" * 72)
    print("  第2组: GET (0x00) 操作类型")
    print("  理由: GET可能表示'数据已获取/确认收到'")
    print("█" * 72)

    gen(OP_GET, {"fhir":{"id":"1"},"url":PAT}, "GET-1: fhir{id}+url")
    gen(OP_GET, {"url":PAT,"fhir":{}}, "GET-2: url+fhir{}")
    gen(OP_GET, {"url":PAT}, "GET-3: 仅url")
    gen(OP_GET, {}, "GET-4: 空JSON{}")

    # =========================================================================
    print("\n\n" + "█" * 72)
    print("  第3组: 空数据帧 (无JSON内容, 只有op_type+CRC)")
    print("  理由: 最简ACK,某些协议响应只需要帧头确认即可")
    print("█" * 72)

    for op_name, op_val in [("POST", 1), ("PUT", 2), ("GET", 0), ("DELETE", 3)]:
        frame = build_frame(op_val, b'')
        print_frame(f"EMPTY-{op_name}: 操作类型={op_val},无数据内容", frame, "(空)")

    # =========================================================================
    print("\n\n" + "█" * 72)
    print("  第4组: 非标准操作类型")
    print("  理由: 心跳用0x08,可能存在其他未文档化的操作码")
    print("█" * 72)

    for op_val in [4, 5, 6, 7, 8, 9, 10, 0x0A, 0x0B, 0x0C, 0x10, 0xFF]:
        if op_val in (0x0A, 0x0B, 0x0C) and op_val in (10,):
            continue
        js_data = {"fhir":{"id":"1"},"url":PAT}
        js = json.dumps(js_data, ensure_ascii=False, separators=(',', ':'))
        frame = build_frame(op_val, js.encode('utf-8'))
        print_frame(f"OP-{op_val:02X}: 操作类型=0x{op_val:04X}", frame, js)

    # =========================================================================
    print("\n\n" + "█" * 72)
    print("  第5组: 不同JSON结构(非url/fhir格式)")
    print("  理由: 服务器响应可能使用完全不同的JSON字段")
    print("█" * 72)

    # 使用code/status/result等字段
    gen(OP_POST, {"code":0}, "JSON-1: POST+{code:0}")
    gen(OP_POST, {"code":200}, "JSON-2: POST+{code:200}")
    gen(OP_POST, {"code":"200"}, "JSON-3: POST+{code:'200'}")
    gen(OP_POST, {"result":0}, "JSON-4: POST+{result:0}")
    gen(OP_POST, {"result":"ok"}, "JSON-5: POST+{result:'ok'}")
    gen(OP_POST, {"status":0}, "JSON-6: POST+{status:0}")
    gen(OP_POST, {"status":"ok"}, "JSON-7: POST+{status:'ok'}")
    gen(OP_POST, {"success":True}, "JSON-8: POST+{success:true}")
    gen(OP_POST, {}, "JSON-9: POST+空JSON{}")
    gen(OP_PUT, {"code":0}, "JSON-10: PUT+{code:0}")
    gen(OP_PUT, {"result":0}, "JSON-11: PUT+{result:0}")
    gen(OP_PUT, {"status":0}, "JSON-12: PUT+{status:0}")
    gen(OP_GET, {"code":0}, "JSON-13: GET+{code:0}")

    # 带parameters字段(协议文档提到parameters是可选的操作参数)
    gen(OP_POST, {"url":PAT,"parameters":{"status":0}}, "JSON-14: POST+url+parameters")
    gen(OP_POST, {"url":PAT,"parameters":{},"fhir":{}}, "JSON-15: POST+url+parameters+fhir")

    # FHIR OperationOutcome模式
    gen(OP_POST, {"url":PAT,"fhir":{"resourceType":"OperationOutcome","issue":[{"severity":"information","code":"informational"}]}},
        "JSON-16: POST+FHIR OperationOutcome")

    # 带extension字段
    gen(OP_POST, {"url":PAT,"fhir":{},"extension":{"position":"1"}},
        "JSON-17: POST+url+fhir+extension{position}")

    # URL末尾加ID (FHIR模式: POST /Patient → Response Location /Patient/1)
    gen(OP_POST, {"fhir":{"id":"1"},"url":PAT+"/1"}, "JSON-18: POST+url含ID(/Patient/1)")

    # =========================================================================
    print("\n\n" + "█" * 72)
    print("  第6组: JSON带空格格式(非紧凑)")
    print("  理由: 仪器可能对JSON格式敏感,期望标准格式带空格")
    print("█" * 72)

    # Python json.dumps默认有空格: {"key": "value"}
    for sep_name, seps in [("标准", (', ', ': ')), ("冒号后空格", (',', ': '))]:
        data = {"fhir": {"id": "1"}, "url": PAT}
        js = json.dumps(data, ensure_ascii=False, separators=seps)
        frame = build_frame(OP_POST, js.encode('utf-8'))
        print_frame(f"FMT-POST-{sep_name}: POST", frame, js)

        frame2 = build_frame(OP_PUT, js.encode('utf-8'))
        print_frame(f"FMT-PUT-{sep_name}: PUT", frame2, js)

    # =========================================================================
    print("\n\n" + "█" * 72)
    print("  第7组: 原始字节/特殊响应")
    print("  理由: 某些协议用单个字节或简单字符串应答")
    print("█" * 72)

    gen_raw(OP_POST, b'OK', "RAW-1: POST+'OK'", "OK")
    gen_raw(OP_POST, b'ok', "RAW-2: POST+'ok'", "ok")
    gen_raw(OP_POST, b'ACK', "RAW-3: POST+'ACK'", "ACK")
    gen_raw(OP_POST, b'0', "RAW-4: POST+'0'", "0")
    gen_raw(OP_POST, b'1', "RAW-5: POST+'1'", "1")
    gen_raw(OP_POST, b'200', "RAW-6: POST+'200'", "200")
    gen_raw(OP_POST, b'\x00', "RAW-7: POST+0x00", "单字节0x00")
    gen_raw(OP_POST, b'\x06', "RAW-8: POST+ACK(0x06)", "ACK控制字符0x06")
    gen_raw(OP_PUT, b'OK', "RAW-9: PUT+'OK'", "OK")
    gen_raw(OP_GET, b'OK', "RAW-10: GET+'OK'", "OK")

    # =========================================================================
    print("\n\n" + "█" * 72)
    print("  第8组: 不同CRC计算范围(如CRC覆盖整个帧)")
    print("  理由: 服务器响应的CRC计算范围可能与仪器发送不同")
    print("█" * 72)

    js_data = {"fhir":{"id":"1"},"url":PAT}
    js = json.dumps(js_data, ensure_ascii=False, separators=(',', ':'))
    js_bytes = js.encode('utf-8')

    frame_alt = build_frame_crc_all(OP_POST, js_bytes)
    print_frame("CRC-ALT-1: POST, CRC覆盖SN+length+op+data", frame_alt, js)

    frame_alt2 = build_frame_crc_all(OP_PUT, js_bytes)
    print_frame("CRC-ALT-2: PUT, CRC覆盖SN+length+op+data", frame_alt2, js)

    # CRC只覆盖data(不含op_type)
    crc_data_only = crc16_modbus(js_bytes)
    op_bytes = struct.pack(">H", OP_POST)
    crc_bytes = struct.pack("<H", crc_data_only)
    frame_length = 2 + len(js_bytes) + 2
    length_bytes = struct.pack(">H", frame_length)
    frame_alt3 = b'\x53\x4E' + length_bytes + op_bytes + js_bytes + crc_bytes
    print_frame("CRC-ALT-3: POST, CRC仅覆盖data(不含op)", frame_alt3, js)

    # =========================================================================
    print("\n\n" + "█" * 72)
    print("  第9组: 无SN帧头的原始响应")
    print("  理由: 服务器响应可能不需要帧包装")
    print("█" * 72)

    raw_responses = [
        (b'\x06', "ACK字符(0x06)"),
        (b'\x15', "NAK字符(0x15)"),
        (b'OK\r\n', "OK+回车换行"),
        (b'{"code":0}', "纯JSON {code:0}"),
        (b'{"result":0}', "纯JSON {result:0}"),
        (b'{"status":"ok"}', "纯JSON {status:ok}"),
        (json.dumps({"fhir":{"id":"1"},"url":PAT}, separators=(',',':')).encode(), "纯JSON fhir+url(无帧头)"),
    ]
    for raw, desc in raw_responses:
        print(f"\n  [NOFRAME-{desc}]")
        print(f"  HEX: {raw.hex(' ').upper()}")
        print(f"  ASCII: {raw.decode('utf-8', errors='replace')}")

    # =========================================================================
    print("\n\n" + "█" * 72)
    print("  第10组: POST + 与Observation URL的响应 ")
    print("  理由: 也许服务器回复时应告知仪器接下来发往哪个URL")
    print("█" * 72)

    gen(OP_POST, {"url":OBS,"fhir":{}}, "OBS-1: POST+Observation url+fhir{}")
    gen(OP_POST, {"url":OBS,"fhir":{"id":"1"}}, "OBS-2: POST+Observation url+fhir{id}")
    gen(OP_GET, {"url":OBS,"fhir":{}}, "OBS-3: GET+Observation url+fhir{}")

    # =========================================================================
    print("\n\n" + "=" * 72)
    print("  排查优先级建议")
    print("=" * 72)
    print("""
已排除: POST(0x01) + url/fhir JSON变体 → 全部 E56-D

优先尝试顺序:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 第1组 PUT (PUT-1 ~ PUT-5) → 不同操作类型
2. 第2组 GET (GET-1 ~ GET-4) → 不同操作类型
3. 第3组 空数据帧 (EMPTY-POST/PUT/GET) → 最简ACK
4. 第5组 不同JSON (JSON-1 ~ JSON-13) → 不同字段名
5. 第6组 带空格JSON (FMT-*) → 格式差异
6. 第9组 无帧头响应 (NOFRAME-*) → 完全不同的响应模式
7. 第4组 非标操作类型 (OP-04 ~ OP-FF) → 隐藏操作码
8. 第7组 原始字节 (RAW-*) → 特殊编码
9. 第8组 不同CRC范围 (CRC-ALT-*) → CRC计算方式不同

提示:
- 在NetAssist中必须选择HEX发送模式
- 第9组(无帧头)的数据可直接粘贴到发送框
- 每次测试一个方案, 记录仪器反应(E56-D/其他错误/成功)
- 如果某个操作类型不再报E56-D而报其他错误, 说明操作类型对了

特别注意:
- 如果 EMPTY-POST 不报 E56-D → 操作类型对, 只需要调整数据内容
- 如果 PUT/GET 某个不报 E56-D → 操作类型找到了
- 如果全部都 E56-D → 可能响应帧格式本身就不一样
""")
