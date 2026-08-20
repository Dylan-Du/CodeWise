"""激活码管理模块：设备码生成、激活码校验、本地存储。"""
import hashlib
import json
import platform
import subprocess
import os
import uuid
import urllib.request
import urllib.error
from pathlib import Path

# 配置目录
_ACTIVATE_DIR = Path(os.path.expanduser("~")) / ".codex-helper"
_ACTIVATE_DIR.mkdir(parents=True, exist_ok=True)
_ACTIVATE_FILE = _ACTIVATE_DIR / "activation.json"

# 后端服务地址（优先级：环境变量 > 配置文件 > 默认值）
_CONFIG_FILE = _ACTIVATE_DIR / "server.json"


def _load_server_url() -> str:
    """读取服务器地址，优先级：环境变量 > 配置文件 > 默认值。"""
    # 1. 环境变量
    env_url = os.environ.get("ACTIVATION_SERVER")
    if env_url:
        return env_url.rstrip("/")
    # 2. 配置文件（~/.codex-helper/server.json）
    try:
        if _CONFIG_FILE.exists():
            data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            url = data.get("server_url")
            if url:
                return url.rstrip("/")
    except Exception:
        pass
    # 3. 默认值（生产环境服务器地址）
    return "http://43.160.233.155:8080"


_SERVER_URL = _load_server_url()


def get_device_id() -> str:
    """生成设备唯一标识：MAC地址 + 硬件UUID 的 SHA256 哈希。"""
    mac = uuid.getnode()
    mac_str = ":".join(f"{(mac >> (8 * i)) & 0xFF:02X}" for i in range(5, -1, -1))

    hw_uuid = ""
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if "IOPlatformUUID" in line:
                    hw_uuid = line.split('"')[-2] if '"' in line else ""
                    break
        except Exception:
            pass
    elif platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["wmic", "csproduct", "get", "UUID"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line and line != "UUID":
                    hw_uuid = line
                    break
        except Exception:
            pass

    raw = f"{mac_str}|{hw_uuid}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]  # 截断为32位，保持向后兼容


def get_device_type() -> str:
    """返回设备类型：mac / win。"""
    s = platform.system()
    if s == "Darwin":
        return "mac"
    if s == "Windows":
        return "win"
    return "mac"  # 默认


def load_activation() -> dict:
    """读取本地激活信息。"""
    if not _ACTIVATE_FILE.exists():
        return {}
    try:
        return json.loads(_ACTIVATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_activation(data: dict):
    """保存激活信息到本地。"""
    _ACTIVATE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def is_activated() -> bool:
    """检查是否已激活且未过期（含在线校验）。"""
    data = load_activation()
    code = data.get("code")
    if not code:
        return False

    # 永久激活：先通过本地检查，再做在线校验
    if data.get("type") == "permanent":
        # 在线校验：确认码仍存在且绑定到当前设备
        result = verify_code_online(code)
        if result.get("code") == 0:
            # 后端正常响应
            if result.get("data", {}).get("valid"):
                return True
            # 后端明确返回无效（码被解绑/删除）
            clear_activation()
            return False
        # 后端不可达（网络错误等），不清除本地记录，信任本地
        return True

    # 按天激活：先检查本地过期
    expires_at = data.get("expires_at")

    # 如果本地没有过期时间，直接做在线校验
    if not expires_at:
        result = verify_code_online(code)
        if result.get("code") == 0:
            if result.get("data", {}).get("valid"):
                # 在线校验通过，补全本地信息
                online_data = result.get("data", {})
                data["type"] = online_data.get("type")
                data["expires_at"] = online_data.get("expires_at")
                save_activation(data)
                # 补全后重新检查
                if data.get("type") == "permanent":
                    return True
                expires_at = data.get("expires_at")
                if not expires_at:
                    return True
            else:
                clear_activation()
                return False
        else:
            # 后端不可达，信任本地
            return True

    import datetime
    try:
        # 解析过期时间，兼容多种格式：
        #   2026-08-07T12:00:00Z（ISO 8601 UTC）
        #   2026-08-07T12:00:00+08:00（ISO 8601 带偏移）
        #   2026-08-07 12:00:00（旧格式，无时区）
        exp_str = expires_at
        if exp_str.endswith("Z"):
            exp_str = exp_str.replace("Z", "+00:00")
        exp = datetime.datetime.fromisoformat(exp_str)

        if exp.tzinfo is not None:
            # 带时区信息，用 UTC 比较
            now = datetime.datetime.now(datetime.timezone.utc)
        else:
            # 无时区信息，按本地时间比较（不转换为 UTC，避免时区错位）
            now = datetime.datetime.now()

        if exp < now:
            # 已过期，清除本地记录
            clear_activation()
            return False
        # 本地未过期，再做在线校验
        result = verify_code_online(code)
        if result.get("code") == 0:
            # 后端正常响应
            if result.get("data", {}).get("valid"):
                return True
            # 后端明确返回无效（码被解绑/删除）
            clear_activation()
            return False
        # 后端不可达（网络错误等），不清除本地记录，信任本地
        return True
    except Exception:
        return False


def clear_activation():
    """清除本地激活记录。"""
    try:
        if _ACTIVATE_FILE.exists():
            _ACTIVATE_FILE.unlink()
    except Exception:
        pass


def verify_code_online(code: str) -> dict:
    """在线校验激活码（调用后端 verify 接口）。"""
    server_url = _load_server_url()
    device_id = get_device_id()
    device_type = get_device_type()

    body = json.dumps({
        "code": code,
        "device_id": device_id,
        "device_type": device_type,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{server_url}/api/activation/verify",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.URLError as e:
        return {"code": -1, "message": f"无法连接激活服务器: {e}"}
    except Exception as e:
        return {"code": -1, "message": f"校验失败: {e}"}


def bind_code_online(code: str) -> dict:
    """在线绑定激活码到当前设备。"""
    server_url = _load_server_url()
    device_id = get_device_id()
    device_type = get_device_type()

    body = json.dumps({
        "code": code,
        "device_id": device_id,
        "device_type": device_type,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{server_url}/api/activation/bind",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") == 0 and data.get("data", {}).get("bound"):
                # 保存到本地
                save_activation({
                    "code": code,
                    "device_id": device_id,
                    "type": data["data"].get("type"),
                    "expires_at": data["data"].get("expires_at"),
                    "bound_at": _now_iso(),
                })
            return data
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            return err_body
        except Exception:
            return {"code": -1, "message": f"绑定失败: HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"code": -1, "message": f"无法连接激活服务器: {e}"}
    except Exception as e:
        return {"code": -1, "message": f"绑定失败: {e}"}


def report_error(error_type: str, message: str, details: str = ""):
    """向后台上报错误日志。"""
    server_url = _load_server_url()
    device_id = get_device_id()
    device_type = get_device_type()
    data = load_activation()
    code = data.get("code", "")

    body = json.dumps({
        "code": code,
        "device_id": device_id,
        "device_type": device_type,
        "error_type": error_type,
        "message": message,
        "details": details,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{server_url}/api/activation/report-error",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {"code": -1, "message": "上报失败"}


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now().isoformat()
