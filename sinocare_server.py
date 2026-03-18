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
    """构建响应帧: SN + len + op + data + CRC(高字节在前,与真实服务器一致)"""
    ob = struct.pack(">H", op)
    crc = crc16_modbus(ob + data)
    cb = struct.pack(">H", crc)  # 高字节在前 (真实服务器抓包验证)
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


OP_CREATED = 0x00C9   # 201 = HTTP Created (真实服务器抓包确认)
OP_OBS_OK = 0x025E    # 606 = Observation响应码 (真实服务器抓包确认)
id_counter = [1000]   # 自增ID

def respond(mode, parsed, frame_type):
    """根据真实服务器抓包结果生成正确响应"""
    if mode == 0:
        return "(静默)", b''

    # 根据帧类型确定resourceType和操作码
    resource_map = {
        "device": ("Device", OP_CREATED),
        "patient": ("Patient", OP_CREATED),
        "observation": ("Observation", OP_OBS_OK),
        "qc": ("Observation", OP_OBS_OK),
        "unknown": ("Resource", OP_CREATED),
    }

    # Communication帧(仪器上报错误日志)
    url = ""
    if parsed["jo"]:
        url = parsed["jo"].get("url", "")
    if "/Communication" in url:
        resource_type = "Communication"
        op_code = OP_CREATED
    else:
        resource_type, op_code = resource_map.get(frame_type, ("Resource", OP_CREATED))

    id_counter[0] += 1
    d = json.dumps({"id": str(id_counter[0]), "resourceType": resource_type},
                   separators=(',', ':')).encode()

    desc = f"OP=0x{op_code:04X} {{id:{id_counter[0]},resourceType:{resource_type}}}"
    return desc, build(op_code, d)


MAX_MODE = 1  # 只有一种模式了(正确模式)


auto_counter = [0]  # 全局计数器，跨连接持续递增

def handle(conn, addr, mode):
    ts = time.strftime("%H:%M:%S")
    print(f"\n{'='*72}")
    print(f"[{ts}] 仪器连接: {addr[0]}:{addr[1]}")
    print(f"[{ts}] 模式: {mode}, 当前Patient轮换计数: {auto_counter[0]}")
    print(f"{'='*72}")

    conn.settimeout(300)
    buf = b''
    n = 0

    # 发送欢迎消息(真实服务器也会发)
    try:
        welcome = b"Welcome to LIS service!\n"
        conn.sendall(welcome)
        print(f"[{ts}] ▶ 发送欢迎消息")
    except:
        pass

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

                # 发送响应(使用从真实服务器抓包得到的正确格式)
                if mode == 0:
                    print(f"    [静默: 不回复]")
                    continue

                desc, resp = respond(1, p, frame_type)

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
