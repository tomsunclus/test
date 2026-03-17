#!/usr/bin/env python3
"""
三诺 iPOCT 仪器数据简单协议 - 帧分析与响应生成工具
"""
import struct
import json


def crc16_modbus(data: bytes) -> int:
    """CRC16-MODBUS: polynomial 0xA001, initial 0xFFFF"""
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
    """构建完整的协议帧"""
    op_bytes = struct.pack(">H", operation_type)
    crc_input = op_bytes + data_content
    crc = crc16_modbus(crc_input)
    crc_bytes = struct.pack("<H", crc)  # 低字节在前
    frame_length = len(op_bytes) + len(data_content) + len(crc_bytes)
    length_bytes = struct.pack(">H", frame_length)
    header = b'\x53\x4E'
    return header + length_bytes + op_bytes + data_content + crc_bytes


def parse_frame(hex_str: str):
    """解析一个协议帧"""
    hex_clean = hex_str.replace(" ", "").replace("\n", "")
    data = bytes.fromhex(hex_clean)

    print(f"\n{'='*70}")
    print(f"原始帧 ({len(data)} 字节)")
    print(f"{'='*70}")

    if len(data) < 8:
        print("错误: 帧长度不足8字节")
        return None

    header = data[0:2]
    if header != b'\x53\x4E':
        print(f"错误: 帧头不正确! 期望 53 4E, 实际 {header.hex(' ').upper()}")
        return None
    print(f"  帧头: 53 4E ('SN') ✓")

    frame_length = struct.unpack(">H", data[2:4])[0]
    actual_payload = len(data) - 4
    match_str = "✓" if actual_payload == frame_length else f"✗ 实际={actual_payload}"
    print(f"  帧长度: 0x{data[2:4].hex().upper()} = {frame_length} {match_str}")

    op_type = struct.unpack(">H", data[4:6])[0]
    op_names = {0: "GET", 1: "POST/Create", 2: "PUT/Update", 3: "DELETE", 8: "心跳"}
    print(f"  操作类型: 0x{data[4:6].hex().upper()} = {op_type} ({op_names.get(op_type, '未知')})")

    crc_received = struct.unpack("<H", data[-2:])[0]
    crc_scope = data[4:-2]
    crc_calc = crc16_modbus(crc_scope)
    crc_match = "✓" if crc_calc == crc_received else f"✗ 计算值=0x{crc_calc:04X}"
    print(f"  CRC16-MODBUS: 0x{crc_received:04X} {crc_match}")

    data_content = data[6:-2]
    try:
        json_str = data_content.decode('utf-8')
        try:
            parsed = json.loads(json_str)
            print(f"  JSON: {json.dumps(parsed, ensure_ascii=False)}")
        except json.JSONDecodeError:
            print(f"  文本: {json_str}")
    except UnicodeDecodeError:
        print(f"  HEX: {data_content.hex(' ').upper()}")

    return {
        "op_type": op_type,
        "data_content": data_content,
        "crc_ok": crc_calc == crc_received,
    }


def generate_frame(op_type: int, json_data: dict, label: str):
    """生成帧并输出可复制的HEX字符串"""
    json_str = json.dumps(json_data, ensure_ascii=False, separators=(',', ':'))
    data_bytes = json_str.encode('utf-8')
    frame = build_frame(op_type, data_bytes)

    op_names = {0: "GET", 1: "POST", 2: "PUT", 3: "DELETE"}
    print(f"\n{'─'*70}")
    print(f"  方案 {label}")
    print(f"  操作类型: {op_type} ({op_names.get(op_type, '?')})")
    print(f"  JSON: {json_str}")
    print(f"  帧长: {len(frame)} 字节")
    print(f"  ▼ 复制以下HEX到NetAssist发送框 ▼")
    print(f"  {frame.hex(' ').upper()}")
    return frame


if __name__ == "__main__":
    print("=" * 70)
    print("  三诺 iPOCT 简单协议 - 服务器响应帧生成工具")
    print("  CRC算法: CRC16-MODBUS (已验证)")
    print("=" * 70)

    # ── 验证CRC算法 ──────────────────────────────────────────
    print("\n\n▶ 验证CRC16算法（使用第二次发送的帧，此帧CRC已知正确）")
    parse_frame(
        "53 4E 00 C3 00 01 7B 22 66 68 69 72 22 3A 7B 22 "
        "55 73 65 72 49 64 22 3A 22 22 2C 22 61 67 65 22 "
        "3A 22 37 30 22 2C 22 61 67 65 4D 6F 6E 74 68 22 "
        "3A 22 30 22 2C 22 64 65 70 61 72 74 6D 65 6E 74 "
        "22 3A 22 22 2C 22 65 78 74 65 6E 73 69 6F 6E 22 "
        "3A 7B 22 70 6F 73 69 74 69 6F 6E 22 3A 22 31 22 "
        "7D 2C 22 67 65 6E 64 65 72 22 3A 31 2C 22 6D 65 "
        "64 69 63 61 6C 52 65 63 6F 72 64 4E 6F 22 3A 22 "
        "22 2C 22 6E 61 6D 65 22 3A 22 E5 BC A0 E4 B8 89 "
        "22 2C 22 69 64 22 3A 22 31 22 7D 2C 22 75 72 6C "
        "22 3A 22 68 74 74 70 73 3A 2F 2F 65 78 61 6D 70 "
        "6C 65 2E 63 6F 6D 2F 70 61 74 68 2F 50 61 74 69 "
        "65 6E 74 22 7D DD 7A"
    )

    print("\n\n▶ 验证第一次发送的帧（此帧CRC可能有误）")
    result = parse_frame(
        "53 4E 00 40 00 01 7B 22 66 68 69 72 22 3A 7B 22 "
        "69 64 22 3A 22 31 22 7D 2C 22 75 72 6C 22 3A 22 "
        "68 74 74 70 73 3A 2F 2F 65 78 61 6D 70 6C 65 2E "
        "63 6F 6D 2F 70 61 74 68 2F 50 61 74 69 65 6E 74 "
        "22 7D FD 8A"
    )

    # ── 关键分析 ──────────────────────────────────────────────
    print("\n\n" + "=" * 70)
    print("▶ 关键分析")
    print("=" * 70)
    print("""
问题现象:
  - 第一次发送: CRC 错误 → 仪器可能当做新请求处理
  - 第二次发送: CRC 正确(MODBUS)，但回显了全部病人数据 → E56-D

结论:
  1. CRC 算法 = CRC16-MODBUS ✓（已验证）
  2. 第二次 CRC 正确但仍然 E56-D → 说明 JSON 数据内容有问题
  3. 回显全部病人数据显然不是仪器期望的响应格式
  4. 需要确定正确的响应 JSON 结构

通信流程:
  ┌─────────┐                    ┌──────────┐
  │  仪 器   │                    │  服务器   │
  └────┬────┘                    └────┬─────┘
       │  1. POST Patient 病人信息    │
       │ ──────────────────────────> │
       │                             │
       │  2. 服务器确认应答           │
       │ <────────────────────────── │  ← 当前问题!
       │                             │
       │  3. POST Observation 检测结果│
       │ ──────────────────────────> │
       │                             │
       │  4. 服务器确认应答           │
       │ <────────────────────────── │
       │                             │
""")

    # ── 生成候选响应帧 ─────────────────────────────────────────
    PATIENT_URL = "https://example.com/path/Patient"
    OBS_URL = "https://example.com/path/Observation"

    print("=" * 70)
    print("▶ 服务器对 Patient POST 的响应候选方案")
    print("  优先级从高到低排列，建议按顺序尝试")
    print("=" * 70)

    # 最可能的方案 - fhir在前(与仪器发送格式一致) + POST
    generate_frame(1, {
        "fhir": {"id": "1"},
        "url": PATIENT_URL,
    }, "★ P1 (推荐首试): POST + fhir{id} + url（fhir在前）")

    # url在前
    generate_frame(1, {
        "url": PATIENT_URL,
        "fhir": {"id": "1"},
    }, "P2: POST + url + fhir{id}（url在前）")

    # 空fhir
    generate_frame(1, {
        "fhir": {},
        "url": PATIENT_URL,
    }, "P3: POST + fhir{} + url")

    generate_frame(1, {
        "url": PATIENT_URL,
        "fhir": {},
    }, "P4: POST + url + fhir{}")

    # 仅url
    generate_frame(1, {
        "url": PATIENT_URL,
    }, "P5: POST + 仅url")

    # fhir在前 + 仅url
    generate_frame(1, {
        "fhir": {},
    }, "P6: POST + 仅fhir{}")

    # 带 status
    generate_frame(1, {
        "fhir": {"id": "1", "status": 0},
        "url": PATIENT_URL,
    }, "P7: POST + fhir{id,status} + url")

    print("\n\n" + "─" * 70)
    print("  ── 备选: 尝试 PUT 操作类型（表示确认/更新）──")
    print("─" * 70)

    generate_frame(2, {
        "fhir": {"id": "1"},
        "url": PATIENT_URL,
    }, "U1: PUT + fhir{id} + url")

    generate_frame(2, {
        "url": PATIENT_URL,
        "fhir": {},
    }, "U2: PUT + url + fhir{}")

    print("\n\n" + "─" * 70)
    print("  ── 备选: 尝试 GET 操作类型 ──")
    print("─" * 70)

    generate_frame(0, {
        "fhir": {"id": "1"},
        "url": PATIENT_URL,
    }, "G1: GET + fhir{id} + url")

    generate_frame(0, {
        "url": PATIENT_URL,
        "fhir": {},
    }, "G2: GET + url + fhir{}")

    # ── Observation 响应 ──
    print("\n\n" + "=" * 70)
    print("▶ 服务器对 Observation POST 的响应候选方案")
    print("  （当 Patient 响应成功后，仪器会发送检测结果）")
    print("=" * 70)

    generate_frame(1, {
        "fhir": {"id": "1"},
        "url": OBS_URL,
    }, "O1: POST + fhir{id} + url(Observation)")

    generate_frame(1, {
        "url": OBS_URL,
        "fhir": {},
    }, "O2: POST + url(Observation) + fhir{}")

    generate_frame(1, {
        "url": OBS_URL,
    }, "O3: POST + 仅url(Observation)")

    # ── 使用说明 ──
    print("\n\n" + "=" * 70)
    print("▶ NetAssist 测试步骤")
    print("=" * 70)
    print("""
1. NetAssist 设置:
   - 协议类型: TCP Server
   - 端口: 9000
   - 发送设置: 选择 HEX 模式
   - 勾选"转义符指令解析"

2. 测试步骤:
   a) 等待仪器连接（会先发心跳 {"id":""}）
   b) 仪器点击"上传"后，会发送 Patient 病人信息
   c) 收到 Patient 数据后，立即将对应方案的HEX复制到发送框并发送
      - 先试 P1，如果仍 E56-D 则换 P2，依次尝试
   d) 如果响应正确，仪器应该继续发送 Observation 检测结果数据
   e) 收到 Observation 后，发送对应的 O1/O2/O3 响应

3. 判断响应是否成功:
   - 成功: 仪器不报错，并继续发送检测结果(Observation)
   - E56-D: 数据格式错误，换下一个方案
   - E59-D: 超时未回复，动作要更快
   - E55-D: 通讯线路忙，等几秒再试

4. 注意事项:
   - 必须用 HEX 模式发送!（选中发送区左侧的 HEX 单选框）
   - 超时约在几秒内，收到数据后要尽快回复
   - 如果 P1-P7 全部 E56-D，尝试 U1-U2 和 G1-G2
""")
