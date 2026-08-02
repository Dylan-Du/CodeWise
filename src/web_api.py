#!/usr/bin/env python3
"""Codex助手 — HTTP 控制 API 服务器。
提供 REST API 给 HTML 前端调用,控制 Codex助手 启停、模型切换、配置管理等。
同时托管 HTML 静态文件。
"""
import json
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    """支持端口复用，避免重启时 TIME_WAIT 导致绑定失败。"""
    allow_reuse_address = True
    allow_reuse_port = True
from pathlib import Path

import core
import adapter
import activation

HOST = "127.0.0.1"
PORT = 18668  # 控制 API 端口(Codex助手 在 18667)

# HTML 文件路径（兼容开发环境和 PyInstaller 打包环境）
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后：web 目录在 sys._MEIPASS 下
    _base = Path(sys._MEIPASS)
else:
    # 开发环境：web 在项目根目录
    _base = Path(__file__).parent.parent

HTML_DIR = _base / "web"
HTML_FILE = HTML_DIR / "index.html"
ASSETS_DIR = _base / "assets"


class APIHandler(BaseHTTPRequestHandler):
    """处理所有 /api/* 请求和静态文件"""

    # ─── 类级别共享状态 ───
    adapter_runner = None
    adapter_active = False  # 真实的启停标志，区别于端口检测
    _transitioning = False  # 防止轮询在 stop/start 期间误判
    timeline_items: list[dict] = []
    log_listeners: list = []

    def log_message(self, fmt, *args):
        """静默日志,避免污染 stdout"""
        pass

    # ─── 工具方法 ───

    def send_json(self, status: int, payload):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def send_options(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def read_body(self) -> dict:
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}

    def add_timeline(self, icon: str, desc: str, extra=None, icon_color: str = "success"):
        item = {
            "icon": icon,
            "desc": desc,
            "icon_color": icon_color,
            "time": time.strftime("%H:%M"),
        }
        if extra:
            item.update(extra)
        self.timeline_items.append(item)
        if len(self.timeline_items) > 100:
            self.timeline_items = self.timeline_items[-100:]

    # ─── 路由 ───

    def do_OPTIONS(self):
        self.send_options()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # ─── API 路由 ───
        if path == "/api/status":
            self._handle_status()
        elif path == "/api/activation/status":
            self._handle_activation_status()
        elif path == "/api/models":
            self._handle_models()
        elif path == "/api/timeline":
            self._handle_timeline()
        elif path == "/api/config":
            self._handle_config_list()
        elif path == "/api/token":
            self._handle_token()
        elif path == "/api/stats":
            self._handle_stats()
        elif path == "/api/errors":
            self._handle_errors()
        elif path == "/" or path == "/index.html":
            self._serve_file(HTML_FILE, "text/html; charset=utf-8")
        elif path.startswith("/assets/"):
            # 静态资源：先查 web/assets，再查项目根 assets 目录
            file_path = HTML_DIR / path.lstrip("/")
            if not file_path.exists():
                file_path = ASSETS_DIR / path[len("/assets/"):]
            if file_path.exists():
                content_type = "application/octet-stream"
                if path.endswith(".css"):
                    content_type = "text/css"
                elif path.endswith(".js"):
                    content_type = "application/javascript"
                elif path.endswith(".svg"):
                    content_type = "image/svg+xml"
                elif path.endswith(".png"):
                    content_type = "image/png"
                self._serve_file(file_path, content_type)
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/toggle":
            self._handle_toggle()
        elif path == "/api/activation/activate":
            self._handle_activation_activate()
        elif path == "/api/model/select":
            self._handle_model_select()
        elif path == "/api/config/save":
            self._handle_config_save()
        elif path == "/api/config/add":
            self._handle_config_add()
        elif path == "/api/config/edit":
            self._handle_config_edit()
        elif path == "/api/config/delete":
            self._handle_config_delete()
        elif path == "/api/token/clear":
            self._handle_token_clear()
        else:
            self.send_error(404)

    # ─── API 处理器 ───

    def _handle_status(self):
        # 如果正在执行启停操作，返回上一次的真实状态，避免轮询误判
        if APIHandler._transitioning:
            running = APIHandler.adapter_active
        else:
            running = APIHandler.adapter_active and core.adapter_running()
        cur_model = core.current_model()
        codex_in_adapter = core.codex_in_adapter_mode()
        token_totals = core.token_tracker.totals()

        # 首页只显示模型名称（不带服务商前缀）
        model_label = cur_model
        model_name = cur_model
        if cur_model:
            custom = core.load_custom()
            found = False
            for it in custom:
                if it["model"] == cur_model:
                    model_label = it["model"]
                    model_name = it["model"]
                    found = True
                    break
            # 如果当前配置的模型已不在模型列表中，显示未选择
            if not found:
                cur_model = None
                model_label = None
                model_name = None

        self.send_json(200, {
            "running": running,
            "model": cur_model,
            "model_label": model_label,
            "model_name": model_name,
            "codex_in_adapter": codex_in_adapter,
            "token": token_totals,
        })

    def _handle_activation_status(self):
        """检查激活状态。"""
        activated = activation.is_activated()
        data = activation.load_activation() if activated else {}
        device_id = activation.get_device_id() if not activated else ""
        self.send_json(200, {
            "activated": activated,
            "device_id": device_id,
            "type": data.get("type"),
            "expires_at": data.get("expires_at"),
        })

    def _handle_activation_activate(self):
        """激活码绑定。"""
        body = self.read_body()
        code = (body.get("code") or "").strip().upper()
        if not code:
            self.send_json(400, {"success": False, "message": "请输入激活码"})
            return
        result = activation.bind_code_online(code)
        if result.get("code") == 0 and result.get("data", {}).get("bound"):
            data = result.get("data", {})
            self.send_json(200, {
                "success": True,
                "message": "激活成功",
                "type": data.get("type"),
                "expires_at": data.get("expires_at"),
            })
        else:
            msg = result.get("message") or result.get("data", {}).get("message") or "激活失败"
            self.send_json(200, {"success": False, "message": msg})

    def _handle_models(self):
        """首页模型列表只展示已配置的自定义模型"""
        custom = core.load_custom()
        models = []
        for idx, it in enumerate(custom):
            models.append({
                "label": it["model"],
                "model": it["model"],
                "provider": it.get("label", ""),
                "route": f"custom:{idx}",
                "is_custom": True,
            })
        self.send_json(200, {"models": models, "custom": custom})

    def _handle_timeline(self):
        self.send_json(200, {"items": self.timeline_items})

    def _handle_config_list(self):
        custom = core.load_custom()
        models = []
        config_out = []
        for idx, it in enumerate(custom):
            config_out.append({
                "label": it.get("model", ""),
                "model": it.get("model", ""),
                "provider": it.get("label", ""),
                "upstream": it.get("upstream", ""),
                "key_url": it.get("key_url", ""),
                "api_key": it.get("api_key", ""),
            })
            models.append({
                "label": it["model"],
                "model": it["model"],
                "route": f"custom:{idx}",
                "is_custom": True,
            })
        self.send_json(200, {"config": config_out, "models": models})

    def _handle_token(self):
        self.send_json(200, {
            "totals": core.token_tracker.totals(),
            "recent": core.token_tracker.recent(20),
        })

    def _handle_stats(self):
        """返回按模型分组的统计数据"""
        stats = core.token_tracker.per_model_stats()
        totals = core.token_tracker.totals()
        total_calls = sum(s.get("calls", 0) for s in stats.values())
        self.send_json(200, {
            "per_model": list(stats.values()),
            "token": totals,
            "total_calls": total_calls,
            "history": core.token_tracker.recent(100),
        })

    def _handle_errors(self):
        """返回错误日志"""
        self.send_json(200, {
            "errors": core.error_tracker.recent(50),
        })

    def _handle_toggle(self):
        body = self.read_body()
        action = body.get("action", "toggle")
        requested_model = body.get("model", "")

        # 激活码校验：未激活不允许启动
        if action in ("start", "toggle") and not activation.is_activated():
            self.send_json(403, {"error": "请先激活后再启动服务", "need_activation": True})
            return

        is_active = APIHandler.adapter_active
        if action == "start" or (action == "toggle" and not is_active):
            self._do_start(requested_model)
        elif action == "stop" or (action == "toggle" and is_active):
            self._do_stop()
        else:
            self.send_json(200, {"ok": True, "running": is_active})

    def _do_start(self, requested_model: str = ""):
        # 获取已配置的自定义模型
        custom = core.load_custom()
        if not custom:
            self.send_json(400, {"error": "没有可用模型,请先添加模型"})
            return

        # 查找用户选中的模型，没选就用第一个
        target = None
        route = None
        if requested_model:
            for idx, it in enumerate(custom):
                if it["model"] == requested_model:
                    target = it
                    route = f"custom:{idx}"
                    break
        if not target:
            target = custom[0]
            route = "custom:0"

        label = target["label"]
        model = target["model"]

        try:
            info = core.resolve_route(route, model)
        except Exception as e:
            self.send_json(400, {"error": f"路由错误: {e}"})
            return

        if not info.get("api_key"):
            self.send_json(400, {"error": f"{label} 的 API Key 未配置"})
            return

        # 写入配置
        try:
            APIHandler._transitioning = True  # 防止轮询在 stop/start 期间误判
            # 先停止 adapter（如果运行中），避免文件被占用
            if APIHandler.adapter_runner:
                APIHandler.adapter_runner.stop()
                import time
                time.sleep(0.3)
            core.write_adapter_json(model, route)
            self.add_timeline("🔄", f"已写入 Codex助手 配置({label})", icon_color="switch")
            if core.backup_config_toml_if_needed():
                self.add_timeline("💾", f"已备份原 Codex 配置 → {core.BACKUP_TOML.name}", icon_color="info")
            core.apply_codex_config(model)
            self.add_timeline("✅", "配置已同步到 config.toml", icon_color="success")
        except PermissionError as e:
            APIHandler._transitioning = False
            APIHandler.adapter_active = False
            self.add_timeline("ERR", f"权限错误: {e}", icon_color="danger")
            self.send_json(500, {"error": str(e)})
            return
        except Exception as e:
            APIHandler._transitioning = False
            APIHandler.adapter_active = False
            import traceback
            tb = traceback.format_exc()
            self.add_timeline("ERR", f"配置写入失败: {e}", icon_color="danger")
            self.send_json(500, {"error": f"配置写入失败: {e}", "debug": tb})
            return

        # 启动 adapter
        if APIHandler.adapter_runner is None:
            APIHandler.adapter_runner = core.AdapterRunner(
                log_fn=lambda msg: self.add_timeline("📝", msg, icon_color="info"),
                on_usage=self._on_usage,
                on_error=self._on_error,
            )

        if not APIHandler.adapter_runner.start():
            APIHandler._transitioning = False
            APIHandler.adapter_active = False
            self.add_timeline("ERR", "Codex助手 启动失败", icon_color="danger")
            self.send_json(500, {"error": "Codex助手 启动失败，请检查端口 18667 是否被占用"})
            return

        APIHandler.adapter_active = True
        APIHandler._transitioning = False
        self.add_timeline("🚀", "Codex助手 服务已启动，可在 Codex App 中使用", icon_color="success")
        self.send_json(200, {"ok": True, "running": True})

    def _do_stop(self):
        # 先标记为已停止，防止轮询误判
        APIHandler.adapter_active = False
        # 停止 adapter（adapter 和 control API 在同一进程，不能 kill）
        if APIHandler.adapter_runner:
            APIHandler.adapter_runner.stop()
            APIHandler.adapter_runner = None
        else:
            # adapter_runner 为 None，尝试创建一个来停止
            # （处理状态不一致的情况）
            pass
        # 短暂等待端口释放
        import time as _time
        for _ in range(10):
            if not core.adapter_running():
                break
            _time.sleep(0.1)
        try:
            msg = core.restore_openai_config()
            self.add_timeline("🔙", msg, icon_color="info")
        except Exception as e:
            self.add_timeline("ERR", f"还原失败: {e}", icon_color="danger")
            self.send_json(500, {"error": f"还原失败: {e}"})
            return
        self.add_timeline("⏹️", "Codex助手 服务已停止，已恢复 OpenAI 原始配置", icon_color="stop")
        self.send_json(200, {"ok": True, "running": False})

    def _on_usage(self, model: str, input_tokens: int, output_tokens: int, cache_tokens: int):
        core.token_tracker.record(model, input_tokens, output_tokens, cache_tokens)
        self.add_timeline("📈", f"{model} 调用完成 · 输入 {input_tokens} / 输出 {output_tokens} / 缓存 {cache_tokens}",
                         {"stats": {"input": input_tokens, "output": output_tokens, "cache": cache_tokens}}, icon_color="token")

    def _on_error(self, model: str, error_type: str, message: str, details: str = ""):
        """记录错误并添加到时间线，同时上报到后台"""
        core.error_tracker.record(model, error_type, message, details)
        self.add_timeline("ERR", f"{model} 错误: {message}", {"error_details": details}, icon_color="danger")
        # 异步上报到后台日志系统
        try:
            activation.report_error(error_type, f"[{model}] {message}", details)
        except Exception:
            pass

    def _handle_model_select(self):
        body = self.read_body()
        route = body.get("route", "")
        model = body.get("model", "")

        if not route or not model:
            self.send_json(400, {"error": "缺少 route 或 model"})
            return

        try:
            info = core.resolve_route(route, model)
        except Exception as e:
            self.send_json(400, {"error": f"路由错误: {e}"})
            return

        if not info.get("api_key"):
            self.send_json(400, {"error": f"{info.get('label', model)} 的 API Key 未配置"})
            return

        try:
            # 先停止 adapter（如果运行中），避免文件被占用
            if APIHandler.adapter_runner:
                APIHandler.adapter_runner.stop()
                import time
                time.sleep(0.5)  # 等待文件释放
            core.write_adapter_json(model, route)
            core.apply_codex_config(model)
            # 重新启动 adapter
            if APIHandler.adapter_runner:
                time.sleep(0.2)
                if APIHandler.adapter_runner.start():
                    APIHandler.adapter_active = True
                else:
                    APIHandler.adapter_active = False
            self.add_timeline("🔀", f"已切换至 {info.get('label', model)}", icon_color="switch")
        except PermissionError as e:
            self.add_timeline("ERR", f"权限错误: {e}", icon_color="danger")
            self.send_json(500, {"error": str(e)})
            return
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.add_timeline("ERR", f"切换失败: {e}", icon_color="danger")
            self.send_json(500, {"error": f"切换失败: {e}", "debug": tb})
            return

        self.send_json(200, {"ok": True, "model_name": info.get('label', model)})

    def _handle_config_save(self):
        """统一保存接口：新增或编辑模型"""
        body = self.read_body()
        provider = body.get("provider", "")
        model = body.get("model", "").strip()
        url = body.get("url", "").strip()
        api_key = body.get("api_key", "").strip()

        if not provider or not model or not url:
            self.send_json(400, {"error": "缺少必填字段: provider, model, url"})
            return

        if not url.startswith(("http://", "https://")):
            self.send_json(400, {"error": "Base URL 必须以 http:// 或 https:// 开头"})
            return

        # 检查是否已存在相同模型，存在则编辑，否则新增
        items = core.load_custom()
        existing_idx = -1
        for idx, it in enumerate(items):
            if it["model"] == model:
                existing_idx = idx
                break

        if existing_idx >= 0:
            # 编辑现有模型：保留 provider 作为 label
            items[existing_idx] = {
                "label": provider or items[existing_idx].get("label", ""),
                "model": model,
                "upstream": url,
                "key_url": items[existing_idx].get("key_url", ""),
                "api_key": api_key,
            }
            core.save_custom_list(items)
            self.add_timeline("✏️", f"已更新模型: {model}", icon_color="switch")
        else:
            # 新增模型：provider 作为 label
            core.add_custom(provider, model, url, "", api_key)
            self.add_timeline("➕", f"已添加模型: {model}", icon_color="success")

        self.send_json(200, {"ok": True})

    def _handle_config_add(self):
        body = self.read_body()
        required = ["label", "model", "upstream", "api_key"]
        missing = [k for k in required if not body.get(k)]
        if missing:
            self.send_json(400, {"error": f"缺少字段: {', '.join(missing)}"})
            return

        if not body["upstream"].startswith(("http://", "https://")):
            self.send_json(400, {"error": "Base URL 必须以 http:// 或 https:// 开头"})
            return

        core.add_custom(
            body["label"], body["model"], body["upstream"],
            body.get("key_url", ""), body["api_key"],
        )
        self.add_timeline("➕", f"已添加模型: {body['label']}", icon_color="success")
        self.send_json(200, {"ok": True})

    def _handle_config_edit(self):
        body = self.read_body()
        index = body.get("index", -1)
        if index < 0:
            self.send_json(400, {"error": "缺少 index"})
            return

        items = core.load_custom()
        if index >= len(items):
            self.send_json(404, {"error": "配置不存在"})
            return

        items[index] = {
            "label": body.get("label", items[index]["label"]),
            "model": body.get("model", items[index]["model"]),
            "upstream": body.get("upstream", items[index]["upstream"]),
            "key_url": body.get("key_url", items[index].get("key_url", "")),
            "api_key": body.get("api_key", items[index].get("api_key", "")),
        }
        core.save_custom_list(items)
        self.add_timeline("✏️", f"已编辑模型: {items[index]['label']}", icon_color="switch")
        self.send_json(200, {"ok": True})

    def _handle_config_delete(self):
        body = self.read_body()
        index = body.get("index", -1)
        if index < 0:
            self.send_json(400, {"error": "缺少 index"})
            return

        items = core.load_custom()
        if index >= len(items):
            self.send_json(404, {"error": "配置不存在"})
            return

        label = items[index]["label"]
        core.remove_custom(index)
        self.add_timeline("🗑️", f"已删除模型: {label}", icon_color="stop")
        self.send_json(200, {"ok": True})

    def _handle_token_clear(self):
        core.token_tracker.clear()
        self.add_timeline("🧹", "已清空 Token 用量统计", icon_color="info")
        self.send_json(200, {"ok": True})

    # ─── 静态文件 ───

    def _serve_file(self, path: Path, content_type: str):
        if not path.exists():
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        with open(path, "rb") as f:
            self.wfile.write(f.read())


class WebServer:
    """控制 API 服务器"""

    def __init__(self):
        self.httpd = None
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.httpd = ReusableThreadingHTTPServer((HOST, PORT), APIHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        print(f"控制 API 已启动: http://{HOST}:{PORT}", flush=True)

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread:
            self.thread.join(timeout=2)


# 全局服务器实例
web_server = WebServer()


def start_server():
    web_server.start()


def stop_server():
    web_server.stop()


if __name__ == "__main__":
    web_server.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        web_server.stop()
