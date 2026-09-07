#!/usr/bin/env python3
# Codex助手 — API 适配器模块
# 将 Codex Responses API 请求转换为 OpenAI Chat Completions 兼容格式
import json
import os
import socket
import sqlite3
import ssl
import time
import threading
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# macOS 上 python.org 的 Python 默认找不到系统根证书,conda 等环境还会用
# SSL_CERT_FILE/SSL_CERT_DIR 污染证书路径,导致 urllib 连 HTTPS 上游时报
# CERTIFICATE_VERIFY_FAILED。这里显式用 certifi 提供的根证书构造 SSL 上下文,
# 让翻译官不依赖系统/终端的证书状态。
try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except Exception:
    # certifi 不可用时退回系统默认(保持原行为)
    _SSL_CONTEXT = ssl.create_default_context()

# ─── SSL 自动重试 & 降级兼容 ───
# 遇到 UNEXPECTED_EOF 等 SSL 瞬时错误时自动重试 1-2 次，
# 重试时降低 TLS 最低版本以兼容老旧服务器 OpenSSL。
_MAX_SSL_RETRIES = 2
_SSL_RETRY_BASE_DELAY = 0.5  # 秒，每次重试递增（0.5s → 1.0s）

# ─── HTTP 网关瞬时错误重试 ───
# 502/503/504 是网关/代理层瞬时错误（如 nginx 超时、服务短暂不可用），
# 重试通常能成功。与 4xx 等永久性错误不同，这些值得自动重试。
_RETRYABLE_HTTP_CODES = {502, 503, 504}

# ─── 输出 token 下限保护 ───
# DeepSeek 等 thinking 模式上游的 max_tokens 是「思维链(reasoning_content)
# + 最终答案(content)」的总预算。Codex 默认 4096 会被思维链耗尽，导致
# content 为空、界面只显示"正在思考"后无输出。此处强制下限，给思维链
# 和最终答案都留出空间。
_MIN_OUTPUT_TOKENS = 16384


def _is_retryable_ssl_error(exc):
    """判断是否为可重试的 SSL/网络瞬时错误。

    可重试的场景：
    - ssl.SSLError: UNEXPECTED_EOF、SSLV3_ALERT、连接被对端重置等
    - ConnectionResetError / ConnectionAbortedError / BrokenPipeError
    - urllib.error.URLError 包装的上述底层错误
    - socket.error: 连接中断类错误

    不可重试的场景：
    - 证书验证失败（CERTIFICATE_VERIFY_FAILED）→ 需在降级上下文中重试
    - HTTPError（4xx/5xx）→ 由调用方处理，不在此函数范围
    """
    if isinstance(exc, ssl.SSLError):
        msg = str(exc).lower()
        reason = str(getattr(exc, "reason", "")).lower()
        combined = f"{msg} {reason}"
        # UNEXPECTED_EOF: 上游在 TLS 握手/传输中意外关闭连接（典型网络抖动）
        if "unexpected_eof" in combined:
            return True
        # SSLV3_ALERT: 上游 SSL 协议层告警（如记录溢出、握手失败）
        if "sslv3_alert" in combined:
            return True
        # 连接被重置/关闭/中断
        if "connection" in combined and ("reset" in combined or "closed" in combined or "aborted" in combined):
            return True
        # 证书验证失败不在此重试（留到降级上下文时再试）
        if "certificate" in combined or "verify" in combined:
            return False
        # 其他 SSLError（如 TLS 握手失败）倾向于重试
        return True

    if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
        return True

    if isinstance(exc, urllib.error.URLError):
        inner = exc.reason
        if isinstance(inner, ssl.SSLError):
            return _is_retryable_ssl_error(inner)
        if isinstance(inner, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return True
        if isinstance(inner, socket.error):
            return True
        msg = str(inner).lower()
        if "unexpected_eof" in msg:
            return True
        if "connection" in msg and ("reset" in msg or "closed" in msg or "refused" in msg):
            return True
        return False

    if isinstance(exc, socket.error):
        return True

    return False


def _create_downgraded_ssl_context():
    """创建降级 SSL 上下文，降低 TLS 最低版本以兼容老旧服务器。

    尝试将 minimum_version 依次设为 TLSv1.0 → TLSv1.1 → TLSv1.2，
    取第一个系统支持的版本。保留证书验证（安全性不降级，仅降级协议版本）。
    """
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = ssl.create_default_context()

    # 依次尝试降低最低 TLS 版本
    for min_ver in (ssl.TLSVersion.TLSv1, ssl.TLSVersion.TLSv1_1, ssl.TLSVersion.TLSv1_2):
        try:
            ctx.minimum_version = min_ver
            break
        except (AttributeError, ValueError):
            continue

    return ctx


# 预创建降级 SSL 上下文（重试时使用，避免运行时开销）
_SSL_CONTEXT_DOWNGRADED = _create_downgraded_ssl_context()

import tempfile
HOST = "127.0.0.1"
PORT = 18667
# 持久化到用户目录，避免重启丢失配置
_CONFIG_DIR = Path(os.path.expanduser("~")) / ".codex-helper" / "data"
_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
# 迁移旧临时目录的配置
_OLD_CONFIG_DIR = Path(tempfile.gettempdir()) / "cc-switch"
if not (_CONFIG_DIR / "codex-helper-config.json").exists() and (_OLD_CONFIG_DIR / "codex-helper-config.json").exists():
    import shutil
    try:
        for f in _OLD_CONFIG_DIR.iterdir():
            shutil.copy2(f, _CONFIG_DIR / f.name)
    except Exception:
        pass
CONFIG_PATH = _CONFIG_DIR / "codex-helper-config.json"
DB_PATH = _CONFIG_DIR / "cc-switch.db"

# 日志文件
_LOG_FILE = _CONFIG_DIR / "adapter-debug.log"
_MAX_LOG_SIZE = 1024 * 1024  # 超过 1MB 自动轮转，防止无限增长

def _log(msg):
    """写入日志文件（带大小轮转）"""
    try:
        if _LOG_FILE.exists() and _LOG_FILE.stat().st_size > _MAX_LOG_SIZE:
            try:
                _LOG_FILE.replace(_LOG_FILE.with_name("adapter-debug.log.old"))
            except Exception:
                _LOG_FILE.unlink(missing_ok=True)
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def load_saved_api_key():
    if not DB_PATH.exists():
        return None
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                """
                select json_extract(settings_config, '$.auth.OPENAI_API_KEY')
                from providers
                where app_type = 'codex' and id = 'codex-helper'
                limit 1
                """
            ).fetchone()
        return row[0] if row and row[0] else None
    except sqlite3.Error:
        return None


def load_config():
    if not CONFIG_PATH.exists():
        return {
            "upstream": "https://api.xiaomimimo.com/v1/chat/completions",
            "model": "mimo-v2.5-pro",
            "subscription": "normal",
        }
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "upstream": data.get("upstream") or "https://api.xiaomimimo.com/v1/chat/completions",
        "model": data.get("model") or "mimo-v2.5-pro",
        "subscription": data.get("subscription") or "normal",
        "api_key": data.get("api_key") or os.environ.get("MIMO_API_KEY") or load_saved_api_key(),
    }


def extract_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [extract_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        value_type = value.get("type")
        if value_type in ("input_text", "output_text", "text"):
            return extract_text(value.get("text"))
        if value_type == "image_url":
            return "[image_url omitted]"
        if value_type in ("input_audio", "video_url"):
            return f"[{value_type} omitted]"
        for key in ("text", "content", "output", "result"):
            if key in value:
                text = extract_text(value[key])
                if text:
                    return text
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def normalize_role(role):
    if role in ("developer", "system"):
        return "system"
    if role in ("assistant", "tool"):
        return role
    return "user"


def responses_to_messages(body):
    messages = []
    instructions = body.get("instructions")
    if instructions:
        messages.append({"role": "system", "content": extract_text(instructions)})

    inp = body.get("input", "")
    if isinstance(inp, str):
        if inp.strip():
            messages.append({"role": "user", "content": inp})
        return messages or [{"role": "user", "content": ""}]

    if isinstance(inp, list):
        pending_reasoning = None
        for item in inp:
            if not isinstance(item, dict):
                text = extract_text(item)
                if text:
                    messages.append({"role": "user", "content": text})
                continue

            typ = item.get("type")
            if typ == "function_call_output":
                messages.append({
                    "role": "tool",
                    "tool_call_id": item.get("call_id") or item.get("id") or "call_unknown",
                    "content": extract_text(item.get("output")),
                })
                continue

            if typ == "function_call":
                call_id = item.get("call_id") or item.get("id") or "call_unknown"
                call_obj = {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": item.get("name") or "unknown",
                        "arguments": item.get("arguments") or "{}",
                    },
                }
                # DeepSeek thinking 模式：带 tool_calls 的 assistant 消息必须
                # 携带 reasoning_content（思维链），否则上游返回 HTTP 400。
                reasoning = pending_reasoning or item.get("reasoning_content") or item.get("reasoning")
                prev = messages[-1] if messages else None
                if prev and prev.get("role") == "assistant" and prev.get("tool_calls"):
                    # 并行工具调用：本轮多个 tool_calls，合并到同一条 assistant 消息
                    prev["tool_calls"].append(call_obj)
                    if reasoning and not prev.get("reasoning_content"):
                        prev["reasoning_content"] = reasoning
                        pending_reasoning = None
                elif prev and prev.get("role") == "assistant" and not prev.get("tool_calls"):
                    # 关键修复：模型一轮同时返回「正文 + 工具调用 + 思维链」时，
                    # 正文和工具调用是同一条 assistant 消息。Codex 回传时正文是
                    # message item、工具调用是紧随其后的 function_call item。这里
                    # 必须把 tool_calls 合并到前一条正文消息上，而不是新建一条
                    # assistant(tool_calls)，否则 reasoning 只挂在正文上、工具调用
                    # 那条缺 reasoning_content，触发 DeepSeek 400。
                    prev["tool_calls"] = [call_obj]
                    if reasoning and not prev.get("reasoning_content"):
                        prev["reasoning_content"] = reasoning
                        pending_reasoning = None
                else:
                    msg = {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [call_obj],
                    }
                    if reasoning:
                        msg["reasoning_content"] = reasoning
                        pending_reasoning = None
                    messages.append(msg)
                continue

            # 处理 reasoning 类型 item：把思维链文本挂到对应的 assistant 消息上。
            # 兼容两种顺序：reasoning 在 message 之前（新顺序，缓存 pending_reasoning
            # 等后续 message 挂载）；reasoning 在 message 之后（旧顺序/Codex 重排，
            # 直接挂到紧邻的前一个 assistant 消息），避免错位挂到下一个 assistant。
            if typ == "reasoning":
                reasoning_text = extract_text(item.get("content")) or extract_text(item.get("summary"))
                if reasoning_text:
                    attached = False
                    for m in reversed(messages):
                        if m.get("role") == "assistant" and not m.get("reasoning_content"):
                            m["reasoning_content"] = reasoning_text
                            attached = True
                            break
                    if not attached:
                        pending_reasoning = reasoning_text
                continue

            role = normalize_role(item.get("role") or ("assistant" if typ == "message" else "user"))
            text = extract_text(item.get("content"))
            if not text and typ:
                text = extract_text(item)
            reasoning = item.get("reasoning_content") or item.get("reasoning")
            if role == "assistant" and not reasoning and pending_reasoning:
                reasoning = pending_reasoning
            if text or reasoning:
                msg = {"role": role, "content": text or ""}
                if role == "assistant" and reasoning:
                    msg["reasoning_content"] = reasoning
                    pending_reasoning = None
                messages.append(msg)

    # 兜底：若 reasoning item 位于序列末尾、之后没有 assistant 消息可挂载，
    # 则把它挂到最后一个 assistant 消息上（无工具调用轮次上游会忽略，不报错）。
    if pending_reasoning:
        for m in reversed(messages):
            if m.get("role") == "assistant" and not m.get("reasoning_content"):
                m["reasoning_content"] = pending_reasoning
                break

    # 工具消息严格配对：
    # OpenAI / DeepSeek 等上游要求每个 tool 消息必须紧跟声明了对应
    # tool_calls 的 assistant 消息（严格相邻）。对话历史截断/压缩、
    # 并行工具调用、或 function_call 嵌套在 assistant 消息的 output
    # 数组中时，会产生孤立的 tool 消息（前面没有声明它的 assistant），
    # 导致上游 HTTP 400："Messages with role 'tool' must be a response
    # to a preceding message with 'tool calls'"。
    # 这里按顺序做严格配对：
    #   1) assistant(tool_calls) 后紧随的 tool 响应原样保留
    #   2) 缺失的 tool 响应补空内容（保持相邻）
    #   3) 孤立的 tool 消息在其前面补一个 assistant tool_calls 占位
    paired = []
    i = 0
    n = len(messages)
    while i < n:
        m = messages[i]
        if m.get("role") == "assistant" and m.get("tool_calls"):
            paired.append(m)
            call_ids = [c.get("id", "call_unknown") for c in m["tool_calls"]]
            # 收集紧随其后的 tool 响应（同一轮的并行工具调用）
            j = i + 1
            responded = {}
            unmatched = []
            while j < n and messages[j].get("role") == "tool":
                tid = messages[j].get("tool_call_id")
                if tid in call_ids and tid not in responded:
                    responded[tid] = messages[j]
                elif tid not in call_ids:
                    unmatched.append(messages[j])
                j += 1
            # 按声明顺序输出 tool 响应，缺失的补空内容
            for cid in call_ids:
                if cid in responded:
                    paired.append(responded[cid])
                else:
                    paired.append({"role": "tool", "tool_call_id": cid, "content": ""})
            # 不属于当前 assistant 的 tool 响应，作为孤立消息补 assistant 占位
            for u in unmatched:
                utid = u.get("tool_call_id") or "call_unknown"
                paired.append({
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": utid,
                        "type": "function",
                        "function": {"name": "tool", "arguments": "{}"},
                    }],
                })
                paired.append(u)
            i = j
        elif m.get("role") == "tool":
            # 孤立 tool 消息：前面没有声明它的 assistant，补一个占位
            tid = m.get("tool_call_id") or "call_unknown"
            paired.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": tid,
                    "type": "function",
                    "function": {"name": "tool", "arguments": "{}"},
                }],
            })
            paired.append(m)
            i += 1
        else:
            paired.append(m)
            i += 1

    messages = paired

    # 调试日志：打印消息结构到文件
    msg_summary = []
    for m in messages:
        role = m.get("role")
        has_tc = bool(m.get("tool_calls"))
        has_tid = "tool_call_id" in m
        has_rc = bool(m.get("reasoning_content"))
        tc_ids = [c.get("id","?") for c in m.get("tool_calls",[])]
        tid = m.get("tool_call_id","")
        info = ""
        if has_tc:
            info = f"(tc:{','.join(tc_ids)})"
        elif has_tid:
            info = f"(tid:{tid})"
        if has_rc:
            info += "(rc)"
        msg_summary.append(f"{role}{info}")
    _log(f"messages: {' -> '.join(msg_summary)}")

    return messages or [{"role": "user", "content": ""}]


def responses_tools_to_chat_tools(tools):
    chat_tools = []
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") != "function":
            continue
        function = tool.get("function") or {}
        name = tool.get("name") or function.get("name")
        if not name:
            continue
        chat_tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool.get("description") or function.get("description") or "",
                "parameters": tool.get("parameters") or function.get("parameters") or {
                    "type": "object",
                    "properties": {},
                },
            },
        })
    return chat_tools


def sse(handler, event, data):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    try:
        handler.wfile.write(f"event: {event}\n".encode("utf-8"))
        handler.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
        handler.wfile.flush()
        return True
    except (BrokenPipeError, ConnectionResetError, socket.timeout):
        return False


def response_shell(response_id, model, status, output=None, usage=None):
    body = {
        "id": response_id,
        "object": "response",
        "created_at": int(time.time()),
        "status": status,
        "model": model,
        "output": output or [],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
    }
    if usage:
        body["usage"] = usage
    return body


def output_from_chat_message(message):
    output = []
    text = message.get("content") or ""
    audio = message.get("audio") or {}
    if not text and isinstance(audio, dict):
        text = audio.get("transcript") or ""
    reasoning = message.get("reasoning_content") or message.get("reasoning")
    # 保留 reasoning_content（思考模式）作为独立 reasoning item，且必须排在
    # message 之前（思考先于回答）。否则 Codex 回传对话历史时，reasoning 会
    # 错位挂到下一个 assistant 消息上，导致 DeepSeek 多轮对话报
    # 「The reasoning_content in the thinking mode must be passed back to the API」。
    # 注意：reasoning item 的 content 数组必须为空/省略！官方 Responses API 对
    # reasoning 输入 item 校验 content 长度最大为 0（只接受 summary）。若带上
    # content 数组，Codex 存盘后切回官方续聊时会报
    # 「Invalid 'input[n].content': array too long. Expected an array with maximum
    # length 0, but got an array with length 1 instead.」
    if reasoning:
        output.append({
            "id": "rs_" + uuid.uuid4().hex,
            "type": "reasoning",
            "summary": [{"type": "summary_text", "text": reasoning}],
        })
    if text:
        msg_item = {
            "id": "msg_" + uuid.uuid4().hex,
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text, "annotations": []}],
        }
        if reasoning:
            msg_item["reasoning_content"] = reasoning
        output.append(msg_item)
    elif reasoning and not (message.get("tool_calls")):
        # thinking 模型思维链耗尽等场景：只有 reasoning、没有最终答案，且没有
        # 工具调用（有工具调用时 content 为空是正常的，不能误判为耗尽）。
        # 注入明确提示，避免 Codex 界面"只显示正在思考后无输出"。
        hint = (f"[提示] 模型思考完成但未生成最终答案，输出可能被 max_tokens 截断"
                f"（思维链耗尽了全部预算）。Codex 助手已自动将 max_tokens 提升到 {_MIN_OUTPUT_TOKENS}，"
                f"请重试。")
        msg_item = {
            "id": "msg_" + uuid.uuid4().hex,
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [{"type": "output_text", "text": hint, "annotations": []}],
        }
        if reasoning:
            msg_item["reasoning_content"] = reasoning
        output.append(msg_item)
    for call in message.get("tool_calls") or []:
        fn = call.get("function") or {}
        output.append({
            "id": "fc_" + uuid.uuid4().hex,
            "type": "function_call",
            "status": "completed",
            "call_id": call.get("id") or "call_" + uuid.uuid4().hex,
            "name": fn.get("name") or "unknown",
            "arguments": fn.get("arguments") or "{}",
        })
    return output


def mapped_usage(usage):
    if not usage:
        return None
    return {
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


def _extract_upstream_error(data):
    """从上游响应中提取错误信息，兼容多种错误格式。

    支持的错误格式：
    1. OpenAI 标准: {"error": {"message": "..."}}
    2. 非标准: {"code": 50001, "message": "..."}
    3. 响应无 choices 但有 message 字段: {"message": "...", "usage": {...}}
    4. choices 中含错误: {"choices": [{"message": {"content": null}, "finish_reason": "error"}]}

    返回错误消息字符串，无错误时返回 None。
    """
    if not isinstance(data, dict):
        return None

    # 1. OpenAI 标准 error 字段
    if data.get("error"):
        err = data["error"]
        if isinstance(err, dict):
            return err.get("message", str(err))
        return str(err)

    # 2. 非标准格式：有 code 字段且有 message（如 apinest/longcat 的 50001 错误）
    if data.get("code") and data.get("message"):
        return f"[code:{data['code']}] {data['message']}"

    # 3. 响应体没有 choices（正常 OpenAI 响应一定有 choices）
    #    但有 message 字段，说明是错误响应
    if not data.get("choices") and data.get("message"):
        msg = data["message"]
        if isinstance(msg, str) and len(msg) > 0:
            return msg

    # 4. choices 存在但内容为空，且 finish_reason 异常
    choices = data.get("choices") or []
    if choices:
        choice = choices[0]
        finish_reason = choice.get("finish_reason", "")
        if finish_reason in ("error", "length", "content_filter"):
            message = choice.get("message") or {}
            content = message.get("content")
            if not content and finish_reason == "error":
                return f"上游返回异常 finish_reason: {finish_reason}"

    return None


# HTTP 状态码 → 友好提示
_HTTP_ERROR_HINTS = {
    502: "上游网关错误（Bad Gateway），服务端可能短暂故障",
    503: "上游服务暂时不可用（Service Unavailable），可能正在维护或过载",
    504: "上游网关超时（Gateway Timeout），模型服务响应超时",
    500: "上游服务器内部错误（Internal Server Error）",
    429: "请求频率超限（Rate Limit），请稍后重试",
}


def _clean_http_error(code, body):
    """将 HTTP 错误响应体清理为可读文本。

    上游 nginx/网关常返回 HTML 错误页（如 504 页面），
    此函数去除 HTML 标签，提取纯文本，并附加友好提示。
    """
    import re
    text = re.sub(r'<[^>]+>', ' ', body).strip()
    text = re.sub(r'\s+', ' ', text)
    hint = _HTTP_ERROR_HINTS.get(code, "")
    if hint:
        return f"HTTP {code} — {hint}" + (f"（{text}）" if text and text != str(code) else "")
    return f"HTTP {code}: {text[:300]}" if text else f"HTTP {code}"


def probe_url(url, timeout=8):
    """探测 Base URL 连通性，返回分类后的诊断结果。

    用于"测试链接"功能：前端调用控制 API，后端用标准库对目标
    URL 发起请求，按失败类型给出可读原因（超时 / DNS / SSL /
    连接拒绝 / HTTP 状态码等）。

    返回: dict
        {"ok": True,  "status": int, "message": str}  可达（含 4xx/5xx）
        {"ok": False, "status": None, "message": str} 不可达，message 为原因
    """
    if not url:
        return {"ok": False, "status": None, "message": "请输入 Base URL"}
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "status": None, "message": "Base URL 必须以 http:// 或 https:// 开头"}

    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "User-Agent": "CodexHelper/1.0 (connectivity-probe)",
            "Accept": "*/*",
        },
    )
    try:
        # 只读取响应头即关闭，不消费响应体，避免触发大流量
        with urllib.request.urlopen(request, timeout=timeout, context=_SSL_CONTEXT) as resp:
            status = resp.getcode()
            return {"ok": True, "status": status, "message": f"连接成功（HTTP {status}），Base URL 可用"}
    except urllib.error.HTTPError as exc:
        # 任何 HTTP 状态码都说明服务器可达（4xx/5xx 属业务层拒绝）
        status = exc.code
        reason = _clean_http_error(status, str(getattr(exc, "read", lambda: b"")())[:300] if hasattr(exc, "read") else "")
        return {"ok": True, "status": status, "message": f"服务器有响应（HTTP {status}），Base URL 可达"}
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, ssl.SSLError):
            return {"ok": False, "status": None, "message": f"SSL 证书错误：{reason}"}
        if isinstance(reason, socket.timeout):
            return {"ok": False, "status": None, "message": f"连接超时：{timeout} 秒内无响应，请检查地址或网络"}
        if isinstance(reason, socket.gaierror):
            return {"ok": False, "status": None, "message": f"域名解析失败（DNS）：{getattr(reason, 'strerror', None) or reason}"}
        if isinstance(reason, ConnectionRefusedError):
            return {"ok": False, "status": None, "message": "连接被拒绝：该地址和端口没有服务在监听"}
        return {"ok": False, "status": None, "message": f"网络错误：{reason}"}
    except socket.timeout:
        return {"ok": False, "status": None, "message": f"连接超时：{timeout} 秒内无响应，请检查地址或网络"}
    except ssl.SSLError as exc:
        return {"ok": False, "status": None, "message": f"SSL 证书错误：{exc}"}
    except ConnectionRefusedError:
        return {"ok": False, "status": None, "message": "连接被拒绝：该地址和端口没有服务在监听"}
    except Exception as exc:
        return {"ok": False, "status": None, "message": f"连接失败：{exc}"}


class Handler(BaseHTTPRequestHandler):
    server_version = "codex-helper/0.1"

    # 由 AdapterRunner 在启动时注入;每次请求后上报 token 用量
    on_usage = None
    # 错误回调：上报 API 错误
    on_error = None

    def log_message(self, fmt, *args):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {self.address_string()} {fmt % args}", flush=True)

    def send_json(self, status, payload):
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        config = load_config()
        if path in ("/health", "/v1/health"):
            self.send_json(200, {"ok": True, "model": config["model"], "subscription": config["subscription"]})
            return
        if path in ("/models", "/v1/models"):
            self.send_json(200, {
                "object": "list",
                "data": [{
                    "id": config["model"],
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "xiaomi",
                }],
            })
            return
        self.send_error(404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if not (path.startswith("/v1/responses") or path.startswith("/responses")):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            raw = self.rfile.read(length)
            body = json.loads(raw.decode("utf-8") or "{}")
            auth = self.headers.get("authorization") or self.headers.get("Authorization")

            config = load_config()
            if not auth and not config.get("api_key"):
                self.send_error(401, "Missing API key")
                return
            messages = responses_to_messages(body)
            orig_max_tokens = body.get("max_output_tokens") or body.get("max_tokens")
            max_tokens = orig_max_tokens or _MIN_OUTPUT_TOKENS
            # DeepSeek 等 thinking 模式上游的 max_tokens 是「思维链 + 最终答案」的
            # 总预算。Codex 默认 4096 会被思维链耗尽，导致 content 为空、
            # 界面只显示"正在思考"后无输出。此处强制下限，给思维链留足空间。
            if max_tokens < _MIN_OUTPUT_TOKENS:
                _log(f"max_tokens={max_tokens} 低于下限 {_MIN_OUTPUT_TOKENS}，已自动抬升")
                max_tokens = _MIN_OUTPUT_TOKENS
            upstream_body = {
                "model": config["model"],
                "messages": messages,
                # "stream" 由各 handler 设置：handle_stream 用 True（真流式，
                # 实时转发思考过程），handle_non_stream 用 False
                "max_tokens": max_tokens,
            }
            chat_tools = responses_tools_to_chat_tools(body.get("tools"))
            if chat_tools:
                upstream_body["tools"] = chat_tools
                tool_choice = body.get("tool_choice")
                if tool_choice and tool_choice != "auto":
                    upstream_body["tool_choice"] = tool_choice
            for key in ("temperature", "top_p"):
                if key in body:
                    upstream_body[key] = body[key]

            if body.get("stream", True) is not False:
                upstream_body["stream"] = True
                self.handle_stream(auth, config, upstream_body)
            else:
                upstream_body["stream"] = False
                self.handle_non_stream(auth, config, upstream_body)
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            return
        except Exception as exc:
            traceback.print_exc()
            self.send_json(500, {"error": str(exc)})

    def upstream_request(self, auth, config, upstream_body, ssl_context=None):
        """向上游 API 发送请求。

        Args:
            ssl_context: 可选的 SSL 上下文。None 时使用默认上下文，
                         重试时可传入降级上下文以兼容老旧 TLS。
        """
        upstream_auth = f"Bearer {config['api_key']}" if config.get("api_key") else auth
        req = urllib.request.Request(
            config["upstream"],
            data=json.dumps(upstream_body, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": upstream_auth,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Codex/1.0",
            },
        )
        ctx = ssl_context or _SSL_CONTEXT
        return urllib.request.urlopen(req, timeout=600, context=ctx)

    def fetch_upstream(self, auth, config, upstream_body):
        """向上游 API 请求数据，内置 SSL 错误自动重试 & TLS 降级兼容。

        重试策略：
        1. 第一次请求使用默认 SSL 上下文（TLS 1.2+）
        2. 遇到 UNEXPECTED_EOF 等瞬时 SSL 错误时，自动重试
        3. 重试时切换到降级 SSL 上下文（TLS 1.0+），兼容老旧服务器
        4. 遇到 502/503/504 网关瞬时错误时，自动重试（延迟更长：1s → 2s）
        5. 最多重试 _MAX_SSL_RETRIES 次，SSL 错误递增延迟（0.5s → 1.0s）
        6. 其他 HTTPError（4xx/500 等）不重试，直接抛出给调用方处理
        """
        last_exc = None
        for attempt in range(_MAX_SSL_RETRIES + 1):
            try:
                # 第一次用默认 SSL 上下文，重试时用降级上下文
                ctx = _SSL_CONTEXT if attempt == 0 else _SSL_CONTEXT_DOWNGRADED
                with self.upstream_request(auth, config, upstream_body, ssl_context=ctx) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                # 上报 token 用量
                usage = data.get("usage") or {}
                inp = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
                out = usage.get("completion_tokens") or usage.get("output_tokens") or 0
                cache = usage.get("cached_tokens") or usage.get("cache_read_tokens") or usage.get("prompt_cache_hit_tokens") or 0
                if self.on_usage and (inp or out):
                    try:
                        self.on_usage(config.get("model", ""), int(inp), int(out), int(cache))
                    except Exception:
                        pass
                # 上报错误（如果上游返回错误）
                err_msg = _extract_upstream_error(data)
                if err_msg:
                    if self.on_error:
                        try:
                            self.on_error(config.get("model", ""), "api_error", err_msg, json.dumps(data, ensure_ascii=False)[:1000])
                        except Exception:
                            pass
                return data

            except urllib.error.HTTPError as http_err:
                # 502/503/504 是网关瞬时错误（如 nginx 超时），重试可能成功
                if http_err.code in _RETRYABLE_HTTP_CODES and attempt < _MAX_SSL_RETRIES:
                    delay = _SSL_RETRY_BASE_DELAY * (attempt + 1) * 2  # HTTP 重试延迟更长（1s → 2s）
                    _log(f"上游返回 HTTP {http_err.code}（第 {attempt+1}/{_MAX_SSL_RETRIES+1} 次），"
                         f"{delay}s 后重试")
                    time.sleep(delay)
                    last_exc = http_err
                    continue
                # 其他 HTTP 错误（4xx/500 等）或重试次数用完，直接抛出
                if attempt > 0 and http_err.code in _RETRYABLE_HTTP_CODES:
                    _log(f"上游 HTTP {http_err.code} 重试 {attempt} 次后仍失败")
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_SSL_RETRIES and _is_retryable_ssl_error(exc):
                    delay = _SSL_RETRY_BASE_DELAY * (attempt + 1)
                    ctx_name = "默认" if attempt == 0 else "降级 TLS"
                    _log(f"上游请求失败（第 {attempt+1}/{_MAX_SSL_RETRIES+1} 次，{ctx_name}上下文），"
                         f"{delay}s 后重试: {type(exc).__name__}: {exc}")
                    time.sleep(delay)
                    continue
                # 不可重试或已用完重试次数
                if attempt > 0:
                    _log(f"上游请求重试 {attempt} 次后仍失败: {type(exc).__name__}: {exc}")
                raise

        # 理论上不会到达这里
        raise last_exc

    def stream_upstream(self, auth, config, upstream_body):
        """真流式：按行迭代上游 SSE 响应，逐 chunk 产出解析后的 JSON。

        兼容两种上游行为：
        1. 标准 SSE 流（data: {...}）→ 逐 chunk yield
        2. 忽略 stream 参数直接返回完整 JSON → yield 一次 {"_non_stream": data}

        重试策略与 fetch_upstream 一致，但仅覆盖「连接建立 / 首个 chunk
        读取」阶段；一旦开始产出 chunk（started=True），流中断直接抛出，
        由调用方负责提示截断，避免重试导致内容重复发送。
        """
        last_exc = None
        for attempt in range(_MAX_SSL_RETRIES + 1):
            started = False
            ctx = _SSL_CONTEXT if attempt == 0 else _SSL_CONTEXT_DOWNGRADED
            try:
                resp = self.upstream_request(auth, config, upstream_body, ssl_context=ctx)
                try:
                    sse_found = False
                    buf = []
                    for raw in resp:
                        line = raw.decode("utf-8", "replace").strip()
                        if line.startswith("data:"):
                            sse_found = True
                            payload = line[len("data:"):].strip()
                            if payload == "[DONE]":
                                break
                            try:
                                chunk = json.loads(payload)
                            except json.JSONDecodeError:
                                continue
                            started = True
                            yield chunk
                        else:
                            if not sse_found:
                                buf.append(line)
                finally:
                    resp.close()
                if not sse_found:
                    # 上游返回了非流式 JSON（完整响应或错误）
                    full = "".join(buf).strip()
                    if not full:
                        raise RuntimeError("上游返回了空响应")
                    data = json.loads(full) if full.startswith(("{", "[")) else {}
                    if data:
                        yield {"_non_stream": data}
                return
            except urllib.error.HTTPError as http_err:
                if http_err.code in _RETRYABLE_HTTP_CODES and attempt < _MAX_SSL_RETRIES and not started:
                    delay = _SSL_RETRY_BASE_DELAY * (attempt + 1) * 2  # HTTP 重试延迟更长（1s → 2s）
                    _log(f"上游返回 HTTP {http_err.code}（第 {attempt+1}/{_MAX_SSL_RETRIES+1} 次），"
                         f"{delay}s 后重试")
                    time.sleep(delay)
                    last_exc = http_err
                    continue
                raise
            except Exception as exc:
                if attempt < _MAX_SSL_RETRIES and _is_retryable_ssl_error(exc) and not started:
                    delay = _SSL_RETRY_BASE_DELAY * (attempt + 1)
                    ctx_name = "默认" if attempt == 0 else "降级 TLS"
                    _log(f"上游流式请求失败（第 {attempt+1}/{_MAX_SSL_RETRIES+1} 次，{ctx_name}上下文），"
                         f"{delay}s 后重试: {type(exc).__name__}: {exc}")
                    time.sleep(delay)
                    last_exc = exc
                    continue
                raise
        raise last_exc

    def handle_non_stream(self, auth, config, upstream_body):
        try:
            data = self.fetch_upstream(auth, config, upstream_body)
        except urllib.error.HTTPError as err:
            payload = err.read().decode("utf-8", "replace")
            clean_msg = _clean_http_error(err.code, payload)
            # 记录 HTTP 错误到后台
            if self.on_error:
                try:
                    self.on_error(config.get("model", ""), "http_error", clean_msg, payload)
                except Exception:
                    pass
            self.send_json(err.code, {"error": clean_msg})
            return
        except urllib.error.URLError as err:
            err_msg = str(err)
            # 记录连接错误到后台
            if self.on_error:
                try:
                    self.on_error(config.get("model", ""), "connection_error", err_msg, err_msg)
                except Exception:
                    pass
            self.send_json(502, {"error": err_msg})
            return

        # 检查上游是否在响应体中返回了错误（兼容标准和非标准格式）
        err_msg = _extract_upstream_error(data)
        if err_msg:
            _log(f"上游返回 API 错误: {err_msg}")
            output = [{
                "id": "msg_" + uuid.uuid4().hex,
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": f"[API Error] {err_msg}", "annotations": []}],
            }]
            result = response_shell(
                "resp_" + uuid.uuid4().hex,
                config["model"],
                "completed",
                output=output,
                usage=mapped_usage(data.get("usage")),
            )
            self.send_json(200, result)
            return

        message = (data.get("choices") or [{}])[0].get("message") or {}
        # 如果消息内容为空，记录日志以便排查
        if not message.get("content") and not message.get("tool_calls") and not message.get("reasoning_content"):
            _log(f"上游返回空响应(无choices): {json.dumps(data, ensure_ascii=False)[:500]}")
            # 没有有效内容时返回错误提示，避免 Codex 收到空响应
            output = [{
                "id": "msg_" + uuid.uuid4().hex,
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "[Error] 上游返回了无效的空响应，请检查 API 配置或重试。", "annotations": []}],
            }]
            result = response_shell(
                "resp_" + uuid.uuid4().hex,
                config["model"],
                "completed",
                output=output,
                usage=mapped_usage(data.get("usage")),
            )
            self.send_json(200, result)
            return
        output = output_from_chat_message(message)
        result = response_shell(
            "resp_" + uuid.uuid4().hex,
            config["model"],
            "completed",
            output=output,
            usage=mapped_usage(data.get("usage")),
        )
        self.send_json(200, result)

    def handle_stream(self, auth, config, upstream_body):
        response_id = "resp_" + uuid.uuid4().hex
        self.send_response(200)
        self.send_header("content-type", "text/event-stream; charset=utf-8")
        self.send_header("cache-control", "no-cache")
        self.send_header("connection", "close")
        self.end_headers()

        if not sse(self, "response.created", {
            "type": "response.created",
            "response": response_shell(response_id, config["model"], "in_progress"),
        }):
            return

        # 伪流式在等待上游完整响应期间（思考模型可能十几秒）不发任何数据，
        # Codex 客户端会误判连接断开并显示"重新连接"。这里启动心跳线程，
        # 定期发送 SSE 注释行（: keep-alive）保持连接活跃。
        stop_hb = threading.Event()

        def _heartbeat():
            while not stop_hb.wait(3.0):
                try:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                except Exception:
                    break

        hb_thread = threading.Thread(target=_heartbeat, daemon=True)

        try:
            # handle_stream 是伪流式：先等上游完整响应，再拆成 SSE 事件
            # 逐条转发。因此必须强制 stream=false —— 否则上游返回 SSE 流，
            # fetch_upstream 的 json.loads 无法解析，导致 500 且无 usage 上报。
            non_stream_body = dict(upstream_body)
            non_stream_body["stream"] = False
            hb_thread.start()
            data = self.fetch_upstream(auth, config, non_stream_body)
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", "replace")
            clean_msg = _clean_http_error(err.code, detail)
            print(f"upstream HTTP {err.code}: {clean_msg}", flush=True)
            # 记录 HTTP 错误到后台
            if self.on_error:
                try:
                    self.on_error(config.get("model", ""), "http_error", clean_msg, detail)
                except Exception:
                    pass
            data = {"choices": [{"message": {"content": f"[Upstream Error] {clean_msg}"}}]}
        except urllib.error.URLError as err:
            detail = str(err)
            print(f"upstream URL error: {detail}", flush=True)
            # 记录连接错误到后台
            if self.on_error:
                try:
                    self.on_error(config.get("model", ""), "connection_error", detail, detail)
                except Exception:
                    pass
            data = {"choices": [{"message": {"content": f"Upstream connection failed: {detail[:1200]}"}}]}
        finally:
            stop_hb.set()

        # 检查上游是否在响应体中返回了错误（兼容标准和非标准格式）
        err_msg = _extract_upstream_error(data)
        if err_msg:
            _log(f"上游返回 API 错误(stream): {err_msg}")
            data = {"choices": [{"message": {"content": f"[API Error] {err_msg}"}}]}

        message = (data.get("choices") or [{}])[0].get("message") or {}
        # 如果消息内容为空，记录日志并返回错误提示
        if not message.get("content") and not message.get("tool_calls") and not message.get("reasoning_content"):
            _log(f"上游返回空响应(stream): {json.dumps(data, ensure_ascii=False)[:500]}")
            data = {"choices": [{"message": {"content": "[Error] 上游返回了无效的空响应，请检查 API 配置或重试。"}}]}
            message = data["choices"][0]["message"]
        output = output_from_chat_message(message)

        for index, item in enumerate(output):
            added_item = dict(item)
            if added_item.get("type") == "message":
                added_item["status"] = "in_progress"
                added_item["content"] = []
            if not sse(self, "response.output_item.added", {
                "type": "response.output_item.added",
                "response_id": response_id,
                "output_index": index,
                "item": added_item,
            }):
                return
            if item.get("type") == "message":
                part = item["content"][0]
                if not sse(self, "response.content_part.added", {
                    "type": "response.content_part.added",
                    "response_id": response_id,
                    "item_id": item["id"],
                    "output_index": index,
                    "content_index": 0,
                    "part": {"type": "output_text", "text": "", "annotations": []},
                }):
                    return
                if not sse(self, "response.output_text.delta", {
                    "type": "response.output_text.delta",
                    "response_id": response_id,
                    "item_id": item["id"],
                    "output_index": index,
                    "content_index": 0,
                    "delta": part.get("text", ""),
                }):
                    return
                if not sse(self, "response.output_text.done", {
                    "type": "response.output_text.done",
                    "response_id": response_id,
                    "item_id": item["id"],
                    "output_index": index,
                    "content_index": 0,
                    "text": part.get("text", ""),
                }):
                    return
                if not sse(self, "response.content_part.done", {
                    "type": "response.content_part.done",
                    "response_id": response_id,
                    "item_id": item["id"],
                    "output_index": index,
                    "content_index": 0,
                    "part": part,
                }):
                    return
            if item.get("type") == "function_call":
                if not sse(self, "response.function_call_arguments.done", {
                    "type": "response.function_call_arguments.done",
                    "response_id": response_id,
                    "item_id": item["id"],
                    "output_index": index,
                    "arguments": item.get("arguments", "{}"),
                }):
                    return
            if not sse(self, "response.output_item.done", {
                "type": "response.output_item.done",
                "response_id": response_id,
                "output_index": index,
                "item": item,
            }):
                return

        sse(self, "response.completed", {
            "type": "response.completed",
            "response": response_shell(
                response_id,
                config["model"],
                "completed",
                output=output,
                usage=mapped_usage(data.get("usage")),
            ),
        })
        self.close_connection = True


def main():
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"codex helper adapter listening on http://{HOST}:{PORT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
