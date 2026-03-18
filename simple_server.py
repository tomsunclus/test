"""
最简TCP服务器 - 测试仪器能否连接
用法: python simple_server.py
"""
import socket
import time

PORT = 9000

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

try:
    sock.bind(('0.0.0.0', PORT))
except OSError as e:
    print(f"端口 {PORT} 绑定失败: {e}")
    print("请确认 NetAssist 已完全关闭!")
    input("按回车退出...")
    exit(1)

sock.listen(5)
print(f"[OK] 服务器已启动，监听端口 {PORT}")
print(f"[..] 等待仪器连接...(如果超过1分钟没反应，请重启仪器的网络)")
print()

while True:
    try:
        conn, addr = sock.accept()
        print(f"[连接] {addr[0]}:{addr[1]} 已连接!")

        while True:
            try:
                data = conn.recv(4096)
                if not data:
                    print(f"[断开] {addr[0]} 断开连接")
                    break
                ts = time.strftime("%H:%M:%S")
                print(f"[{ts}] 收到 {len(data)} 字节: {data.hex(' ').upper()}")

                try:
                    text = data.decode('utf-8', errors='replace')
                    printable = ''.join(c if 32 <= ord(c) < 127 else '.' for c in text)
                    print(f"[{ts}] ASCII: {printable}")
                except:
                    pass

            except ConnectionResetError:
                print(f"[断开] {addr[0]} 连接被重置")
                break
            except Exception as e:
                print(f"[错误] {e}")
                break

        conn.close()
        print(f"[..] 等待下一次连接...")

    except KeyboardInterrupt:
        print("\n[停止] Ctrl+C")
        break

sock.close()
