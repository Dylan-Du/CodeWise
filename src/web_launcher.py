#!/usr/bin/env python3
"""Codex助手 — pywebview 桌面启动器。
启动控制 API 服务器,然后在原生 webview 窗口中打开 HTML UI。
"""
import os
import sys
import time
import threading

# 确保 src 目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import web_api


def wait_for_server(host: str, port: int, timeout: float = 10.0) -> bool:
    """等待服务器就绪"""
    import socket
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main():
    # 启动控制 API 服务器
    web_api.start_server()

    # 等待就绪
    if not wait_for_server(web_api.HOST, web_api.PORT):
        print("控制 API 启动失败", file=sys.stderr)
        sys.exit(1)

    # 启动 pywebview
    try:
        import webview
    except ImportError:
        print("缺少 pywebview,请运行: pip install pywebview", file=sys.stderr)
        sys.exit(1)

    url = f"http://{web_api.HOST}:{web_api.PORT}/"

    window = webview.create_window(
        "Codex助手",
        url=url,
        width=420,
        height=680,
        min_size=(320, 480),
        frameless=False,
        easy_drag=False,
    )

    # 设置窗口图标(兼容打包环境)
    if getattr(sys, 'frozen', False):
        icon_path = os.path.join(sys._MEIPASS, "assets", "icon-1024.png")
    else:
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon-1024.png")
    if os.path.exists(icon_path):
        try:
            window.icon = icon_path
        except Exception:
            pass

    webview.start(debug=False)


if __name__ == "__main__":
    main()
