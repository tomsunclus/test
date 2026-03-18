#!/usr/bin/env python3
"""
三诺 iPOCT 协议 - TCP 调试服务器

功能:
  1. 精确捕获仪器发送的每一个字节 (HEX + ASCII)
  2. 完整解析 SN 协议帧
  3. 可选自动回复多种响应格式

用法:
  python sinocare_server.py           → 默认9000端口，静默模式(只收不发)
  python sinocare_server.py 9000 0    → 静默模式: 只接收不回复，观察仪器完整行为
  python sinocare_server.py 9000 1    → 精确回显模式
  python sinocare_server.py 9000 99   → 自动逐个尝试所有模式

第一步请用模式0运行，观察仪器的完整发送流程!
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


def build_frame(op_type: int, data: bytes) -> bytes:
    """标准帧: SN + length + op + data + CRC(低字节在前)"""
    op_bytes = struct.pack(">H", op_type)
    crc = crc16_modbus(op_bytes + data)
    crc_bytes = struct.pack("<H", crc)  # 低字节在前 (已确认: 低=E56-D=帧可识别)
    frame_length = 2 + len(data) + 2
    return b'\x53\x4E' + struct.pack(">H", frame_length) + op_bytes + data + crc_bytes


def parse_frame(raw: bytes):
    if len(raw) < 8 or raw[0:2] != b'\x53\x4E':
        return None
    frame_length = struct.unpack(">H", raw[2:4])[0]
    total = 4 + frame_length
    if len(raw) < total:
        return None

    frame = raw[:total]
    op_type = struct.unpack(">H", frame[4:6])[0]
    data_content = frame[6:-2]
    crc_received = struct.unpack("<H", frame[-2:])[0]  # 低字节在前
    crc_calc = crc16_modbus(frame[4:-2])

    result = {
        "raw": frame,
        "frame_length": frame_length,
        "op_type": op_type,
        "data_content": data_content,
        "crc_received": crc_received,
        "crc_calc": crc_calc,
        "crc_ok": crc_received == crc_calc,
        "total": total,
    }
    try:
        result["json_str"] = data_content.decode('utf-8')
        result["json_obj"] = json.loads(result["json_str"])
    except:
        result["json_str"] = None
        result["json_obj"] = None
    return result


def hex_dump(data: bytes, prefix: str = "    "):
    """格式化的十六进制dump，类似Wireshark"""
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02X}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        lines.append(f"{prefix}{i:04X}  {hex_part:<48s}  {ascii_part}")
    return '\n'.join(lines)


def generate_response(mode: int, parsed: dict) -> tuple:
    """返回 (描述, 响应字节) 或 (描述, b'')"""
    data = parsed["data_content"]
    raw = parsed["raw"]
    url = ""
    if parsed["json_obj"]:
        url = parsed["json_obj"].get("url", "")

    modes = {
        0: ("静默(不回复)", b''),
        1: ("精确回显(原样返回仪器发来的帧)", raw),
        2: ("POST + 同样的JSON数据", build_frame(1, data)),
        3: ("PUT + 同样的JSON数据", build_frame(2, data)),
        4: ("GET + 同样的JSON数据", build_frame(0, data)),
        5: ("POST + {fhir:{id:1},url}", build_frame(1,
            json.dumps({"fhir":{"id":"1"},"url":url}, ensure_ascii=False, separators=(',',':')).encode())),
        6: ("PUT + {fhir:{id:1},url}", build_frame(2,
            json.dumps({"fhir":{"id":"1"},"url":url}, ensure_ascii=False, separators=(',',':')).encode())),
        7: ("POST + {url,fhir:{id:1}}", build_frame(1,
            json.dumps({"url":url,"fhir":{"id":"1"}}, ensure_ascii=False, separators=(',',':')).encode())),
        8: ("POST + {fhir:{},url}", build_frame(1,
            json.dumps({"fhir":{},"url":url}, ensure_ascii=False, separators=(',',':')).encode())),
        9: ("POST + {url}", build_frame(1,
            json.dumps({"url":url}, ensure_ascii=False, separators=(',',':')).encode())),
        10: ("POST + 空JSON {}", build_frame(1, b'{}')),
        11: ("POST + 空数据", build_frame(1, b'')),
        12: ("PUT + 空数据", build_frame(2, b'')),
        13: ("GET + 空数据", build_frame(0, b'')),
        14: ("POST + {code:0}", build_frame(1, b'{"code":0}')),
        15: ("POST + {status:0}", build_frame(1, b'{"status":0}')),
        16: ("POST + 带空格JSON", build_frame(1,
            json.dumps({"fhir": {"id": "1"}, "url": url}, ensure_ascii=False).encode())),
    }

    if mode in modes:
        return modes[mode]
    return ("未知模式", b'')


MAX_MODE = 16


def handle_client(conn, addr, mode):
    ts = time.strftime("%H:%M:%S")
    print(f"\n{'='*72}")
    print(f"[{ts}] 仪器已连接: {addr[0]}:{addr[1]}")
    if mode == 0:
        print(f"[{ts}] 模式: 0 = 静默模式(只接收不回复)")
        print(f"[{ts}] 目的: 观察仪器的完整通信流程")
    elif mode == 99:
        print(f"[{ts}] 模式: 99 = 自动逐个尝试 (模式1→{MAX_MODE})")
    else:
        desc, _ = generate_response(mode, {"data_content": b'', "raw": b'', "json_obj": {"url": ""}, "json_str": ""})
        print(f"[{ts}] 模式: {mode} = {desc}")
    print(f"{'='*72}")

    conn.settimeout(300)
    buffer = b''
    data_frame_count = 0
    current_auto_mode = 1

    try:
        while True:
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                print(f"\n[超时5分钟，断开]")
                break
            if not chunk:
                print(f"\n[仪器断开连接]")
                break

            ts = time.strftime("%H:%M:%S.") + f"{time.time() % 1:.3f}"[2:]
            buffer += chunk

            print(f"\n[{ts}] ◀ 收到 {len(chunk)} 字节")
            print(hex_dump(chunk))

            while len(buffer) >= 4:
                sn_pos = buffer.find(b'\x53\x4E')
                if sn_pos == -1:
                    print(f"    (无SN帧头，丢弃 {len(buffer)} 字节)")
                    buffer = b''
                    break
                if sn_pos > 0:
                    print(f"    (跳过 {sn_pos} 字节非帧数据)")
                    buffer = buffer[sn_pos:]

                if len(buffer) < 4:
                    break
                frame_length = struct.unpack(">H", buffer[2:4])[0]
                total = 4 + frame_length
                if len(buffer) < total:
                    print(f"    (等待更多数据: 需要{total}字节, 当前{len(buffer)}字节)")
                    break

                parsed = parse_frame(buffer[:total])
                buffer = buffer[total:]

                if not parsed:
                    continue

                op_names = {0:"GET", 1:"POST", 2:"PUT", 3:"DELETE", 8:"心跳"}
                op_name = op_names.get(parsed["op_type"], f"0x{parsed['op_type']:04X}")
                crc_s = "✓" if parsed["crc_ok"] else f"✗(期望0x{parsed['crc_calc']:04X})"

                is_heartbeat = (parsed["json_obj"] and
                    set(parsed["json_obj"].keys()) <= {"id"} and
                    parsed["json_obj"].get("id", "") == "")

                if is_heartbeat:
                    print(f"    ♥ 心跳帧 | op={op_name} CRC={crc_s}")
                    continue

                data_frame_count += 1
                print(f"\n    {'━'*60}")
                print(f"    ★ 数据帧 #{data_frame_count}")
                print(f"    ├ 帧长度: {parsed['frame_length']}")
                print(f"    ├ 操作类型: {op_name}")
                print(f"    ├ CRC: 0x{parsed['crc_received']:04X} {crc_s}")
                print(f"    ├ 数据长度: {len(parsed['data_content'])} 字节")

                if parsed["json_str"]:
                    print(f"    ├ JSON: {parsed['json_str']}")
                    if parsed["json_obj"]:
                        print(f"    ├ JSON格式化:")
                        for k, v in parsed["json_obj"].items():
                            if isinstance(v, dict):
                                print(f"    │   {k}: {json.dumps(v, ensure_ascii=False)}")
                            else:
                                print(f"    │   {k}: {v}")

                print(f"    ├ 完整帧HEX:")
                print(hex_dump(parsed["raw"], "    │   "))
                print(f"    {'━'*60}")

                # 发送响应
                if mode == 0:
                    print(f"\n    [静默模式: 不发送响应，继续观察仪器行为...]")
                    continue

                actual_mode = mode
                if mode == 99:
                    actual_mode = current_auto_mode
                    current_auto_mode += 1
                    if current_auto_mode > MAX_MODE:
                        current_auto_mode = 1

                desc, response = generate_response(actual_mode, parsed)

                if not response:
                    print(f"\n    [模式{actual_mode}: {desc}]")
                    continue

                resp_ts = time.strftime("%H:%M:%S.") + f"{time.time() % 1:.3f}"[2:]
                print(f"\n[{resp_ts}] ▶ 发送响应 [模式{actual_mode}: {desc}]")
                print(hex_dump(response))

                try:
                    conn.sendall(response)
                    print(f"    发送成功 ({len(response)} 字节)")
                except Exception as e:
                    print(f"    发送失败: {e}")

                print(f"\n    ⏳ 等待仪器下一条消息...")

    except Exception as e:
        print(f"\n[异常: {e}]")
        traceback.print_exc()
    finally:
        conn.close()
        print(f"\n[连接关闭, 共收到 {data_frame_count} 个数据帧]")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
    mode = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    print("=" * 72)
    print("  三诺 iPOCT 协议 - TCP 调试服务器")
    print("=" * 72)
    print(f"  端口: {port}")
    print(f"  CRC: CRC16-MODBUS, 低字节在前 (已确认)")
    print()
    print("  可用模式:")
    print("    0  = 静默模式 (只收不发，观察仪器完整行为) ★ 第一步用这个!")
    print("    1  = 精确回显 (原样返回仪器发来的帧)")
    print("    2  = POST + 仪器发来的同样JSON")
    print("    3  = PUT  + 仪器发来的同样JSON")
    print("    4  = GET  + 仪器发来的同样JSON")
    print("    5  = POST + {fhir:{id:1},url}")
    print("    6  = PUT  + {fhir:{id:1},url}")
    print("    7  = POST + {url,fhir:{id:1}}")
    print("    8  = POST + {fhir:{},url}")
    print("    9  = POST + {url}")
    print("    10 = POST + {}")
    print("    11 = POST 空数据")
    print("    12 = PUT  空数据")
    print("    13 = GET  空数据")
    print("    14 = POST + {code:0}")
    print("    15 = POST + {status:0}")
    print("    16 = POST + 带空格JSON")
    print("    99 = 自动逐个尝试 (每次换一种)")
    print()
    print(f"  当前模式: {mode}")
    print("=" * 72)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', port))
    sock.listen(1)

    print(f"\n  ✓ 服务器已启动: 0.0.0.0:{port}")
    print(f"  → 将仪器的服务器IP设为本机IP，端口设为 {port}")
    print(f"  → 等待仪器连接...\n")

    try:
        while True:
            conn, addr = sock.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            handle_client(conn, addr, mode)
            print(f"\n  → 等待下一次连接...\n")
    except KeyboardInterrupt:
        print("\n\n  服务器已停止 (Ctrl+C)")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
