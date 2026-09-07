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
import theme_manager

HOST = "127.0.0.1"
PORT = 18668  # 控制 API 端口(Codex助手 在 18667)
ALLOWED_NEW_PROVIDERS = frozenset({"APINest", "自定义"})

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
        elif path == "/api/themes/status":
            self._handle_theme_status()
        elif path == "/api/themes/local":
            self._handle_theme_local()
        elif path == "/api/themes/builtin":
            self._handle_theme_builtin()
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
        elif path == "/api/config/test-url":
            self._handle_config_test_url()
        elif path == "/api/token/clear":
            self._handle_token_clear()
        elif path == "/api/themes/apply":
            self._handle_theme_apply()
        elif path == "/api/themes/apply-builtin":
            self._handle_theme_apply_builtin()
        elif path == "/api/themes/restore":
            self._handle_theme_restore()
        elif path == "/api/themes/customize":
            self._handle_theme_customize()
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
            # 内置 provider 模型：直接识别（不在自定义列表中）
            if core.model_to_provider(cur_model):
                found = True
            else:
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
                "provider": it.get("label", ""),
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

        # 启动前清理 18667 的外部占用者（守门进程/残留服务），
        # 避免端口冲突导致"启动失败"
        try:
            core.clear_adapter_port()
        except Exception:
            pass

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
        for _ in range(5):
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
        # 启动守门进程占用 18667：历史对话（锁定本地适配器）请求时返回
        # 明确指引，而不是 "502 Bad Gateway: Unknown error"
        try:
            if core.spawn_gatekeeper():
                self.add_timeline("🚧", "守门服务已接管 18667（历史对话将收到明确提示）", icon_color="info")
        except Exception:
            pass
        self.add_timeline("⏹️", "Codex助手 服务已停止，已恢复 OpenAI 原始配置", icon_color="stop")
        self.send_json(200, {"ok": True, "running": False})

    def _on_usage(self, model: str, input_tokens: int, output_tokens: int, cache_tokens: int):
        core.token_tracker.record(model, input_tokens, output_tokens, cache_tokens)
        self.add_timeline("📈", f"{model} 调用完成 · 输入 {input_tokens} / 输出 {output_tokens} / 缓存 {cache_tokens}",
                         {"stats": {"input": input_tokens, "output": output_tokens, "cache": cache_tokens}}, icon_color="token")

    def _on_error(self, model: str, error_type: str, message: str, details: str = ""):
        """记录错误并添加到本地时间线。"""
        core.error_tracker.record(model, error_type, message, details)
        self.add_timeline("ERR", f"{model} 错误: {message}", {"error_details": details}, icon_color="danger")

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

        # 检查是否已存在相同模型（同 model + 同 upstream 视为重复，不同 upstream 允许同名模型）
        items = core.load_custom()
        # 忽略配置文件中的非字典项，避免异常数据导致保存失败
        items = [item for item in items if isinstance(item, dict)]
        existing_idx = -1
        for idx, it in enumerate(items):
            if it.get("model") == model and it.get("upstream") == url:
                existing_idx = idx
                break

        if existing_idx < 0 and provider not in ALLOWED_NEW_PROVIDERS:
            self.send_json(400, {"error": "新增模型服务商仅支持 APINest 或 自定义"})
            return

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

        if body["label"] not in ALLOWED_NEW_PROVIDERS:
            self.send_json(400, {"error": "新增模型服务商仅支持 APINest 或 自定义"})
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
        if not isinstance(items[index], dict):
            self.send_json(400, {"error": "配置格式无效"})
            return

        current = items[index]
        label = body.get("label", current.get("label", ""))
        model = body.get("model", current.get("model", ""))
        upstream = body.get("upstream", current.get("upstream", ""))
        if not label or not model or not upstream:
            self.send_json(400, {"error": "配置不能为空"})
            return
        if not upstream.startswith(("http://", "https://")):
            self.send_json(400, {"error": "Base URL 必须以 http:// 或 https:// 开头"})
            return

        items[index] = {
            "label": label,
            "model": model,
            "upstream": upstream,
            "key_url": body.get("key_url", current.get("key_url", "")),
            "api_key": body.get("api_key", current.get("api_key", "")),
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

    def _handle_config_test_url(self):
        """测试 Base URL 连通性，返回分类诊断结果。"""
        body = self.read_body()
        url = body.get("url", "")
        result = adapter.probe_url(url, timeout=8)
        # 不可达时返回 200 + ok=false，方便前端统一处理
        self.send_json(200, result)

    def _handle_token_clear(self):
        core.token_tracker.clear()
        self.add_timeline("🧹", "已清空 Token 用量统计", icon_color="info")
        self.send_json(200, {"ok": True})

    # ─── 主题管理 API ───

    def _handle_theme_status(self):
        """获取主题状态和基准检测结果"""
        baseline = theme_manager.theme_manager.check_baseline()
        current_theme = theme_manager.theme_manager.get_current_theme()

        self.send_json(200, {
            "baseline": baseline,
            "current_theme": current_theme
        })

    def _handle_theme_local(self):
        """获取本地主题列表"""
        themes = theme_manager.theme_manager.get_local_themes()
        self.send_json(200, {"themes": themes})

    def _handle_theme_builtin(self):
        """获取内置主题列表（含背景缩略图）"""
        themes = theme_manager.theme_manager.get_builtin_themes()
        self.send_json(200, {"themes": themes})

    def _handle_theme_customize(self):
        """创建自定义主题"""
        # 检查是否是文件上传
        content_type = self.headers.get("Content-Type", "")
        
        if "multipart/form-data" in content_type:
            # 处理文件上传
            result = self._handle_image_upload()
        else:
            # 处理 JSON 参数
            body = self.read_body()
            image_path = body.get("image_path", "")
            params = body.get("params", {})
            
            if not image_path:
                self.send_json(400, {"error": "缺少 image_path"})
                return
            
            result = theme_manager.theme_manager.create_custom_theme(image_path, params)
            
            if result["success"]:
                self.add_timeline("🖼️", f"已创建自定义主题: {result['theme_id']}", icon_color="success")
            else:
                self.add_timeline("ERR", f"创建失败: {result['message']}", icon_color="danger")
            
            self.send_json(200, result)

    def _handle_image_upload(self) -> dict:
        """处理图片上传"""
        import cgi
        import tempfile
        from pathlib import Path
        
        result = {
            "success": False,
            "image_path": "",
            "message": ""
        }
        
        try:
            # 解析 multipart 表单
            content_type = self.headers.get("Content-Type", "")
            boundary = None
            for part in content_type.split(";"):
                part = part.strip()
                if part.startswith("boundary="):
                    boundary = part[9:]
                    break
            
            if not boundary:
                raise ValueError("无效的表单数据")
            
            # 读取请求体
            length = int(self.headers.get("content-length", "0"))
            body = self.rfile.read(length)
            
            # 解析表单字段
            boundary_bytes = boundary.encode("utf-8")
            parts = body.split(b"--" + boundary_bytes)
            
            for part in parts:
                if not part or part == b"--\r\n":
                    continue
                
                # 解析 header 和内容
                try:
                    header_end = part.index(b"\r\n\r\n")
                    headers_raw = part[:header_end].decode("utf-8")
                    content = part[header_end + 4:]
                    
                    # 移除末尾的 \r\n
                    if content.endswith(b"\r\n"):
                        content = content[:-2]
                    
                    # 检查是否是文件
                    if "filename=" in headers_raw:
                        # 提取文件名
                        for line in headers_raw.split("\r\n"):
                            if "filename=" in line:
                                filename = line.split('filename="')[1].split('"')[0]
                                break
                        
                        # 保存到临时目录
                        temp_dir = Path(tempfile.mkdtemp())
                        temp_path = temp_dir / filename
                        
                        with open(temp_path, "wb") as f:
                            f.write(content)
                        
                        result["success"] = True
                        result["image_path"] = str(temp_path)
                        result["message"] = "图片上传成功"
                        
                except Exception as e:
                    continue
            
            if not result["success"]:
                result["message"] = "未找到上传的文件"
            
        except Exception as e:
            result["message"] = str(e)
        
        return result

    def _handle_theme_apply(self):
        """应用主题"""
        body = self.read_body()
        theme_id = body.get("theme_id", "")

        if not theme_id:
            self.send_json(400, {"error": "缺少 theme_id"})
            return

        # 应用主题
        result = theme_manager.theme_manager.apply_theme(theme_id)

        if result["success"]:
            self.add_timeline("🎨", f"已应用主题: {theme_id}", icon_color="success")
        else:
            self.add_timeline("ERR", f"主题应用失败: {result['message']}", icon_color="danger")

        self.send_json(200, result)

    def _handle_theme_apply_builtin(self):
        """应用内置主题"""
        body = self.read_body()
        theme_id = body.get("theme_id", "")
        css_content = body.get("css", "")
        theme_name = body.get("name", "内置主题")
        dir_name = body.get("dir_name", "")

        if not theme_id:
            self.send_json(400, {"error": "缺少 theme_id"})
            return

        result = {"success": False, "message": ""}

        try:
            theme_data = {}
            theme_dir = None

            # 如果提供了 dir_name，从内置主题目录构建完整 CSS（含背景图）
            if dir_name:
                from theme_manager import BUILTIN_THEMES_DIR
                theme_dir = BUILTIN_THEMES_DIR / dir_name
                if theme_dir.exists():
                    theme_json_path = theme_dir / "theme.json"
                    if theme_json_path.exists():
                        import json as _json
                        theme_data = _json.loads(theme_json_path.read_text(encoding="utf-8"))
                    built_css = theme_manager.theme_manager.build_builtin_theme_css(dir_name)
                    if built_css:
                        css_content = built_css

            # 保存主题配置（包括 CSS 和目录名，供 watcher 自动注入使用）
            config = theme_manager.theme_manager._load_config()
            config["current_theme"] = theme_id
            config["current_theme_name"] = theme_name
            config["last_applied"] = theme_manager.theme_manager._now_iso()
            config["builtin"] = True
            config["builtin_css"] = css_content
            if dir_name:
                config["builtin_dir_name"] = dir_name
            theme_manager.theme_manager._save_config(config)
            theme_manager.theme_manager.current_theme = theme_id

            # 确保 CDP 可用（必要时自动重启 ChatGPT），然后注入主题
            if css_content:
                if theme_manager.theme_manager._ensure_cdp_available(auto_restart=True):
                    # 传入 theme_data 和 theme_dir，确保背景图被正确注入
                    theme_manager.theme_manager._inject_css_to_codex(css_content, theme_data, theme_dir)
                    result["success"] = True
                    result["message"] = "主题已立即应用"
                    self.add_timeline("🎨", f"已应用内置主题: {theme_name}", icon_color="success")
                else:
                    # CDP 不可用，主题已保存
                    result["success"] = True
                    result["message"] = "主题已保存，打开 Codex 后生效"
                    self.add_timeline("🎨", f"已保存内置主题: {theme_name}", icon_color="info")
            else:
                result["message"] = "主题 CSS 为空"

        except Exception as e:
            result["message"] = str(e)
            self.add_timeline("ERR", f"内置主题应用失败: {str(e)}", icon_color="danger")

        self.send_json(200, result)

    def _handle_theme_restore(self):
        """恢复官方外观"""
        result = theme_manager.theme_manager.restore_default()

        if result["success"]:
            self.add_timeline("🔄", "已恢复官方外观", icon_color="info")
        else:
            self.add_timeline("ERR", f"恢复失败: {result['message']}", icon_color="danger")

        self.send_json(200, result)

    # ─── 静态文件 ───

    def _serve_file(self, path: Path, content_type: str):
        if not path.exists():
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        # 禁用缓存，保证前端页面/资源修改后刷新立即生效
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
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
        try:
            self.httpd = ReusableThreadingHTTPServer((HOST, PORT), APIHandler)
        except OSError as e:
            msg = f"控制 API 端口 {PORT} 已被占用（{e}）。可能已有另一个 Codex 助手实例正在运行，请先退出后再启动。"
            print(msg, file=sys.stderr, flush=True)
            raise RuntimeError(msg) from e
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


def shutdown_and_restore():
    """停止适配器并还原 Codex 配置（供窗口关闭/进程退出时调用）。

    之前关闭窗口只杀进程、不还原 config.toml，导致 config.toml 里残留
    model_provider = "codex_helper_adapter"，官方 Codex 启动时报
    "Model provider codex_helper_adapter not found"。这里统一做清理。

    还原后启动守门进程占用 18667，让仍指向本地适配器的历史对话收到
    明确指引（而非 502 Unknown error）。
    """
    try:
        if APIHandler.adapter_runner:
            APIHandler.adapter_runner.stop()
            APIHandler.adapter_runner = None
    except Exception:
        pass
    try:
        core.restore_openai_config()
    except Exception:
        pass
    try:
        core.spawn_gatekeeper()
    except Exception:
        pass


if __name__ == "__main__":
    web_server.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        web_server.stop()
