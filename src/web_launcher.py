#!/usr/bin/env python3
"""Codex助手 — pywebview 桌面启动器。
启动控制 API 服务器,然后在原生 webview 窗口中打开 HTML UI。
"""
import os
import sys
import time
import threading
import webbrowser
import urllib.request
import subprocess
from pathlib import Path

# 确保 src 目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import web_api


class JsApi:
    """暴露给 JavaScript 的 API 类"""
    
    def __init__(self):
        self._window = None
        self._download_progress = {}
    
    def set_window(self, window):
        """设置窗口引用（由 main 调用）"""
        self._window = window
    
    def openUrl(self, url: str) -> bool:
        """在系统默认浏览器中打开 URL"""
        try:
            webbrowser.open(url)
            return True
        except Exception as e:
            print(f"打开 URL 失败: {e}", file=sys.stderr)
            return False
    
    def downloadFile(self, url: str, filename: str = "") -> dict:
        """下载文件到下载目录，返回结果"""
        try:
            # 确定下载目录
            downloads_dir = Path.home() / "Downloads"
            if not downloads_dir.exists():
                downloads_dir = Path.home()
            
            # 确定文件名
            if not filename:
                filename = url.split("/")[-1] or "download"
                # URL 解码文件名
                import urllib.parse
                filename = urllib.parse.unquote(filename)
            
            filepath = downloads_dir / filename
            
            # 下载文件（带进度）
            def do_download():
                try:
                    import urllib.request
                    import ssl
                    
                    # 创建 SSL 上下文（兼容证书问题）
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    
                    # 获取文件信息
                    req = urllib.request.Request(url, headers={
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
                    })
                    response = urllib.request.urlopen(req, timeout=30, context=ctx)
                    
                    # 获取文件大小
                    total_size = int(response.headers.get('Content-Length', 0))
                    downloaded = 0
                    chunk_size = 65536  # 64KB chunks for better performance
                    
                    # 立即通知前端已连接
                    if self._window:
                        try:
                            self._window.evaluate_js("window._downloadProgress && window._downloadProgress(1)")
                        except:
                            pass
                    
                    with open(filepath, 'wb') as f:
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # 报告进度
                            if total_size > 0 and self._window:
                                percent = int(downloaded * 100 / total_size)
                                try:
                                    self._window.evaluate_js(f"window._downloadProgress && window._downloadProgress({percent})")
                                except:
                                    pass
                            elif self._window and downloaded % (512 * 1024) == 0:
                                # 无 Content-Length 时，按已下载量报告
                                mb = downloaded // (1024 * 1024)
                                try:
                                    self._window.evaluate_js(f"window._downloadProgress && window._downloadProgress(-1)")
                                except:
                                    pass
                    
                    # 下载完成，自动打开 DMG 安装
                    if filename.lower().endswith('.dmg'):
                        # DMG 文件：直接打开（挂载并弹出安装窗口）
                        subprocess.run(["open", str(filepath)], check=False)
                    else:
                        # 其他文件：在 Finder 中显示
                        subprocess.run(["open", "-R", str(filepath)], check=False)
                    if self._window:
                        self._window.evaluate_js("window._downloadComplete && window._downloadComplete()")
                        
                except Exception as e:
                    print(f"下载失败: {e}", file=sys.stderr)
                    if self._window:
                        try:
                            # 转义错误消息中的特殊字符
                            err_msg = str(e).replace("'", "\\'").replace("\n", " ")
                            self._window.evaluate_js(f"window._downloadError && window._downloadError('{err_msg}')")
                        except:
                            pass
            
            # 在后台线程下载
            thread = threading.Thread(target=do_download, daemon=True)
            thread.start()
            
            return {"success": True, "path": str(filepath), "message": "开始下载"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def openInFinder(self, path: str) -> bool:
        """在 Finder 中显示文件"""
        try:
            subprocess.run(["open", "-R", path], check=False)
            return True
        except Exception as e:
            print(f"打开 Finder 失败: {e}", file=sys.stderr)
            return False


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

    # 创建 API 实例
    api = JsApi()

    window = webview.create_window(
        "Codex助手",
        url=url,
        width=420,
        height=680,
        min_size=(320, 480),
        frameless=False,
        easy_drag=False,
        js_api=api,  # 暴露 API 给 JavaScript
    )
    
    # 设置窗口引用
    api.set_window(window)

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
