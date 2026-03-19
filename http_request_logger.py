#!/usr/bin/env python3
"""
HTTP 请求日志记录代理服务

功能:
  1. 监听指定端口，记录所有收到的 HTTP 请求（Headers + Body）
  2. 可选：将请求转发到真实后端服务（透明代理模式）
  3. 所有请求详情写入日志文件，同时打印到终端

用法:
  # 仅记录模式 - 监听 8281 端口，记录所有请求
  python3 http_request_logger.py --port 8281

  # 代理模式 - 监听 8281 端口，记录后转发到真实后端 8280 端口
  python3 http_request_logger.py --port 8281 --forward http://127.0.0.1:8280

  # 指定日志文件
  python3 http_request_logger.py --port 8281 --log ./logs/ecg_requests.log

部署提示:
  如果要替代原来的 8280 端口:
  1. 先把原服务改到 8281 端口
  2. 本工具监听 8280 端口，转发到 8281
  python3 http_request_logger.py --port 8280 --forward http://127.0.0.1:8281
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


LOG_FORMAT = "%(asctime)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

request_counter = 0


def setup_logger(log_file):
    os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else ".", exist_ok=True)

    logger = logging.getLogger("http_logger")
    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(file_handler)

    return logger


def format_json_body(body_str):
    try:
        parsed = json.loads(body_str)
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        return body_str


class RequestLoggerHandler(BaseHTTPRequestHandler):
    forward_url = None
    logger = None

    def log_message(self, format, *args):
        pass

    def _handle_request(self, method):
        global request_counter
        request_counter += 1
        req_id = request_counter
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8", errors="replace") if content_length > 0 else ""

        separator = "=" * 80
        log_lines = [
            "",
            separator,
            f"[请求 #{req_id}] {timestamp}",
            separator,
            f"来源地址: {self.client_address[0]}:{self.client_address[1]}",
            f"请求方法: {method}",
            f"请求路径: {self.path}",
            f"HTTP版本: {self.request_version}",
            "",
            "--- 请求头 (Headers) ---",
        ]

        for header, value in self.headers.items():
            log_lines.append(f"  {header}: {value}")

        log_lines.append("")
        if body:
            log_lines.append("--- 请求体 (Body) ---")
            formatted_body = format_json_body(body)
            log_lines.append(formatted_body)
        else:
            log_lines.append("--- 请求体 (Body): 空 ---")

        if self.forward_url:
            log_lines.append("")
            log_lines.append(f"--- 转发到: {self.forward_url}{self.path} ---")
            try:
                forward_target = f"{self.forward_url}{self.path}"
                req = Request(
                    forward_target,
                    data=body.encode("utf-8") if body else None,
                    method=method,
                )
                for header, value in self.headers.items():
                    if header.lower() not in ("host", "content-length"):
                        req.add_header(header, value)
                if body:
                    req.add_header("Content-Length", str(len(body.encode("utf-8"))))

                with urlopen(req, timeout=30) as resp:
                    resp_status = resp.status
                    resp_headers = dict(resp.headers)
                    resp_body = resp.read().decode("utf-8", errors="replace")

                log_lines.append(f"转发响应状态: {resp_status}")
                log_lines.append("转发响应头:")
                for h, v in resp_headers.items():
                    log_lines.append(f"  {h}: {v}")
                log_lines.append("转发响应体:")
                log_lines.append(format_json_body(resp_body))

                self.send_response(resp_status)
                for h, v in resp_headers.items():
                    if h.lower() not in ("transfer-encoding",):
                        self.send_header(h, v)
                self.end_headers()
                self.wfile.write(resp_body.encode("utf-8"))

            except HTTPError as e:
                resp_body = e.read().decode("utf-8", errors="replace")
                log_lines.append(f"转发失败 - HTTP {e.code}: {resp_body}")
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(resp_body.encode("utf-8"))

            except URLError as e:
                log_lines.append(f"转发失败 - 连接错误: {e.reason}")
                self.send_response(502)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                error_resp = json.dumps({"error": f"Backend unreachable: {e.reason}"})
                self.wfile.write(error_resp.encode("utf-8"))

            except Exception as e:
                log_lines.append(f"转发失败 - 异常: {str(e)}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                error_resp = json.dumps({"error": str(e)})
                self.wfile.write(error_resp.encode("utf-8"))
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            response = json.dumps({
                "code": 0,
                "msg": "OK - Request logged successfully",
                "requestId": req_id,
                "serverTime": timestamp,
            })
            self.wfile.write(response.encode("utf-8"))

        log_lines.append(separator)
        full_log = "\n".join(log_lines)
        self.logger.info(full_log)

    def do_GET(self):
        self._handle_request("GET")

    def do_POST(self):
        self._handle_request("POST")

    def do_PUT(self):
        self._handle_request("PUT")

    def do_DELETE(self):
        self._handle_request("DELETE")

    def do_PATCH(self):
        self._handle_request("PATCH")

    def do_OPTIONS(self):
        self._handle_request("OPTIONS")


def main():
    parser = argparse.ArgumentParser(
        description="HTTP 请求日志记录代理服务 - 用于抓取和记录第三方系统发送的 HTTP 请求"
    )
    parser.add_argument("--port", type=int, default=8281,
                        help="监听端口 (默认: 8281)")
    parser.add_argument("--host", default="0.0.0.0",
                        help="监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--forward", default=None,
                        help="转发目标地址，例如 http://127.0.0.1:8280 (不设置则仅记录)")
    parser.add_argument("--log", default="./logs/http_requests.log",
                        help="日志文件路径 (默认: ./logs/http_requests.log)")

    args = parser.parse_args()

    logger = setup_logger(args.log)

    RequestLoggerHandler.forward_url = args.forward.rstrip("/") if args.forward else None
    RequestLoggerHandler.logger = logger

    server = HTTPServer((args.host, args.port), RequestLoggerHandler)

    mode = "代理模式" if args.forward else "仅记录模式"
    print("=" * 60)
    print("  HTTP 请求日志记录服务已启动")
    print("=" * 60)
    print(f"  运行模式: {mode}")
    print(f"  监听地址: {args.host}:{args.port}")
    if args.forward:
        print(f"  转发目标: {args.forward}")
    print(f"  日志文件: {os.path.abspath(args.log)}")
    print(f"  启动时间: {datetime.now().strftime(DATE_FORMAT)}")
    print("=" * 60)
    print("  按 Ctrl+C 停止服务")
    print("=" * 60)
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n服务已停止，共处理 {request_counter} 个请求")
        print(f"日志文件: {os.path.abspath(args.log)}")
        server.server_close()


if __name__ == "__main__":
    main()
