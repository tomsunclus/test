#!/usr/bin/env python3
"""
三诺 iPOCT 协议 - 自动应答 TCP 服务器

用法:
  python3 sinocare_server.py [端口] [响应模式]

响应模式:
  0  = 不回复（静默，观察仪器完整发送流程）
  1  = 精确回显（原样返回仪器发来的帧）
  2  = 修改操作类型后回显（PUT=0x02）
  3  = 修改操作类型后回显（GET=0x00）
  4  = POST + {"fhir":{"id":"1"},"url":"<仪器url>"}
  5  = PUT  + {"fhir":{"id":"1"},"url":"<仪器url>"}
  6  = GET  + {"fhir":{"id":"1"},"url":"<仪器url>"}
  7  = POST + {"code":0}
  8  = PUT  + {"code":0}
  9  = POST + 空数据(纯ACK帧)
  10 = PUT  + 空数据(纯ACK帧)
  11 = POST + {} (空JSON)
  12 = POST + {"url":"<仪器url>","fhir":{"id":"1","status":0}}
  13 = 无操作类型帧: SN+length+data+CRC (CRC仅覆盖data)
  14 = 帧长度不含CRC: SN+length(op+data)+op+data+CRC
  15 = POST + 精确回显仪器的JSON数据（完全相同的fhir内容）
  16 = POST + {"fhir":{"id":"<extension.position>"},"url":"<仪器url>"}
  99 = 逐个自动尝试模式0-16（每次收到数据换一种响应）

默认: 端口=9000, 模式=99(自动逐个尝试)

示例:
  python3 sinocare_server.py 9000 99
  python3 sinocare_server.py 9000 1
"""

import socket
import struct
import json
import sys
import time
import traceback


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


def parse_frame(raw: bytes):
    """解析一个SN协议帧，返回解析结果或None"""
    if len(raw) < 8:
        return None
    if raw[0:2] != b'\x53\x4E':
        return None

    frame_length = struct.unpack(">H", raw[2:4])[0]
    expected_total = 4 + frame_length  # header(2) + length(2) + payload(frame_length)

    if len(raw) < expected_total:
        return None

    frame_data = raw[:expected_total]
    op_type = struct.unpack(">H", frame_data[4:6])[0]
    data_content = frame_data[6:-2]
    crc_received = struct.unpack(">H", frame_data[-2:])[0]  # 高字节在前

    crc_scope = frame_data[4:-2]
    crc_calc = crc16_modbus(crc_scope)

    result = {
        "raw": frame_data,
        "frame_length": frame_length,
        "op_type": op_type,
        "data_content": data_content,
        "crc_received": crc_received,
        "crc_calc": crc_calc,
        "crc_ok": crc_received == crc_calc,
        "total_bytes": expected_total,
    }

    try:
        result["json_str"] = data_content.decode('utf-8')
        result["json_obj"] = json.loads(result["json_str"])
    except (UnicodeDecodeError, json.JSONDecodeError):
        result["json_str"] = None
        result["json_obj"] = None

    return result


def build_frame(op_type: int, data: bytes) -> bytes:
    """标准帧: SN + length + op + data + CRC (CRC覆盖op+data)"""
    op_bytes = struct.pack(">H", op_type)
    crc = crc16_modbus(op_bytes + data)
    crc_bytes = struct.pack(">H", crc)  # 高字节在前(仪器实际使用big-endian)
    frame_length = 2 + len(data) + 2
    return b'\x53\x4E' + struct.pack(">H", frame_length) + op_bytes + data + crc_bytes


def build_frame_no_optype(data: bytes) -> bytes:
    """变体帧(无操作类型): SN + length + data + CRC (CRC仅覆盖data)"""
    crc = crc16_modbus(data)
    crc_bytes = struct.pack(">H", crc)  # 高字节在前
    frame_length = len(data) + 2
    return b'\x53\x4E' + struct.pack(">H", frame_length) + data + crc_bytes


def build_frame_short_length(op_type: int, data: bytes) -> bytes:
    """变体帧(帧长度不含CRC): SN + length(op+data) + op + data + CRC"""
    op_bytes = struct.pack(">H", op_type)
    crc = crc16_modbus(op_bytes + data)
    crc_bytes = struct.pack(">H", crc)  # 高字节在前
    frame_length = 2 + len(data)  # 不含CRC的2字节
    return b'\x53\x4E' + struct.pack(">H", frame_length) + op_bytes + data + crc_bytes


def print_hex(label: str, data: bytes):
    hex_str = data.hex(' ').upper()
    if len(hex_str) > 120:
        hex_str = hex_str[:120] + f"... (共{len(data)}字节)"
    print(f"  {label}: {hex_str}")


def print_frame_info(prefix: str, parsed: dict):
    op_names = {0: "GET", 1: "POST", 2: "PUT", 3: "DELETE", 8: "心跳"}
    op_name = op_names.get(parsed["op_type"], f"0x{parsed['op_type']:04X}")

    crc_status = "✓" if parsed["crc_ok"] else f"✗(期望0x{parsed['crc_calc']:04X})"

    print(f"\n{'─'*70}")
    print(f"  {prefix}")
    print(f"  帧长度={parsed['frame_length']}, 操作类型={op_name}, "
          f"数据={len(parsed['data_content'])}字节, CRC=0x{parsed['crc_received']:04X} {crc_status}")
    print_hex("原始帧", parsed["raw"])

    if parsed["json_str"]:
        if len(parsed["json_str"]) > 200:
            print(f"  JSON: {parsed['json_str'][:200]}...")
        else:
            print(f"  JSON: {parsed['json_str']}")
        if parsed["json_obj"]:
            url = parsed["json_obj"].get("url", "")
            if url:
                print(f"  URL: {url}")
    elif parsed["data_content"]:
        print_hex("数据(非UTF8)", parsed["data_content"])


def generate_response(mode: int, parsed_frame: dict) -> bytes:
    """根据模式生成响应帧"""
    received_data = parsed_frame["data_content"]
    received_op = parsed_frame["op_type"]
    received_raw = parsed_frame["raw"]

    url = ""
    position = ""
    if parsed_frame["json_obj"]:
        url = parsed_frame["json_obj"].get("url", "")
        fhir = parsed_frame["json_obj"].get("fhir", {})
        ext = fhir.get("extension", parsed_frame["json_obj"].get("extension", {}))
        position = ext.get("position", "1") if isinstance(ext, dict) else "1"

    if mode == 0:
        return b''
    elif mode == 1:
        return received_raw
    elif mode == 2:
        return build_frame(0x0002, received_data)  # PUT + 原始数据
    elif mode == 3:
        return build_frame(0x0000, received_data)  # GET + 原始数据
    elif mode == 4:
        data = json.dumps({"fhir": {"id": "1"}, "url": url}, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return build_frame(0x0001, data)
    elif mode == 5:
        data = json.dumps({"fhir": {"id": "1"}, "url": url}, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return build_frame(0x0002, data)
    elif mode == 6:
        data = json.dumps({"fhir": {"id": "1"}, "url": url}, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return build_frame(0x0000, data)
    elif mode == 7:
        data = json.dumps({"code": 0}, separators=(',', ':')).encode('utf-8')
        return build_frame(0x0001, data)
    elif mode == 8:
        data = json.dumps({"code": 0}, separators=(',', ':')).encode('utf-8')
        return build_frame(0x0002, data)
    elif mode == 9:
        return build_frame(0x0001, b'')
    elif mode == 10:
        return build_frame(0x0002, b'')
    elif mode == 11:
        return build_frame(0x0001, b'{}')
    elif mode == 12:
        data = json.dumps({"url": url, "fhir": {"id": "1", "status": 0}}, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return build_frame(0x0001, data)
    elif mode == 13:
        data = json.dumps({"fhir": {"id": "1"}, "url": url}, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return build_frame_no_optype(data)
    elif mode == 14:
        data = json.dumps({"fhir": {"id": "1"}, "url": url}, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return build_frame_short_length(0x0001, data)
    elif mode == 15:
        return build_frame(0x0001, received_data)  # POST + 完全相同的数据
    elif mode == 16:
        data = json.dumps({"fhir": {"id": position}, "url": url}, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return build_frame(0x0001, data)
    else:
        return b''


MODE_NAMES = {
    0: "静默(不回复)",
    1: "精确回显(原样返回)",
    2: "PUT+原始数据回显",
    3: "GET+原始数据回显",
    4: "POST+{fhir:{id:1},url}",
    5: "PUT+{fhir:{id:1},url}",
    6: "GET+{fhir:{id:1},url}",
    7: "POST+{code:0}",
    8: "PUT+{code:0}",
    9: "POST+空数据(纯ACK)",
    10: "PUT+空数据(纯ACK)",
    11: "POST+空JSON{}",
    12: "POST+{url,fhir:{id,status:0}}",
    13: "无操作类型帧(SN+len+data+CRC)",
    14: "帧长度不含CRC变体",
    15: "POST+精确回显仪器JSON数据",
    16: "POST+{fhir:{id:position},url}",
}


def handle_client(conn, addr, mode):
    print(f"\n{'='*70}")
    print(f"  仪器连接: {addr[0]}:{addr[1]}")
    print(f"  响应模式: {mode} = {MODE_NAMES.get(mode, '自动逐个尝试')}")
    print(f"{'='*70}")

    conn.settimeout(120)
    buffer = b''
    frame_count = 0
    current_mode = 0 if mode == 99 else mode
    heartbeat_count = 0

    try:
        while True:
            try:
                data = conn.recv(4096)
            except socket.timeout:
                print("\n  [超时120秒无数据，断开连接]")
                break

            if not data:
                print("\n  [仪器断开连接]")
                break

            buffer += data
            timestamp = time.strftime("%H:%M:%S")

            print(f"\n  [{timestamp}] 收到 {len(data)} 字节:")
            print_hex("原始数据", data)

            while len(buffer) >= 8:
                if buffer[0:2] != b'\x53\x4E':
                    skip = buffer.find(b'\x53\x4E', 1)
                    if skip == -1:
                        print(f"  [跳过 {len(buffer)} 字节非SN数据]")
                        buffer = b''
                        break
                    print(f"  [跳过 {skip} 字节，找到SN帧头]")
                    buffer = buffer[skip:]
                    continue

                if len(buffer) < 4:
                    break

                frame_length = struct.unpack(">H", buffer[2:4])[0]
                expected_total = 4 + frame_length

                if len(buffer) < expected_total:
                    break

                parsed = parse_frame(buffer[:expected_total])
                buffer = buffer[expected_total:]

                if parsed is None:
                    continue

                frame_count += 1
                is_heartbeat = parsed["op_type"] == 8 or (
                    parsed["json_obj"] and
                    set(parsed["json_obj"].keys()) <= {"id"} and
                    parsed["json_obj"].get("id", "") == ""
                )

                if is_heartbeat:
                    heartbeat_count += 1
                    if heartbeat_count <= 3 or heartbeat_count % 10 == 0:
                        print(f"\n  [{timestamp}] ♥ 心跳 #{heartbeat_count} (不回复)")
                    continue

                print_frame_info(f"[{timestamp}] 收到数据帧 #{frame_count}", parsed)

                if mode == 99:
                    current_mode = (frame_count - heartbeat_count - 1) % len(MODE_NAMES)
                    while current_mode not in MODE_NAMES:
                        current_mode += 1

                response = generate_response(current_mode, parsed)

                if response:
                    print(f"\n  >>> 发送响应 [模式{current_mode}: {MODE_NAMES.get(current_mode, '?')}]")
                    print_hex("响应帧", response)

                    resp_parsed = parse_frame(response)
                    if resp_parsed:
                        op_names = {0: "GET", 1: "POST", 2: "PUT", 3: "DELETE", 8: "心跳"}
                        print(f"  响应详情: op={op_names.get(resp_parsed['op_type'], hex(resp_parsed['op_type']))}, "
                              f"数据={len(resp_parsed['data_content'])}字节, CRC=0x{resp_parsed['crc_received']:04X}")

                    try:
                        conn.sendall(response)
                        print(f"  >>> 发送成功 ({len(response)} 字节)")
                    except Exception as e:
                        print(f"  >>> 发送失败: {e}")
                else:
                    print(f"\n  >>> 模式{current_mode}: 不发送响应（静默）")

                print(f"\n  ⏳ 等待仪器下一条消息... (观察仪器是否报错)")

    except Exception as e:
        print(f"\n  [连接异常: {e}]")
        traceback.print_exc()
    finally:
        conn.close()
        print(f"\n  连接已关闭 (共收到{frame_count}帧, 其中心跳{heartbeat_count}次)")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
    mode = int(sys.argv[2]) if len(sys.argv) > 2 else 99

    print("=" * 70)
    print("  三诺 iPOCT 协议 - 自动应答 TCP 服务器")
    print("=" * 70)
    print(f"  端口: {port}")
    print(f"  模式: {mode} = {MODE_NAMES.get(mode, '自动逐个尝试(0→16)')}")
    print()
    print("  可用模式:")
    for k, v in sorted(MODE_NAMES.items()):
        print(f"    {k:3d} = {v}")
    print(f"     99 = 自动逐个尝试(每次数据帧换一种)")
    print()
    print(f"  用法: python3 sinocare_server.py {port} <模式号>")
    print("=" * 70)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', port))
    server.listen(1)

    print(f"\n  ✓ 服务器已启动，监听 0.0.0.0:{port}")
    print(f"  → 请将仪器的服务器地址设置为本机IP，端口 {port}")
    print(f"  → 等待仪器连接...\n")

    try:
        while True:
            conn, addr = server.accept()
            handle_client(conn, addr, mode)
            print(f"\n  → 等待下一次仪器连接...\n")
    except KeyboardInterrupt:
        print("\n\n  服务器已停止 (Ctrl+C)")
    finally:
        server.close()


if __name__ == "__main__":
    main()
