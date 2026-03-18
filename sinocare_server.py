"""
三诺 iPOCT 协议 - 自动应答 TCP 服务器

已确认:
  - CRC16-MODBUS, 高字节在前(big-endian) ← 仪器自身数据验证
  - 仪器连接后先发 Device 注册帧, 再发 Patient/Observation 帧
  - 仪器使用 GBK 编码

用法:
  python sinocare_server.py              → 默认模式(自动回复Device+Patient)
  python sinocare_server.py 9000 0       → 静默模式
  python sinocare_server.py 9000 99      → 自动逐个尝试
"""
import socket, struct, json, sys, time, traceback


def crc16_modbus(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def build(op, data):
    """构建响应帧: SN + len + op + data + CRC(低字节在前,仪器接收端验证)"""
    ob = struct.pack(">H", op)
    crc = crc16_modbus(ob + data)
    cb = struct.pack("<H", crc)  # 低字节在前 (仪器接收端验证用低字节在前)
    fl = struct.pack(">H", 2 + len(data) + 2)
    return b'\x53\x4E' + fl + ob + data + cb


def parse(raw):
    if len(raw) < 8 or raw[:2] != b'\x53\x4E':
        return None
    fl = struct.unpack(">H", raw[2:4])[0]
    total = 4 + fl
    if len(raw) < total:
        return None
    f = raw[:total]
    op = struct.unpack(">H", f[4:6])[0]
    data = f[6:-2]
    crc_r = struct.unpack(">H", f[-2:])[0]  # 高字节在前
    crc_c = crc16_modbus(f[4:-2])
    r = {"raw": f, "fl": fl, "op": op, "data": data,
         "crc_ok": crc_r == crc_c, "crc_r": crc_r, "crc_c": crc_c, "total": total}
    try:
        r["js"] = data.decode('gbk')  # 仪器使用GBK编码
        r["jo"] = json.loads(r["js"])
    except:
        try:
            r["js"] = data.decode('utf-8', errors='replace')
            r["jo"] = json.loads(r["js"])
        except:
            r["js"] = None
            r["jo"] = None
    return r


def hexd(d, pfx="    "):
    lines = []
    for i in range(0, len(d), 16):
        c = d[i:i+16]
        h = ' '.join(f'{b:02X}' for b in c)
        a = ''.join(chr(b) if 32 <= b < 127 else '.' for b in c)
        lines.append(f"{pfx}{i:04X}  {h:<48s}  {a}")
    return '\n'.join(lines)


def respond(mode, parsed, frame_type):
    """frame_type: 'device', 'patient', 'observation', 'other'"""
    url = ""
    if parsed["jo"]:
        url = parsed["jo"].get("url", "")

    if mode == 0:
        return "(静默)", b''

    desc_prefix = f"{frame_type}响应"

    if mode == 1:  # 回显(用低字节CRC重新构建)
        return f"{desc_prefix}: POST+原始数据(低CRC)", build(1, parsed["data"])
    elif mode == 2:  # PUT + 同数据
        return f"{desc_prefix}: PUT+同数据", build(2, parsed["data"])
    elif mode == 3:  # GET + 同数据
        return f"{desc_prefix}: GET+同数据", build(0, parsed["data"])
    elif mode == 4:  # POST + {fhir:{id:1},url}
        d = json.dumps({"fhir":{"id":"1"},"url":url}, separators=(',',':')).encode()
        return f"{desc_prefix}: POST+fhir{{id}}+url", build(1, d)
    elif mode == 5:  # PUT + {fhir:{id:1},url}
        d = json.dumps({"fhir":{"id":"1"},"url":url}, separators=(',',':')).encode()
        return f"{desc_prefix}: PUT+fhir{{id}}+url", build(2, d)
    elif mode == 6:  # POST + {url,fhir:{}}
        d = json.dumps({"url":url,"fhir":{}}, separators=(',',':')).encode()
        return f"{desc_prefix}: POST+url+fhir{{}}", build(1, d)
    elif mode == 7:  # POST + {url}
        d = json.dumps({"url":url}, separators=(',',':')).encode()
        return f"{desc_prefix}: POST+url", build(1, d)
    elif mode == 8:  # POST + {}
        return f"{desc_prefix}: POST+{{}}", build(1, b'{}')
    elif mode == 9:  # POST 空
        return f"{desc_prefix}: POST空数据", build(1, b'')
    elif mode == 10:  # POST+{code:0}
        return f"{desc_prefix}: POST+code:0", build(1, b'{"code":0}')
    elif mode == 11:  # POST+{status:0}
        return f"{desc_prefix}: POST+status:0", build(1, b'{"status":0}')
    elif mode == 12:  # POST + 带空格
        d = json.dumps({"fhir": {"id": "1"}, "url": url}).encode()
        return f"{desc_prefix}: POST+带空格JSON", build(1, d)
    else:
        return "(无)", b''


MAX_MODE = 12


def handle(conn, addr, mode):
    ts = time.strftime("%H:%M:%S")
    print(f"\n{'='*72}")
    print(f"[{ts}] 仪器连接: {addr[0]}:{addr[1]}")
    print(f"[{ts}] 模式: {mode}")
    print(f"{'='*72}")

    conn.settimeout(300)
    buf = b''
    n = 0
    auto_mode = 1

    try:
        while True:
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                print(f"\n[超时]")
                break
            if not chunk:
                print(f"\n[断开]")
                break

            ts = time.strftime("%H:%M:%S")
            buf += chunk
            print(f"\n[{ts}] ◀ 收到 {len(chunk)} 字节")

            while len(buf) >= 4:
                pos = buf.find(b'\x53\x4E')
                if pos < 0:
                    buf = b''
                    break
                if pos > 0:
                    buf = buf[pos:]

                if len(buf) < 4:
                    break
                fl = struct.unpack(">H", buf[2:4])[0]
                total = 4 + fl
                if len(buf) < total:
                    break

                p = parse(buf[:total])
                buf = buf[total:]
                if not p:
                    continue

                crc_s = "✓" if p["crc_ok"] else f"✗"

                # 识别帧类型
                frame_type = "unknown"
                url = ""
                if p["jo"]:
                    url = p["jo"].get("url", "")
                    if "/Device" in url:
                        frame_type = "device"
                    elif "/Patient" in url:
                        frame_type = "patient"
                    elif "/Observation" in url:
                        frame_type = "observation"
                    elif "/qc/" in url:
                        frame_type = "qc"
                    elif p["jo"].get("id") is not None and len(p["jo"]) <= 2:
                        frame_type = "heartbeat"

                if frame_type == "heartbeat":
                    print(f"    ♥ 心跳 CRC={crc_s}")
                    continue

                n += 1
                print(f"\n    {'━'*60}")
                print(f"    ★ 帧 #{n} [{frame_type.upper()}]")
                print(f"    ├ 操作: {p['op']}, 长度: {p['fl']}, CRC: 0x{p['crc_r']:04X} {crc_s}")
                if url:
                    print(f"    ├ URL: {url}")
                if p["js"]:
                    if len(p["js"]) > 200:
                        print(f"    ├ JSON: {p['js'][:200]}...")
                    else:
                        print(f"    ├ JSON: {p['js']}")
                print(f"    ├ 完整帧HEX ({len(p['raw'])}字节):")
                print(hexd(p["raw"]))
                print(f"    {'━'*60}")

                # 决定响应
                if mode == 0:
                    print(f"    [静默: 不回复]")
                    continue

                actual_mode = mode
                if mode == 99:
                    actual_mode = auto_mode
                    auto_mode = (auto_mode % MAX_MODE) + 1

                desc, resp = respond(actual_mode, p, frame_type)

                if not resp:
                    print(f"    [{desc}]")
                    continue

                rts = time.strftime("%H:%M:%S")
                print(f"\n[{rts}] ▶ 发送 [模式{actual_mode}: {desc}]")
                print(hexd(resp))

                try:
                    conn.sendall(resp)
                    print(f"    ✓ 已发送 {len(resp)} 字节")
                except Exception as e:
                    print(f"    ✗ 发送失败: {e}")

    except Exception as e:
        print(f"\n[异常: {e}]")
        traceback.print_exc()
    finally:
        conn.close()
        print(f"\n[关闭, 共 {n} 帧]")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
    mode = int(sys.argv[2]) if len(sys.argv) > 2 else 99

    print("=" * 72)
    print("  三诺 iPOCT 协议 - 自动应答服务器")
    print("  CRC: CRC16-MODBUS (仪器发送:高字节在前, 服务器回复:低字节在前)")
    print("=" * 72)
    print(f"  端口: {port}, 模式: {mode}")
    print("  模式说明:")
    print("    0  = 静默 (只收不发)")
    print("    1  = 精确回显")
    print("    2  = PUT+同数据  3=GET+同数据  4=POST+fhir{id}+url")
    print("    5  = PUT+fhir{id}+url  6=POST+url+fhir{}  7=POST+url")
    print("    8  = POST+{}  9=POST空  10=POST+code:0")
    print("    11 = POST+status:0  12=POST+带空格JSON")
    print("    99 = 自动逐个尝试(每次换一种) ★推荐")
    print("=" * 72)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(('0.0.0.0', port))
    except OSError as e:
        print(f"\n  ✗ 端口 {port} 被占用: {e}")
        print(f"    请关闭 NetAssist 或其他占用程序")
        input("按回车退出...")
        return
    sock.listen(5)
    print(f"\n  ✓ 监听 0.0.0.0:{port}")
    print(f"  → 等待仪器连接...\n")

    try:
        while True:
            conn, addr = sock.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            handle(conn, addr, mode)
            print(f"\n  → 等待下一次连接...\n")
    except KeyboardInterrupt:
        print("\n  已停止")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
