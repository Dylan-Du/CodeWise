"""核心逻辑：配置管理 + Codex助手 启停 + 多 provider 路由。GUI 调用本模块。

加新 provider 只需要在 PROVIDERS 字典里加一行；其它代码不用动。
"""
import json
import os
import re
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
# 持久化到用户目录，避免重启丢失配置
CC_SWITCH_DIR = HOME / ".codex-helper" / "data"
CC_SWITCH_DIR.mkdir(parents=True, exist_ok=True)
CODEX_DIR = HOME / ".codex"
CODEX_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_TOML = CODEX_DIR / "config.toml"
BACKUP_TOML = CODEX_DIR / "config.toml.openai-backup"
AUTH_JSON = CODEX_DIR / "auth.json"
MODEL_CATALOG_JSON = CODEX_DIR / "codex-helper-model-catalog.json"
# Codex 桌面版门控要求模型目录字段完整（含 base_instructions 等），
# 否则选择器不显示自定义模型。这里从 Codex 内置模板（gpt-5.5）复制完整结构。
if getattr(sys, "_MEIPASS", None):
    _RESOURCE_BASE = Path(sys._MEIPASS)
else:
    _RESOURCE_BASE = Path(__file__).parent.parent
MODEL_TEMPLATE_JSON = _RESOURCE_BASE / "assets" / "codex-model-template.json"
ADAPTER_JSON = CC_SWITCH_DIR / "codex-helper-config.json"
KEYS_JSON = CC_SWITCH_DIR / "switcher-keys.json"
CUSTOM_JSON = CC_SWITCH_DIR / "switcher-custom-providers.json"
# 首次切入 Codex助手 前，用户官方配置的顶层字段快照（model 等）
OFFICIAL_SNAPSHOT_JSON = CC_SWITCH_DIR / "official-snapshot.json"

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
     "upstream": "https://xn--xhqu89o.cc/v1/chat/completions",
     "key_url": "https://xn--xhqu89o.cc/"},
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
    # DeepSeek 官方方案的关键字段：强制走 API Key 认证，跳过 ChatGPT 账号登录。
    # 否则 Codex 桌面版会用官方 ChatGPT 登录态走 api.openai.com，触发官方账号
    # 「使用上限」限流。参考 https://api-docs.deepseek.com/zh-cn/quick_start/agent_integrations/codex
    "preferred_auth_method": "apikey",
    "forced_login_method": "api",
}
PROVIDER_BLOCK = {
    "name": "Codex助手 Adapter",
    "base_url": f"http://{ADAPTER_HOST}:{ADAPTER_PORT}/v1",
    "wire_api": "responses",
    # 关键：不要设置 requires_openai_auth（默认 false）。之前误设为 true 会导致
    # Codex 桌面版认为"需要 OpenAI 认证"，用官方 token 走 api.openai.com，触发
    # 官方账号限流。DeepSeek 官方方案：不设 requires_openai_auth，用
    # experimental_bearer_token 让 Codex 用第三方 token 走 base_url（本地适配器
    # 18667）；配合顶层 forced_login_method="api" 跳过 ChatGPT 登录。适配器会
    # 忽略这个占位 token，改用 config 里用户填的真实 key。
    "experimental_bearer_token": "sk-codex-helper-local",
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


def _write_model_catalog(model: str):
    """生成 Codex 桌面版识别第三方模型所需的模型目录文件。

    Codex 桌面版的模型选择器门控要求模型目录字段完整（含 base_instructions、
    model_messages、support_verbosity、context_window 等 36+ 字段），否则不显示
    自定义模型。因此从 Codex 内置模板（gpt-5.5）复制完整结构，只替换模型标识。
    """
    ensure_dirs()
    try:
        template = json.loads(MODEL_TEMPLATE_JSON.read_text(encoding="utf-8"))
    except Exception:
        # 模板缺失时回退到最小可用结构（仅 CLI 可用，桌面版可能仍不显示）
        template = {
            "slug": "__MODEL__",
            "display_name": "__MODEL__",
            "description": "__MODEL__",
            "default_reasoning_level": "high",
            "supported_reasoning_levels": [
                {"effort": "none", "description": "Think-Off"},
                {"effort": "low", "description": "Fast responses with lighter reasoning"},
                {"effort": "medium", "description": "Balances speed and reasoning depth"},
                {"effort": "high", "description": "Greater reasoning depth"},
            ],
            "shell_type": "shell_command",
            "visibility": "list",
            "supported_in_api": True,
            "priority": 0,
        }
    for key in ("slug", "display_name", "description"):
        if key in template:
            template[key] = model
    catalog = {"models": [template]}
    MODEL_CATALOG_JSON.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def apply_codex_config(model: str):
    """字段级合并，不冲掉用户其他配置。"""
    ensure_dirs()
    if CONFIG_TOML.exists():
        doc = tomlkit.parse(CONFIG_TOML.read_text(encoding="utf-8"))
    else:
        doc = tomlkit.document()

    # 保存"切走前的官方顶层字段"快照（仅首次切入时保存）。还原时恢复，
    # 避免每次切回官方后 Codex 因缺少 model 字段而反复弹出模型选择。
    try:
        if not OFFICIAL_SNAPSHOT_JSON.exists():
            prev_model = doc.get("model")
            snap = {}
            if prev_model and str(prev_model) != model:
                snap["model"] = str(prev_model)
            prev_effort = doc.get("model_reasoning_effort")
            if prev_effort is not None:
                snap["model_reasoning_effort"] = str(prev_effort)
            if snap:
                OFFICIAL_SNAPSHOT_JSON.write_text(
                    json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8"
                )
    except Exception:
        pass

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

    # 生成模型目录文件，并把 model_catalog_json 写入顶层和 provider 块
    # （Codex 桌面版靠它才能在选择器里显示第三方模型，见 openai/codex#32349）
    _write_model_catalog(model)
    catalog_path = str(MODEL_CATALOG_JSON)
    doc["model_catalog_json"] = catalog_path
    block["model_catalog_json"] = catalog_path

    content = tomlkit.dumps(doc)

    # 直接写入
    try:
        CONFIG_TOML.write_text(content, encoding="utf-8")
        # auth.json：仅当完全不存在时才写入占位 API Key（兼容从未登录的场景）。
        # 现在走 DeepSeek 官方方案：config.toml 里设 forced_login_method="api" +
        # preferred_auth_method="apikey"，强制用 provider 块的 experimental_bearer_token
        # 认证，跳过 ChatGPT 账号登录。auth.json 的官方登录态已无影响，无需覆盖。
        if not AUTH_JSON.exists():
            auth_content = json.dumps({"OPENAI_API_KEY": "sk-codex-helper-local"}, indent=2)
            AUTH_JSON.write_text(auth_content, encoding="utf-8")
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
    """切回 OpenAI 官方：字段级清理 Codex助手 写入的顶层字段。

    不再整体覆盖旧备份（备份可能早已过时，会覆盖用户或其它工具后来新增的
    plugins、projects、marketplaces 等配置）。改为从当前 config.toml 里精确
    删除 Codex助手 写入的顶层字段。

    关键：必须保留 [model_providers.codex_helper_adapter] 段！Codex 桌面版把
    每个对话串的 model_provider 持久化在本地数据库（state sqlite）里，历史
    对话串恢复时会按这个 provider id 去 config.toml 找对应段。如果切回官方时
    把这个段删掉，那些在 Codex助手 模式下创建的对话串就会报
    "Model provider codex_helper_adapter not found"，无法重新打开。
    参考 openai/codex#22484 与 cc-switch#5398。
    """
    if not CONFIG_TOML.exists():
        return "config.toml 不存在，无需还原。"

    try:
        doc = tomlkit.parse(CONFIG_TOML.read_text(encoding="utf-8"))
    except Exception as e:
        # 解析失败时回退到整体复制备份（尽力而为）
        if BACKUP_TOML.exists():
            shutil.copy2(str(BACKUP_TOML), str(CONFIG_TOML))
            return f"config.toml 解析失败，已从备份整体还原（{e}）。"
        return f"config.toml 解析失败且无备份: {e}"

    # 1. 删除顶层 Codex助手 写入的字段。删除 model / model_provider 后，
    #    新对话会回退到官方默认 provider；但保留 provider 段定义，让历史
    #    对话串仍能恢复（见函数 docstring）。
    for key in (
        "model",
        "model_provider",
        "model_catalog_json",
        "preferred_auth_method",
        "forced_login_method",
        "disable_response_storage",
        "model_reasoning_effort",
    ):
        if key in doc:
            del doc[key]

    # 1.5 恢复"切走前的官方顶层字段"快照（model 等），避免 Codex 每次新
    #     对话都因缺少 model 字段而弹出模型选择器。
    restored_model = False
    try:
        if OFFICIAL_SNAPSHOT_JSON.exists():
            snap = json.loads(OFFICIAL_SNAPSHOT_JSON.read_text(encoding="utf-8"))
            if snap.get("model"):
                doc["model"] = str(snap["model"])
                restored_model = True
            if snap.get("model_reasoning_effort"):
                doc["model_reasoning_effort"] = str(snap["model_reasoning_effort"])
    except Exception:
        pass

    # 2. 注意：不删除 [model_providers.codex_helper_adapter] 段。
    #    保留它作为历史对话串的 provider 别名，避免恢复对话串时报
    #    "Model provider codex_helper_adapter not found"。

    # 3. 写回
    try:
        CONFIG_TOML.write_text(tomlkit.dumps(doc), encoding="utf-8")
    except OSError as e:
        return f"还原失败: {e}"

    # 4. 如果 auth.json 是我们创建的占位文件，删除它
    if AUTH_JSON.exists():
        try:
            auth_data = json.loads(AUTH_JSON.read_text(encoding="utf-8"))
            if auth_data.get("OPENAI_API_KEY") == "sk-codex-helper-local":
                AUTH_JSON.unlink()
        except Exception:
            pass

    # 5. 把历史对话串从 codex_helper_adapter 迁移到 openai：关闭 Codex助手
    #    后继续历史对话才不会再打到 127.0.0.1:18667（502/503 根因）。
    migrate_msg = migrate_threads_to_openai()

    return ("已从 config.toml 移除 Codex助手 顶层配置，恢复 OpenAI 官方。"
            + ("已恢复切走前的官方模型设置。" if restored_model else "")
            + migrate_msg)


# ---------- 历史对话迁移（切官方时把第三方对话串迁移到官方） ----------

THREAD_PROVIDER_ADAPTER = "codex_helper_adapter"
THREAD_PROVIDER_OPENAI = "openai"
THREAD_PROVIDER_OPENAI_HTTP = "openai_http"
# Codex 桌面版官方默认模型（threads 表里官方对话的常见取值）
OFFICIAL_DEFAULT_MODEL = "gpt-5.6-luna"

# 第三方 provider id 集合（这些对话串在关闭 Codex助手 后都无法续聊，
# 切官方时必须全部迁移到 openai）。codex_helper_adapter 是主适配器；
# stepfun_codex_adapter / custom 是用户添加的自定义适配器/自定义 provider。
THIRD_PARTY_PROVIDERS = (
    THREAD_PROVIDER_ADAPTER,
    "stepfun_codex_adapter",
    "custom",
)

# Codex助手 本地为 Response item 生成的伪造 id 格式：rs_/msg_/fc_ + 32 位 hex
# （见 adapter.output_from_chat_message）。官方后端未持久化这类 id，切官方续聊
# 时按 id 引用会 404，迁移时须删除。官方格式 id（rs_resp_<uuid>、resp_<uuid>_msg、
# fc_call_XX_<base62>）不匹配本正则，会原样保留。
FAKE_ITEM_ID_RE = re.compile(r"^(rs|msg|fc)_[0-9a-f]{32}$")


def _strip_responses_item_content(obj):
    """递归清理 Responses item 中官方 API 不允许的 content 数组。

    官方 Responses API 对 reasoning / function_call 输入 item 校验 content 长度
    最大为 0（只允许空数组或省略该字段）。旧版 Codex助手 生成的 reasoning item
    带 content: [{type: "reasoning_text", ...}]，Codex 存盘后切回官方续聊时原样
    重放为 input，官方校验报「Invalid 'input[n].content': array too long.
    Expected an array with maximum length 0, but got an array with length 1
    instead.」。这里递归清理所有 type 为 reasoning / function_call 的 item。

    返回是否发生了修改。幂等：已清理的条目返回 False。
    """
    if isinstance(obj, dict):
        modified = False
        typ = obj.get("type")
        if typ in ("reasoning", "function_call"):
            c = obj.get("content")
            if isinstance(c, list) and len(c) > 0:
                # 删除字段而不是置空数组：官方接受「缺省或空数组」两种形态，
                # 删除后条目更接近官方原生格式；输入侧解析有 summary 兜底。
                obj.pop("content", None)
                modified = True
        for v in obj.values():
            if _strip_responses_item_content(v):
                modified = True
        return modified
    if isinstance(obj, list):
        modified = False
        for v in obj:
            if _strip_responses_item_content(v):
                modified = True
        return modified
    return False


def _strip_fake_item_ids(obj):
    """递归移除 Response item 上本地伪造的 id 字段。

    背景（重要）：Codex助手 在转发第三方模型响应时，为 reasoning / message /
    function_call item 生成本地 id：rs_<hex32> / msg_<hex32> / fc_<hex32>
    （见 adapter.output_from_chat_message）。这些 id 从未在官方后端持久化
    （官方 Responses API 在 store=false 时不会把 input item 落库）。切回官方
    续聊时，Codex 把这些带 id 的 item 原样重放为 input，官方 API 按「引用已
    存储 item」解析 id，找不到就报：
      unexpected status 404 Not Found: Item with id 'rs_08ee...' not found.
      Items are not persisted when store is set to false. Try again with
      store set to true, or remove this item from your input.

    修复：删除这些伪造 id，让 item 变成纯内联输入（官方 API 对内联 item 直接
    用内容、按需分配新 id，不再按 id 查存储，因此不会再 404）。

    只删除匹配伪造格式（^(rs|msg|fc)_[0-9a-f]{32}$）的 id：
      - 官方格式 id（rs_resp_<uuid> / resp_<uuid>_msg / fc_call_XX_<base62>）
        是官方后端见过/可解析的 id，保留不动；
      - call_id / tool_call_id 是 function_call 与 function_call_output 的
        配对键（官方按 call_id 关联工具调用，不按 id 查存储），一律保留。

    返回是否发生了修改。幂等：已清理的条目返回 False。
    """
    if isinstance(obj, dict):
        modified = False
        i = obj.get("id")
        if isinstance(i, str) and FAKE_ITEM_ID_RE.match(i):
            obj.pop("id", None)
            modified = True
        for v in obj.values():
            if _strip_fake_item_ids(v):
                modified = True
        return modified
    if isinstance(obj, list):
        modified = False
        for v in obj:
            if _strip_fake_item_ids(v):
                modified = True
        return modified
    return False


def _rewrite_rollout_jsonl(path: Path) -> int:
    """改写单个 rollout jsonl：把 session_meta 的 model_provider 改为 openai，
    把 turn_context 里非官方模型名改为官方默认模型，清理 reasoning /
    function_call item 中官方 API 不允许的 content 数组，并删除本地伪造的
    item id（rs_/msg_/fc_ + hex32，切官方续聊按 id 引用会 404）。

    返回改写的行数（0 表示没有需要改写的行）。文件先写临时文件再原子替换，
    保持 UTF-8 编码与 compact JSON 格式（与 Codex 原始格式一致）。
    """
    changed = 0
    lines_out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                lines_out.append(line)
                continue
            try:
                obj = json.loads(line)
            except Exception:
                # 解析失败的行原样保留，不破坏文件
                lines_out.append(line)
                continue
            t = obj.get("type")
            modified = False
            if t == "session_meta":
                payload = obj.get("payload")
                if isinstance(payload, dict) and payload.get("model_provider") in THIRD_PARTY_PROVIDERS:
                    payload["model_provider"] = THREAD_PROVIDER_OPENAI
                    modified = True
            elif t == "turn_context":
                payload = obj.get("payload")
                if isinstance(payload, dict):
                    m = payload.get("model")
                    if isinstance(m, str) and not m.startswith("gpt-"):
                        payload["model"] = OFFICIAL_DEFAULT_MODEL
                        modified = True
            # 全行递归清理 reasoning/function_call 的 content（任何事件类型都处理，
            # 幂等）。官方 API 拒绝非空 content 数组，这是切官方续聊 400 的根因。
            if _strip_responses_item_content(obj):
                modified = True
            # 全行递归删除本地伪造 item id（rs_/msg_/fc_ + hex32）。切官方续聊时
            # 官方 API 按 id 引用未持久化 item 会 404，删除后 item 变纯内联。
            if _strip_fake_item_ids(obj):
                modified = True
            if modified:
                lines_out.append(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
                changed += 1
            else:
                lines_out.append(line)
    if changed:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
        tmp.replace(path)
    return changed


def migrate_threads_to_openai() -> str:
    """切回官方时，把历史对话串从第三方 provider 迁移到 openai。

    背景（重要）：Codex 桌面版把每个对话串的 model_provider 权威地持久化在
    两处：
      1) ~/.codex/state_*.sqlite 的 threads 表（model_provider / model 字段）；
      2) ~/.codex/sessions/.../rollout-*.jsonl 的 session_meta / turn_context
         事件（恢复对话时桌面版以 jsonl 为准，并会把 provider 回写到 sqlite）。
    只改 sqlite 会被桌面版按 jsonl 回写覆盖（实测确认）。因此必须同时改写
    jsonl，才能让关闭 Codex助手 后"继续上个任务"真正走官方、不再 502/503。

    额外兜底（重要）：桌面版恢复对话以 jsonl 为权威，而 sqlite 可能因历史
    迁移已标记为 openai、导致按 sqlite 扫描不到该对话串。因此除 sqlite 驱动
    的迁移外，还会独立扫描全部 rollout-*.jsonl，凡最后一个 session_meta 的
    model_provider 仍为第三方就一律改写，彻底覆盖"sqlite 已 openai 但 jsonl
    仍是第三方"的漏网场景（曾导致退出 Codex助手 后继续上个任务仍 503）。

    失败不影响切官方主流程，只返回描述信息供 UI 展示。
    """
    import sqlite3

    migrated = 0
    jsonl_fixed = 0
    errors = []

    # 遍历所有 state_*.sqlite（文件名带版本号，如 state_5.sqlite）
    for db_path in sorted(CODEX_DIR.glob("state_*.sqlite")):
        try:
            conn = sqlite3.connect(str(db_path), timeout=5)
            conn.execute("PRAGMA busy_timeout = 5000")
            try:
                rows = conn.execute(
                    "SELECT id, model, rollout_path FROM threads "
                    "WHERE model_provider IN (?, ?, ?)",
                    THIRD_PARTY_PROVIDERS,
                ).fetchall()
                for tid, model, rollout_path in rows:
                    new_model = model if (model or "").startswith("gpt-") else OFFICIAL_DEFAULT_MODEL
                    # 1) 改写 rollout jsonl（权威来源，防止桌面版回写覆盖）
                    if rollout_path:
                        rp = Path(rollout_path)
                        if rp.exists():
                            try:
                                jsonl_fixed += _rewrite_rollout_jsonl(rp)
                            except Exception as e:
                                errors.append(f"{rp.name}: {e}")
                        # 文件不存在则跳过 jsonl 改写，sqlite 仍照常更新
                    # 2) 更新 sqlite threads 表
                    conn.execute(
                        "UPDATE threads SET model_provider = ?, model = ? WHERE id = ?",
                        (THREAD_PROVIDER_OPENAI, new_model, tid),
                    )
                    migrated += 1
                conn.commit()
            except sqlite3.OperationalError as e:
                # 桌面版可能正持有写锁；记录但不让切官方失败
                errors.append(f"{db_path.name}: {e}")
            finally:
                conn.close()
        except Exception as e:
            errors.append(f"{db_path.name}: {e}")

    # 独立扫描全部 rollout jsonl（不依赖 sqlite 状态）。
    # 场景：08-22 批次对话的 sqlite 行早已标记 openai，但 jsonl 仍是第三方，
    # 旧逻辑按 sqlite 扫描不到它们 → 继续上个任务仍走 18667 → 503。
    # _rewrite_rollout_jsonl 幂等：已是 openai 的文件返回 0，可安全全量调用。
    jsonl_scan_files = 0
    jsonl_scan_lines = 0
    for rp in sorted(CODEX_DIR.glob("sessions/**/rollout-*.jsonl")):
        try:
            n = _rewrite_rollout_jsonl(rp)
            if n:
                jsonl_scan_lines += n
                jsonl_scan_files += 1
        except Exception as e:
            errors.append(f"{rp.name}: {e}")

    parts = []
    if migrated:
        parts.append(f"已将 {migrated} 个历史对话迁移到官方模型（继续对话不再报错）")
    if jsonl_fixed:
        parts.append(f"已改写 {jsonl_fixed} 条会话记录，桌面版恢复对话时将直接走官方")
    if jsonl_scan_files:
        parts.append(
            f"已额外修复 {jsonl_scan_files} 个旧会话记录文件（{jsonl_scan_lines} 行），"
            "这些记录此前在数据库中已标记官方但文件中仍为第三方，现一并修正"
        )
    if errors:
        parts.append("部分历史对话迁移失败: " + "; ".join(errors))
    return "。" + "。".join(parts) if parts else ""



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
        for _ in range(8):
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
        for _ in range(5):
            if not adapter_running():
                break
            time.sleep(0.1)
        self.log("Codex助手 已停止。")


# ---------- 守门服务（gatekeeper） ----------

GATEKEEPER_PID = CC_SWITCH_DIR / "gatekeeper.pid"

GATEKEEPER_MESSAGE = (
    "Codex助手 已停止：此对话使用第三方模型创建，无法直接切到官方。"
    "请重新打开 Codex助手 继续使用第三方模型，或在 Codex 中新建对话使用官方模型。"
)


class _GatekeeperHandler(adapter.Handler):
    """占用 18667 的守门 Handler：返回明确指引，替代连接拒绝/502 Unknown error。

    Codex 桌面版把每个对话串的 model_provider 持久化在本地数据库，历史对话
    恢复时会固定请求 http://127.0.0.1:18667。Codex助手 停止后若端口无服务，
    Codex 只能报 "502 Bad Gateway: Unknown error"。守门进程返回标准 OpenAI
    错误格式（error.message），让 Codex 界面直接显示中文指引。

    自愈：收到模型请求说明仍有历史对话指向本端口（用户继续第三方会话时
    Codex 界面会显示"重新连接"）。首次收到请求时自动把所有第三方 provider
    的对话迁移到官方（幂等、可复用 migrate_threads_to_openai），这样用户
    关闭该对话重新打开后即走官方，不再持续报错。进程内只迁移一次，避免
    每次重试都全量扫描。
    """

    on_usage = None
    on_error = None
    _migrated_once = False

    def do_GET(self):
        self.send_json(503, {"error": {"message": GATEKEEPER_MESSAGE, "type": "server_error"}})

    def do_POST(self):
        try:
            length = int(self.headers.get("content-length", "0"))
            if length:
                self.rfile.read(length)
        except Exception:
            pass
        message = GATEKEEPER_MESSAGE
        if not _GatekeeperHandler._migrated_once:
            _GatekeeperHandler._migrated_once = True
            try:
                migrate_threads_to_openai()
                message = (
                    GATEKEEPER_MESSAGE
                    + " 已自动将此对话迁移到官方模型：请关闭该对话后重新打开，即可继续使用官方模型。"
                )
            except Exception:
                pass  # 迁移失败不影响返回指引
        self.send_json(503, {"error": {"message": message, "type": "server_error"}})


def run_gatekeeper():
    """独立守门进程入口：占用 18667 直到被清理。"""
    try:
        httpd = ReusableHTTPServer((ADAPTER_HOST, ADAPTER_PORT), _GatekeeperHandler)
    except OSError:
        return  # 端口被占（适配器还在或别人占用），直接退出
    try:
        GATEKEEPER_PID.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if GATEKEEPER_PID.exists() and GATEKEEPER_PID.read_text().strip() == str(os.getpid()):
                GATEKEEPER_PID.unlink()
        except Exception:
            pass


def spawn_gatekeeper() -> bool:
    """启动守门子进程（detached）。Codex助手 停止后由它接管 18667。"""
    try:
        stop_gatekeeper()
    except Exception:
        pass
    # 等端口释放
    for _ in range(10):
        if not adapter_running():
            break
        time.sleep(0.1)
    if adapter_running():
        return False  # 仍有服务在 18667，无需守门
    import subprocess
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--gatekeeper"]
    else:
        cmd = [sys.executable, str(Path(__file__).resolve()), "--gatekeeper"]
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        return False
    # 等守门进程就绪
    for _ in range(20):
        time.sleep(0.1)
        try:
            if GATEKEEPER_PID.exists():
                return True
        except Exception:
            pass
    return False


def stop_gatekeeper():
    """停止守门进程（按 pid 文件）。"""
    try:
        if GATEKEEPER_PID.exists():
            pid = int(GATEKEEPER_PID.read_text().strip())
            if pid != os.getpid():
                os.kill(pid, 15)
            GATEKEEPER_PID.unlink()
    except Exception:
        pass


def clear_adapter_port():
    """清理 18667 端口的所有外部占用者（守门孤儿进程/残留服务），供适配器启动前调用。"""
    stop_gatekeeper()
    import subprocess
    try:
        out = subprocess.run(
            ["lsof", "-tiTCP:18667", "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        for pid_s in out.split():
            try:
                pid = int(pid_s)
                if pid != os.getpid():
                    os.kill(pid, 15)
            except Exception:
                pass
    except Exception:
        pass
    for _ in range(10):
        if not adapter_running():
            return True
        time.sleep(0.1)
    return not adapter_running()


if __name__ == "__main__":
    # 源码模式独立入口：python core.py --gatekeeper
    if "--gatekeeper" in sys.argv:
        run_gatekeeper()
