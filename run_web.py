#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Entry point để khởi chạy Web Server WordScan.me (MathScanToWord Web Version)
"""
import os
import sys
import argparse
import uvicorn

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chạy Web Server WordScan.me")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Địa chỉ IP lắng nghe (mặc định: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)), help="Cổng mạng (mặc định: 8000)")
    parser.add_argument("--reload", action="store_true", help="Bật chế độ tự tải lại khi sửa code (Dev mode)")
    args = parser.parse_args()

    print("=" * 70)
    print("🚀 KHỞI ĐỘNG HỆ THỐNG WEB WORDSAN.ME - SỐ HÓA SÁCH TOÁN SANG WORD")
    print(f"👉 Địa chỉ truy cập: http://localhost:{args.port} hoặc http://127.0.0.1:{args.port}")
    print("👑 Tài khoản Admin mặc định: admin / admin123")
    print("=" * 70)

    uvicorn.run("web.app:app", host=args.host, port=args.port, reload=args.reload)
