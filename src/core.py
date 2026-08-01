"""核心逻辑：配置管理 + Codex助手 启停 + 多 provider 路由。GUI 调用本模块。

加新 provider 只需要在 PROVIDERS 字典里加一行；其它代码不用动。
"""
import json
import os
import shutil
import socket
import sys
import threading
import time
import tempfile
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer, HTTPServer

class ReusableHTTPServer(ThreadingHTTPServer):
    """支持端口复用，避免 stop 后重启时端口 TIME_WAIT 导致绑定失败。"""
    allow_reuse_address = True
    allow_reuse_port = True
from pathlib import Path

import tomlkit

import adapter

HOME = Path(os.path.expanduser("~"))
# 使用临时目录避免 macOS 沙箱限制
CC_SWITCH_DIR = Path(tempfile.gettempdir()) / "cc-switch"
CODEX_DIR = HOME / ".codex"
CONFIG_TOML = CODEX_DIR / "config.toml"
BACKUP_TOML = CODEX_DIR / "config.toml.openai-backup"
ADAPTER_JSON = CC_SWITCH_DIR / "codex-helper-config.json"
KEYS_JSON = CC_SWITCH_DIR / "switcher-keys.json"
CUSTOM_JSON = CC_SWITCH_DIR / "switcher-custom-providers.json"

ADAPTER_HOST = "127.0.0.1"
ADAPTER_PORT = 18667
HEALTH_URL = f"http://{ADAPTER_HOST}:{ADAPTER_PORT}/health"


# ---------- Provider 注册表（未来加新家在这里加一行） ----------

PROVIDERS = {
    "deepseek": {
        "label": "DeepSeek",
        "upstream": "https://api.deepseek.com/chat/completions",
        "key_url": "https://platform.deepseek.com",
        "models": ["deepseek-v4-pro", "deepseek-v4-flash"],
    },
    "kimi": {
        "label": "Kimi",
        "upstream": "https://api.moonshot.cn/v1/chat/completions",
        "key_url": "https://platform.moonshot.cn",
        "models": [
            "kimi-k3",
            "kimi-k2.7-code",
            "kimi-k2.6",
        ],
    },
}

# ---------- 自定义提供商预设模板（GUI 弹窗里给用户挑） ----------
# 不直接出现在主下拉里；用户点"添加自定义"选模板后，base_url 自动填充。
PRESETS = [
    {"label": "APINest", "model": "",
     "upstream": "https://apinest.eu.cc/v1/chat/completions",
     "key_url": "https://apinest.eu.cc"},
    {"label": "智谱", "model": "glm-5.2",
     "upstream": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
     "key_url": "https://open.bigmodel.cn"},
    {"label": "智谱", "model": "glm-5.1",
     "upstream": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
     "key_url": "https://open.bigmodel.cn"},
    {"label": "智谱", "model": "glm-5-turbo",
     "upstream": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
     "key_url": "https://open.bigmodel.cn"},
    {"label": "通义", "model": "qwen3.8-max-preview",
     "upstream": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
     "key_url": "https://dashscope.console.aliyun.com"},
    {"label": "通义", "model": "qwen3.7-max",
     "upstream": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
     "key_url": "https://dashscope.console.aliyun.com"},
    {"label": "通义", "model": "qwen3.7-plus",
     "upstream": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
     "key_url": "https://dashscope.console.aliyun.com"},
    {"label": "小米MIMO", "model": "mimo-v2.5-pro",
     "upstream": "https://api.xiaomimimo.com/v1/chat/completions",
     "key_url": "https://platform.xiaomimimo.com"},
    {"label": "StepFun", "model": "step-3.7-flash",
     "upstream": "https://api.stepfun.com/v1/chat/completions",
     "key_url": "https://platform.stepfun.com"},
    {"label": "LongCat", "model": "LongCat-2.0",
     "upstream": "https://api.longcat.chat/openai/v1/chat/completions",
     "key_url": "https://longcat.ai"},
    {"label": "Claude", "model": "claude-opus-5",
     "upstream": "https://api.anthropic.com/v1/messages",
     "key_url": "https://console.anthropic.com"},
    {"label": "Gemini", "model": "gemini-3.6-flash",
     "upstream": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent",
     "key_url": "https://aistudio.google.com"},
    {"label": "自定义", "model": "",
     "upstream": "", "key_url": ""},
]


# ---------- 自定义提供商持久化 ----------

def load_custom() -> list[dict]:
    if not CUSTOM_JSON.exists():
        return []
    try:
        data = json.loads(CUSTOM_JSON.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_custom_list(items: list[dict]):
    ensure_dirs()
    CUSTOM_JSON.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_custom(label: str, model: str, upstream: str, key_url: str, api_key: str):
    items = load_custom()
    items.append({
        "label": label.strip(),
        "model": model.strip(),
        "upstream": upstream.strip(),
        "key_url": key_url.strip(),
        "api_key": api_key.strip(),
    })
    save_custom_list(items)


def remove_custom(index: int):
    items = load_custom()
    if 0 <= index < len(items):
        items.pop(index)
        save_custom_list(items)


# ---------- 统一路由 ----------

def resolve_route(route_type: str, model: str) -> dict:
    """返回 {label, upstream, key_url, api_key}。
    route_type:
      - 内置 provider id（'deepseek' / 'kimi' / ...）
      - 'custom:<index>' 指向 load_custom()[index]
    """
    if route_type.startswith("custom:"):
        idx = int(route_type[7:])
        items = load_custom()
        if idx >= len(items):
            raise ValueError(f"自定义条目 {idx} 不存在（可能被删了）")
        it = items[idx]
        return {
            "label": it["label"], "upstream": it["upstream"],
            "key_url": it.get("key_url", ""), "api_key": it.get("api_key", ""),
        }
    if route_type not in PROVIDERS:
        raise ValueError(f"未知 provider: {route_type}")
    info = PROVIDERS[route_type]
    return {
        "label": info["label"], "upstream": info["upstream"],
        "key_url": info["key_url"], "api_key": load_key(route_type),
    }


def update_custom_key(index: int, api_key: str):
    """单独更新自定义条目的 api_key（GUI 编辑用）。"""
    items = load_custom()
    if 0 <= index < len(items):
        items[index]["api_key"] = api_key.strip()
        save_custom_list(items)


def flat_models() -> list[tuple[str, str, str]]:
    """返回 (display_label, model_id, route_type) 列表，给下拉框用。
    route_type 是 'deepseek'/'kimi'/.../'custom:<idx>'。
    """
    out = []
    for pid, info in PROVIDERS.items():
        for m in info["models"]:
            out.append((f"{info['label']} · {m}", m, pid))
    for idx, it in enumerate(load_custom()):
        label = f"{it['label']} · {it['model']} ✦"
        out.append((label, it["model"], f"custom:{idx}"))
    return out


def model_to_provider(model: str):
    for pid, info in PROVIDERS.items():
        if model in info["models"]:
            return pid
    return None


def provider_info(pid: str) -> dict:
    return PROVIDERS[pid]


# ---------- TOML 字段（与 provider 无关） ----------

CODEX_TOML_FIELDS = {
    "model_provider": "codex_helper_adapter",
    "model_reasoning_effort": "high",
    "disable_response_storage": True,
}
PROVIDER_BLOCK = {
    "name": "Codex助手 Adapter",
    "base_url": f"http://{ADAPTER_HOST}:{ADAPTER_PORT}/v1",
    "wire_api": "responses",
    "requires_openai_auth": False,
    "request_max_retries": 2,
    "stream_max_retries": 2,
    "stream_idle_timeout_ms": 300000,
}


# ---------- 状态检测 ----------

def adapter_running() -> bool:
    try:
        with socket.create_connection((ADAPTER_HOST, ADAPTER_PORT), timeout=0.5):
            return True
    except OSError:
        return False


def adapter_healthy() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=1.0) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def codex_in_adapter_mode() -> bool:
    """是否已切到 Codex助手（任何 provider 都算）。"""
    if not CONFIG_TOML.exists():
        return False
    try:
        doc = tomlkit.parse(CONFIG_TOML.read_text(encoding="utf-8"))
    except Exception:
        return False
    return doc.get("model_provider") == "codex_helper_adapter"


def current_model():
    if not CONFIG_TOML.exists():
        return None
    try:
        doc = tomlkit.parse(CONFIG_TOML.read_text(encoding="utf-8"))
    except Exception:
        return None
    m = doc.get("model")
    return str(m) if m else None


# ---------- Key 多 provider 存取 ----------

def ensure_dirs():
    CC_SWITCH_DIR.mkdir(parents=True, exist_ok=True)
    CODEX_DIR.mkdir(parents=True, exist_ok=True)


def _load_keys_dict() -> dict:
    if KEYS_JSON.exists():
        try:
            return json.loads(KEYS_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    # 兼容旧版：从 adapter.json 迁移一次 DeepSeek key
    if ADAPTER_JSON.exists():
        try:
            old = json.loads(ADAPTER_JSON.read_text(encoding="utf-8"))
            k = old.get("api_key")
            if k:
                return {"deepseek": k}
        except Exception:
            pass
    return {}


def load_key(provider: str) -> str:
    return _load_keys_dict().get(provider, "")


def save_key(provider: str, key: str):
    ensure_dirs()
    d = _load_keys_dict()
    d[provider] = key
    KEYS_JSON.write_text(
        json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------- Codex助手 + Codex 配置写入 ----------

def write_adapter_json(model: str, route_type: str):
    """根据 route_type 写 Codex助手 配置。支持内置和 custom:<idx>。"""
    ensure_dirs()
    route = resolve_route(route_type, model)
    if not route["api_key"]:
        raise ValueError(f"{route['label']} 的 API Key 未设置")
    if not route["upstream"]:
        raise ValueError(f"{route['label']} 的 Base URL 未设置")
    payload = {
        "subscription": "normal",
        "model": model,
        "upstream": route["upstream"],
        "api_key": route["api_key"],
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    # 重试机制：macOS 上文件可能被短暂锁定
    for attempt in range(5):
        try:
            # 直接写入文件（覆盖）
            ADAPTER_JSON.write_text(content, encoding="utf-8")
            return  # 成功
        except OSError as e:
            if attempt < 4:
                time.sleep(0.2 * (attempt + 1))  # 递增等待
            else:
                raise ValueError(f"写入配置文件失败: {e}")


def backup_config_toml_if_needed() -> bool:
    if not CONFIG_TOML.exists():
        return False
    if BACKUP_TOML.exists():
        return False
    src = str(CONFIG_TOML)
    dest = str(BACKUP_TOML)
    try:
        shutil.copy2(src, dest)
        return True
    except Exception:
        pass
    return False


def apply_codex_config(model: str):
    """字段级合并，不冲掉用户其他配置。"""
    ensure_dirs()
    if CONFIG_TOML.exists():
        doc = tomlkit.parse(CONFIG_TOML.read_text(encoding="utf-8"))
    else:
        doc = tomlkit.document()

    doc["model"] = model
    for k, v in CODEX_TOML_FIELDS.items():
        doc[k] = v

    if "model_providers" not in doc:
        doc["model_providers"] = tomlkit.table()
    providers = doc["model_providers"]
    if "codex_helper_adapter" not in providers:
        providers["codex_helper_adapter"] = tomlkit.table()
    block = providers["codex_helper_adapter"]
    for k, v in PROVIDER_BLOCK.items():
        block[k] = v
    block["name"] = model

    content = tomlkit.dumps(doc)
    
    # 直接写入
    try:
        CONFIG_TOML.write_text(content, encoding="utf-8")
        return
    except OSError as e:
        raise PermissionError(
            f"无法写入 {CONFIG_TOML}: {e}\n"
            f"请尝试以下方法：\n"
            f"1. 在终端运行: chmod 755 ~/.codex\n"
            f"2. 或手动创建: mkdir -p ~/.codex && chmod 755 ~/.codex\n"
            f"3. 或将运行本应用的终端添加到「系统设置 → 隐私与安全性 → 完全磁盘访问权限」"
        )


def restore_openai_config() -> str:
    if not BACKUP_TOML.exists():
        return "未发现备份文件，跳过还原（你的 Codex 配置本来就没被改过）。"
    src = str(BACKUP_TOML)
    dest = str(CONFIG_TOML)
    
    # 直接复制
    try:
        shutil.copy2(src, dest)
        return f"已从 {BACKUP_TOML.name} 还原 config.toml。"
    except Exception as e:
        return f"还原失败: {e}\n请手动复制：cp {src} {dest}"


# ---------- Token 用量追踪 ----------

TOKEN_LOG_JSON = CC_SWITCH_DIR / "token-usage.json"


class TokenTracker:
    """线程安全的 token 用量追踪器。adapter 每次请求后调用 record()。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.total_input: int = 0
        self.total_output: int = 0
        self.total_cache: int = 0
        self.history: list[dict] = []
        self.per_model: dict[str, dict] = {}
        self._load()

    def record(self, model: str, input_tokens: int, output_tokens: int, cache_tokens: int = 0):
        with self.lock:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            self.total_input += input_tokens
            self.total_output += output_tokens
            self.total_cache += cache_tokens
            self.history.append({
                "timestamp": ts,
                "model": model,
                "input": input_tokens,
                "output": output_tokens,
                "cache": cache_tokens,
            })
            if len(self.history) > 200:
                self.history = self.history[-200:]
            # 独立累加按模型分组统计（不受 history 截断影响）
            if model not in self.per_model:
                self.per_model[model] = {
                    "model": model, "calls": 0, "input": 0,
                    "output": 0, "cache": 0, "last_used": ts,
                }
            s = self.per_model[model]
            s["calls"] += 1
            s["input"] += input_tokens
            s["output"] += output_tokens
            s["cache"] += cache_tokens
            s["last_used"] = ts
            self._save()

    def totals(self) -> dict:
        with self.lock:
            return {"input": self.total_input, "output": self.total_output, "cache": self.total_cache}

    def per_model_stats(self) -> dict:
        """返回按模型分组的统计数据（独立累加，不受 history 截断影响）。"""
        with self.lock:
            # 深拷贝避免外部修改
            return {k: dict(v) for k, v in self.per_model.items()}

    def recent(self, n: int = 50) -> list[dict]:
        with self.lock:
            return list(self.history[-n:])

    def clear(self):
        with self.lock:
            self.total_input = self.total_output = self.total_cache = 0
            self.history = []
            self.per_model = {}
            self._save()

    def _load(self):
        if TOKEN_LOG_JSON.exists():
            try:
                d = json.loads(TOKEN_LOG_JSON.read_text(encoding="utf-8"))
                self.total_input = int(d.get("total_input", 0))
                self.total_output = int(d.get("total_output", 0))
                self.total_cache = int(d.get("total_cache", 0))
                self.history = d.get("history", []) if isinstance(d.get("history"), list) else []
                pm = d.get("per_model", {})
                if isinstance(pm, dict):
                    self.per_model = pm
            except Exception:
                pass

    def _save(self):
        ensure_dirs()
        TOKEN_LOG_JSON.write_text(
            json.dumps({
                "total_input": self.total_input,
                "total_output": self.total_output,
                "total_cache": self.total_cache,
                "history": self.history,
                "per_model": self.per_model,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


token_tracker = TokenTracker()


# ---------- 错误追踪器 ----------

ERROR_LOG_JSON = CC_SWITCH_DIR / "error-log.json"


class ErrorTracker:
    """线程安全的错误追踪器。记录调用错误、API 错误等。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.errors: list[dict] = []
        self._load()

    def record(self, model: str, error_type: str, message: str, details: str = ""):
        with self.lock:
            self.errors.append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "model": model,
                "error_type": error_type,
                "message": message,
                "details": details,
            })
            if len(self.errors) > 200:
                self.errors = self.errors[-200:]
            self._save()

    def recent(self, n: int = 50) -> list[dict]:
        with self.lock:
            return list(self.errors[-n:])

    def clear(self):
        with self.lock:
            self.errors = []
            self._save()

    def _load(self):
        if ERROR_LOG_JSON.exists():
            try:
                self.errors = json.loads(ERROR_LOG_JSON.read_text(encoding="utf-8"))
                if not isinstance(self.errors, list):
                    self.errors = []
            except Exception:
                self.errors = []

    def _save(self):
        ensure_dirs()
        ERROR_LOG_JSON.write_text(
            json.dumps(self.errors, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


error_tracker = ErrorTracker()

# ---------- Codex助手 启停（同进程子线程） ----------

class AdapterRunner:
    def __init__(self, log_fn=None, on_usage=None, on_error=None):
        self.httpd = None
        self.thread = None
        self.log = log_fn or (lambda msg: None)
        self.on_usage = on_usage
        self.on_error = on_error

    def start(self) -> bool:
        if self.thread and self.thread.is_alive():
            self.log("Codex助手 已经在跑了。")
            return True
        # 把 usage 回调注入到 adapter Handler
        adapter.Handler.on_usage = self.on_usage
        # 把 error 回调注入到 adapter Handler
        adapter.Handler.on_error = self.on_error if hasattr(self, 'on_error') else None
        try:
            self.httpd = ReusableHTTPServer(
                (adapter.HOST, adapter.PORT), adapter.Handler
            )
        except OSError as e:
            # 端口可能还在 TIME_WAIT，重试几次
            started = False
            for attempt in range(5):
                time.sleep(0.3)
                try:
                    self.httpd = ReusableHTTPServer(
                        (adapter.HOST, adapter.PORT), adapter.Handler
                    )
                    started = True
                    break
                except OSError:
                    continue
            if not started:
                self.log(f"端口 {adapter.PORT} 占用或权限不足：{e}")
                return False
        self.thread = threading.Thread(
            target=self.httpd.serve_forever,
            name="adapter-server",
            daemon=True,
        )
        self.thread.start()
        for _ in range(20):
            if adapter_running():
                self.log(f"Codex助手 已启动：http://{adapter.HOST}:{adapter.PORT}")
                return True
            time.sleep(0.05)
        self.log("Codex助手 启动超时。")
        return False

    def stop(self):
        if not self.httpd:
            return
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except Exception as e:
            self.log(f"停 Codex助手 出错（忽略）：{e}")
        self.httpd = None
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
        # 等待端口完全释放
        for _ in range(20):
            if not adapter_running():
                break
            time.sleep(0.1)
        self.log("Codex助手 已停止。")
