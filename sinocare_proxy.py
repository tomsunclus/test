"""
三诺 iPOCT 协议 - TCP 代理 (中间人抓包)

仪器 → 本机:9000 → 47.99.87.157:9525 (三诺真实服务器)
         ↕ 记录所有双向数据

用法: python sinocare_proxy.py
"""
import socket, struct, threading, time, sys


REMOTE_HOST = "47.99.87.157"
REMOTE_PORT = 9525
LOCAL_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9000


def crc16_modbus(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1: crc = (crc >> 1) ^ 0xA001
            else: crc >>= 1
    return crc


def hexd(d, pfx="    "):
    lines = []
    for i in range(0, len(d), 16):
        c = d[i:i+16]
        h = ' '.join(f'{b:02X}' for b in c)
        a = ''.join(chr(b) if 32 <= b < 127 else '.' for b in c)
        lines.append(f"{pfx}{i:04X}  {h:<48s}  {a}")
    return '\n'.join(lines)


def parse_frames(data, label):
    """尝试解析SN帧并打印"""
    pos = 0
    while pos < len(data) - 7:
        idx = data.find(b'\x53\x4E', pos)
        if idx < 0 or idx + 4 > len(data):
            break
        fl = struct.unpack(">H", data[idx+2:idx+4])[0]
        total = 4 + fl
        if idx + total > len(data):
            break

        frame = data[idx:idx+total]
        op = struct.unpack(">H", frame[4:6])[0]
        dc = frame[6:-2]

        crc_hi = struct.unpack(">H", frame[-2:])[0]
        crc_lo = struct.unpack("<H", frame[-2:])[0]
        crc_calc = crc16_modbus(frame[4:-2])

        crc_s = ""
        if crc_calc == crc_hi:
            crc_s = f"0x{crc_hi:04X} ✓(高字节在前)"
        elif crc_calc == crc_lo:
            crc_s = f"0x{crc_lo:04X} ✓(低字节在前)"
        else:
            crc_s = f"bytes={frame[-2:].hex().upper()} calc=0x{crc_calc:04X} ✗"

        url = ""
        try:
            for enc in ['gbk', 'utf-8']:
                try:
                    js = dc.decode(enc)
                    import json
                    jo = json.loads(js)
                    url = jo.get("url", "")
                    break
                except:
                    continue
        except:
            pass

        ftype = ""
        if "/Device" in url: ftype = "[DEVICE]"
        elif "/Patient" in url: ftype = "[PATIENT]"
        elif "/Observation" in url: ftype = "[OBSERVATION]"
        elif "/qc/" in url: ftype = "[QC]"
        elif url: ftype = f"[{url.split('/')[-1]}]"

        op_names = {0:"GET",1:"POST",2:"PUT",3:"DELETE",8:"心跳"}
        op_name = op_names.get(op, f"0x{op:04X}")

        print(f"    {label} 帧 {ftype} op={op_name} len={fl} CRC={crc_s}")
        if url:
            print(f"    {label} URL: {url}")

        try:
            for enc in ['gbk', 'utf-8']:
                try:
                    text = dc.decode(enc)
                    if len(text) > 300:
                        print(f"    {label} JSON({enc}): {text[:300]}...")
                    else:
                        print(f"    {label} JSON({enc}): {text}")
                    break
                except:
                    continue
        except:
            pass

        pos = idx + total

    return pos


def forward(src, dst, label, other_label):
    """转发数据并记录"""
    try:
        while True:
            data = src.recv(4096)
            if not data:
                ts = time.strftime("%H:%M:%S")
                print(f"\n[{ts}] {label} 连接关闭")
                break

            ts = time.strftime("%H:%M:%S")
            print(f"\n[{ts}] {label} → {other_label}: {len(data)} 字节")
            print(hexd(data))
            parse_frames(data, label)

            dst.sendall(data)

    except Exception as e:
        ts = time.strftime("%H:%M:%S")
        print(f"\n[{ts}] {label} 异常: {e}")
    finally:
        try: src.close()
        except: pass
        try: dst.close()
        except: pass


def handle(client, addr):
    ts = time.strftime("%H:%M:%S")
    print(f"\n{'='*72}")
    print(f"[{ts}] 仪器连接: {addr[0]}:{addr[1]}")
    print(f"[{ts}] 连接三诺服务器 {REMOTE_HOST}:{REMOTE_PORT} ...")

    try:
        remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote.settimeout(10)
        remote.connect((REMOTE_HOST, REMOTE_PORT))
        remote.settimeout(None)
        print(f"[{ts}] ✓ 已连接三诺服务器")
    except Exception as e:
        print(f"[{ts}] ✗ 连接三诺服务器失败: {e}")
        client.close()
        return

    print(f"[{ts}] 开始双向转发...")
    print(f"{'='*72}")

    t1 = threading.Thread(target=forward, args=(client, remote, "仪器", "服务器"), daemon=True)
    t2 = threading.Thread(target=forward, args=(remote, client, "服务器", "仪器"), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    print(f"\n[{time.strftime('%H:%M:%S')}] 会话结束")


def main():
    print("=" * 72)
    print("  三诺 iPOCT 协议 - TCP 代理 (中间人抓包)")
    print("=" * 72)
    print(f"  本地监听: 0.0.0.0:{LOCAL_PORT}")
    print(f"  远程服务器: {REMOTE_HOST}:{REMOTE_PORT}")
    print(f"  仪器 → 本机:{LOCAL_PORT} → {REMOTE_HOST}:{REMOTE_PORT}")
    print("=" * 72)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(('0.0.0.0', LOCAL_PORT))
    except OSError as e:
        print(f"\n  ✗ 端口 {LOCAL_PORT} 被占用: {e}")
        input("按回车退出...")
        return
    sock.listen(5)
    print(f"\n  ✓ 代理已启动")
    print(f"  → 将仪器服务器IP设为本机IP(192.168.1.29)，端口 {LOCAL_PORT}")
    print(f"  → 等待仪器连接...\n")

    try:
        while True:
            client, addr = sock.accept()
            client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            threading.Thread(target=handle, args=(client, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n  已停止")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
