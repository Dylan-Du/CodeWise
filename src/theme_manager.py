"""主题管理模块：基准检测、主题下载、校验、应用。"""
import json
import os
import socket
import subprocess
import urllib.request
import urllib.error
import zipfile
import shutil
import hashlib
from pathlib import Path
from typing import Optional

# 主题库路径
THEME_LIBRARY = Path.home() / "Library" / "Application Support" / "CodexDreamSkinStudio" / "themes"

# 用户自定义主题路径
CUSTOM_THEME_DIR = Path.home() / "Library" / "Application Support" / "Codex助手" / "themes" / "custom"

# 配置文件
THEME_CONFIG_FILE = Path.home() / ".codex-helper" / "theme_config.json"


def _ensure_dir(path: Path):
    """安全创建目录"""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        pass


class ThemeManager:
    """主题管理器"""

    def __init__(self):
        _ensure_dir(THEME_LIBRARY)
        _ensure_dir(CUSTOM_THEME_DIR)
        self.current_theme = self._load_config().get("current_theme")

    def _load_config(self) -> dict:
        """加载主题配置"""
        if not THEME_CONFIG_FILE.exists():
            return {}
        try:
            return json.loads(THEME_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_config(self, data: dict):
        """保存主题配置"""
        THEME_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        THEME_CONFIG_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def check_baseline(self) -> dict:
        """检查主题功能的前置条件"""
        results = {
            "codex_installed": False,
            "codex_launched": False,
            "cdp_available": False,
            "all_passed": False,
            "message": ""
        }

        # 检查 Codex 是否安装
        codex_app = Path("/Applications/Codex.app")
        results["codex_installed"] = codex_app.exists()

        # 检查 Codex 是否启动过
        config_toml = Path.home() / ".codex" / "config.toml"
        results["codex_launched"] = config_toml.exists()

        # 检查 CDP 端口是否可用
        try:
            sock = socket.create_connection(("127.0.0.1", 9222), timeout=1)
            sock.close()
            results["cdp_available"] = True
        except:
            results["cdp_available"] = False

        results["all_passed"] = all([
            results["codex_installed"],
            results["codex_launched"],
            results["cdp_available"]
        ])

        if results["all_passed"]:
            results["message"] = "Codex 已就绪"
        elif not results["codex_installed"]:
            results["message"] = "请先安装 Codex 桌面应用"
        elif not results["codex_launched"]:
            results["message"] = "请先启动一次 Codex"
        elif not results["cdp_available"]:
            results["message"] = "请启动 Codex 后重试"

        return results

    def get_local_themes(self) -> list[dict]:
        """获取本地主题列表"""
        themes = []
        for theme_dir in THEME_LIBRARY.iterdir():
            if theme_dir.is_dir():
                theme_json = theme_dir / "theme.json"
                if theme_json.exists():
                    try:
                        data = json.loads(theme_json.read_text(encoding="utf-8"))
                        themes.append({
                            "id": data.get("id", theme_dir.name),
                            "name": data.get("name", theme_dir.name),
                            "author": data.get("author", "Unknown"),
                            "path": str(theme_dir),
                            "thumbnail": self._get_thumbnail(theme_dir)
                        })
                    except Exception:
                        pass
        return themes

    def _get_thumbnail(self, theme_dir: Path) -> Optional[str]:
        """获取主题缩略图路径"""
        for ext in ["png", "jpg", "webp"]:
            thumb = theme_dir / f"thumbnail.{ext}"
            if thumb.exists():
                return str(thumb)
        # 使用背景图作为缩略图
        for name in ["background", "bg"]:
            for ext in ["png", "jpg", "webp"]:
                bg = theme_dir / f"{name}.{ext}"
                if bg.exists():
                    return str(bg)
        return None

    def get_current_theme(self) -> Optional[dict]:
        """获取当前应用的主题"""
        if not self.current_theme:
            return None

        theme_dir = THEME_LIBRARY / self.current_theme
        if not theme_dir.exists():
            return None

        theme_json = theme_dir / "theme.json"
        if not theme_json.exists():
            return None

        try:
            data = json.loads(theme_json.read_text(encoding="utf-8"))
            return {
                "id": data.get("id", self.current_theme),
                "name": data.get("name", self.current_theme),
                "author": data.get("author", "Unknown"),
                "thumbnail": self._get_thumbnail(theme_dir)
            }
        except Exception:
            return None

    def get_community_themes(self) -> list[dict]:
        """从 GitHub Releases 和 dreamskin.cc 获取社区主题列表"""
        themes = []

        # 1. 从 GitHub Releases 获取
        try:
            themes.extend(self._fetch_github_themes())
        except Exception as e:
            print(f"GitHub 主题获取失败: {e}")

        return themes

    def _fetch_github_themes(self) -> list[dict]:
        """从 GitHub Releases 获取主题"""
        themes = []
        url = "https://api.github.com/repos/Fei-Away/Codex-Dream-Skin/releases"

        req = urllib.request.Request(url, headers={
            "User-Agent": "CodexHelper/1.0",
            "Accept": "application/vnd.github.v3+json"
        })

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

                for release in data[:5]:  # 只取最近 5 个 release
                    for asset in release.get("assets", []):
                        name = asset.get("name", "")
                        if name.endswith(".zip"):
                            # 解析主题名称
                            theme_name = name.replace(".zip", "").replace("theme-", "")
                            themes.append({
                                "id": f"github-{release['tag_name']}-{theme_name}",
                                "name": theme_name.replace("-", " ").title(),
                                "author": release.get("author", {}).get("login", "Fei-Away"),
                                "download_url": asset.get("browser_download_url"),
                                "source": "github",
                                "version": release.get("tag_name", "latest")
                            })
        except urllib.error.URLError as e:
            print(f"GitHub API 请求失败: {e}")

        return themes

    def download_theme(self, url: str, theme_id: str) -> dict:
        """下载并解压主题包"""
        result = {
            "success": False,
            "theme_id": theme_id,
            "message": ""
        }

        try:
            # 确保目录存在
            self._ensure_theme_library()

            # 下载到临时文件
            temp_zip = THEME_LIBRARY / f"_temp_{theme_id}.zip"

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                with open(temp_zip, "wb") as f:
                    f.write(resp.read())

            # 校验文件大小
            if temp_zip.stat().st_size > 32 * 1024 * 1024:  # 32MB
                raise ValueError("主题包超过大小限制 (32MB)")

            # 解压
            theme_dir = THEME_LIBRARY / theme_id
            if theme_dir.exists():
                shutil.rmtree(theme_dir)

            with zipfile.ZipFile(temp_zip, "r") as zf:
                # 安全检查
                for name in zf.namelist():
                    if name.startswith("/") or ".." in name:
                        raise ValueError("主题包包含不安全路径")

                zf.extractall(theme_dir)

            # 清理
            temp_zip.unlink()

            # 校验主题包
            if not self._validate_theme(theme_dir):
                shutil.rmtree(theme_dir)
                raise ValueError("主题包格式无效")

            result["success"] = True
            result["message"] = "主题下载成功"

        except Exception as e:
            result["message"] = str(e)

        return result

    def _validate_theme(self, theme_dir: Path) -> bool:
        """校验主题包格式"""
        # 必须包含 theme.json
        theme_json = theme_dir / "theme.json"
        if not theme_json.exists():
            return False

        try:
            data = json.loads(theme_json.read_text(encoding="utf-8"))
            # 必需字段
            if not data.get("name"):
                return False
        except:
            return False

        # 文件数量限制
        file_count = sum(1 for _ in theme_dir.rglob("*") if _.is_file())
        if file_count > 32:
            return False

        # 解压后大小限制
        total_size = sum(f.stat().st_size for f in theme_dir.rglob("*") if f.is_file())
        if total_size > 64 * 1024 * 1024:  # 64MB
            return False

        return True

    def _ensure_theme_library(self):
        """确保主题库目录存在"""
        try:
            THEME_LIBRARY.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def apply_theme(self, theme_id: str) -> dict:
        """应用主题到 Codex"""
        result = {
            "success": False,
            "theme_id": theme_id,
            "message": ""
        }

        try:
            # 1. 查找主题目录
            theme_dir = THEME_LIBRARY / theme_id
            if not theme_dir.exists():
                # 尝试在子目录中查找
                for d in THEME_LIBRARY.iterdir():
                    if d.is_dir():
                        sub_theme_json = d / "theme.json"
                        if sub_theme_json.exists():
                            try:
                                data = json.loads(sub_theme_json.read_text(encoding="utf-8"))
                                if data.get("id") == theme_id or d.name == theme_id:
                                    theme_dir = d
                                    break
                            except:
                                pass

            if not theme_dir.exists():
                raise ValueError(f"主题不存在: {theme_id}")

            # 2. 读取主题配置
            theme_json = theme_dir / "theme.json"
            if not theme_json.exists():
                raise ValueError("主题缺少 theme.json")

            theme_data = json.loads(theme_json.read_text(encoding="utf-8"))

            # 3. 检查基准条件
            baseline = self.check_baseline()
            if not baseline["cdp_available"]:
                raise ValueError("Codex 未运行或 CDP 端口不可用")

            # 4. 构建注入 CSS
            css_content = self._build_theme_css(theme_dir, theme_data)

            # 5. 通过 CDP 注入
            self._inject_css_to_codex(css_content)

            # 6. 保存当前主题配置
            config = self._load_config()
            config["current_theme"] = theme_id
            config["last_applied"] = self._now_iso()
            self._save_config(config)
            self.current_theme = theme_id

            result["success"] = True
            result["message"] = "主题应用成功"

        except Exception as e:
            result["message"] = str(e)

        return result

    def _build_theme_css(self, theme_dir: Path, theme_data: dict) -> str:
        """构建主题 CSS"""
        css_parts = []

        # 1. 读取主题 CSS 文件
        theme_css = theme_dir / "theme.css"
        if theme_css.exists():
            css_parts.append(theme_css.read_text(encoding="utf-8"))

        # 2. 如果有背景图，添加背景样式
        bg_path = self._find_background_image(theme_dir)
        if bg_path:
            # 将图片转为 base64 data URL
            import base64
            bg_data = base64.b64encode(bg_path.read_bytes()).decode("utf-8")
            bg_ext = bg_path.suffix.lower().replace(".", "")
            mime_type = "image/jpeg" if bg_ext in ["jpg", "jpeg"] else f"image/{bg_ext}"
            bg_url = f"data:{mime_type};base64,{bg_data}"

            # 获取艺术配置
            art = theme_data.get("art", {})
            focus_x = art.get("focusX", 0.5)
            focus_y = art.get("focusY", 0.5)

            # 添加背景样式
            bg_css = f"""
/* Codex助手 注入的背景样式 */
body {{
  background-image: url('{bg_url}') !important;
  background-size: cover !important;
  background-position: {focus_x * 100}% {focus_y * 100}% !important;
  background-repeat: no-repeat !important;
  background-attachment: fixed !important;
}}
"""
            css_parts.append(bg_css)

        # 3. 添加配色
        colors = theme_data.get("colors", {})
        if colors:
            color_css = "/* 配色变量 */\n:root {\n"
            for name, color in colors.items():
                color_css += f"  --theme-{name}: {color};\n"
            color_css += "}\n"
            css_parts.append(color_css)

        return "\n".join(css_parts)

    def _find_background_image(self, theme_dir: Path) -> Optional[Path]:
        """查找主题背景图"""
        for name in ["background", "bg", "wallpaper"]:
            for ext in ["webp", "jpg", "jpeg", "png"]:
                path = theme_dir / f"{name}.{ext}"
                if path.exists():
                    return path
        return None

    def _inject_css_to_codex(self, css_content: str):
        """通过 CDP 注入 CSS 到 Codex"""
        import http.client
        import hashlib

        # 1. 获取 WebSocket URL
        conn = http.client.HTTPConnection("127.0.0.1", 9222, timeout=5)
        conn.request("GET", "/json")
        resp = conn.getresponse()
        pages = json.loads(resp.read().decode("utf-8"))
        conn.close()

        if not pages:
            raise ValueError("未找到 Codex 页面")

        # 获取第一个页面的 WebSocket URL
        ws_url = None
        for page in pages:
            if page.get("type") == "page":
                ws_url = page.get("webSocketDebuggerUrl")
                if ws_url:
                    break

        if not ws_url:
            raise ValueError("未找到有效的 Codex 调试页面")

        # 2. 建立 WebSocket 连接并发送 CDP 命令
        self._send_cdp_command(ws_url, "Page.addStyleSheetToDocument", {
            "styleSheetId": f"codex-helper-theme-{hashlib.md5(css_content.encode()).hexdigest()[:8]}",
            "cssContent": css_content
        })

    def _send_cdp_command(self, ws_url: str, method: str, params: dict):
        """发送 CDP 命令（简化 WebSocket 实现）"""
        import socket
        import struct
        import hashlib
        import base64
        from urllib.parse import urlparse

        # 解析 WebSocket URL
        parsed = urlparse(ws_url)
        host = parsed.hostname
        port = parsed.port or 9222

        # 建立 TCP 连接
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((host, port))

        try:
            # WebSocket 握手
            key = base64.b64encode(hashlib.sha1(b"codex-helper").digest()[:16]).decode()
            path = parsed.path or "/"
            handshake = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                f"Sec-WebSocket-Version: 13\r\n"
                f"\r\n"
            )
            sock.send(handshake.encode())

            # 读取握手响应
            resp = b""
            while b"\r\n\r\n" not in resp:
                resp += sock.recv(4096)

            # 发送 CDP 命令（WebSocket 文本帧）
            command = json.dumps({
                "id": 1,
                "method": method,
                "params": params
            })

            # 构造 WebSocket 帧（opcode 0x01 = text）
            frame = self._build_websocket_frame(command)
            sock.send(frame)

            # 读取响应
            response_data = self._read_websocket_frame(sock)
            response = json.loads(response_data)

            if "error" in response:
                raise ValueError(f"CDP 错误: {response['error']}")

        finally:
            sock.close()

    def _build_websocket_frame(self, data: str) -> bytes:
        """构建 WebSocket 文本帧"""
        payload = data.encode("utf-8")
        length = len(payload)

        # FIN + opcode (text)
        frame = bytearray([0x81])

        if length <= 125:
            frame.append(length)
        elif length <= 65535:
            frame.extend([126, (length >> 8) & 0xFF, length & 0xFF])
        else:
            frame.extend([127])
            for i in range(7, -1, -1):
                frame.append((length >> (8 * i)) & 0xFF)

        frame.extend(payload)
        return bytes(frame)

    def _read_websocket_frame(self, sock: socket.socket) -> str:
        """读取 WebSocket 帧"""
        # 读取前两个字节
        header = sock.recv(2)
        payload_len = header[1] & 0x7F

        if payload_len == 126:
            ext_len = sock.recv(2)
            payload_len = int.from_bytes(ext_len, "big")
        elif payload_len == 127:
            ext_len = sock.recv(8)
            payload_len = int.from_bytes(ext_len, "big")

        # 读取掩码键（如果有）
        if header[1] & 0x80:
            mask_key = sock.recv(4)
            payload = sock.recv(payload_len)
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        else:
            payload = sock.recv(payload_len)

        return payload.decode("utf-8")

    def restore_default(self) -> dict:
        """恢复官方外观"""
        result = {
            "success": False,
            "message": ""
        }

        try:
            # 检查基准
            baseline = self.check_baseline()
            if not baseline["cdp_available"]:
                raise ValueError("Codex 未运行")

            # 通过 CDP 刷新页面来清除注入的样式
            # 这是一个简化的恢复方式，实际上可能需要更精细的控制
            import http.client
            conn = http.client.HTTPConnection("127.0.0.1", 9222, timeout=5)
            conn.request("GET", "/json")
            resp = conn.getresponse()
            pages = json.loads(resp.read().decode("utf-8"))
            conn.close()

            for page in pages:
                if page.get("type") == "page":
                    ws_url = page.get("webSocketDebuggerUrl")
                    if ws_url:
                        # 发送页面刷新命令
                        self._send_cdp_command(ws_url, "Page.reload", {})
                        break

            # 清除配置
            config = self._load_config()
            config["current_theme"] = None
            self._save_config(config)
            self.current_theme = None

            result["success"] = True
            result["message"] = "已恢复官方外观"

        except Exception as e:
            result["message"] = str(e)

        return result

    def _now_iso(self) -> str:
        """返回当前时间的 ISO 格式"""
        import datetime
        return datetime.datetime.now().isoformat()

    def create_custom_theme(self, image_path: str, params: dict) -> dict:
        """从自定义图片创建主题"""
        import base64
        import datetime

        result = {
            "success": False,
            "theme_id": "",
            "message": ""
        }

        try:
            # 1. 检查图片文件
            img_path = Path(image_path)
            if not img_path.exists():
                raise ValueError("图片文件不存在")

            # 2. 检查文件大小（最大 10MB）
            if img_path.stat().st_size > 10 * 1024 * 1024:
                raise ValueError("图片文件过大（最大 10MB）")

            # 3. 检查图片格式
            valid_exts = ["jpg", "jpeg", "png", "webp"]
            if img_path.suffix.lower().replace(".", "") not in valid_exts:
                raise ValueError("不支持的图片格式")

            # 4. 生成主题 ID
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            theme_id = f"custom_{timestamp}"

            # 5. 创建主题目录
            theme_dir = CUSTOM_THEME_DIR / theme_id
            theme_dir.mkdir(parents=True, exist_ok=True)

            # 6. 复制图片作为背景
            bg_path = theme_dir / f"background{img_path.suffix}"
            shutil.copy(img_path, bg_path)

            # 7. 构建主题配置
            theme_name = params.get("name", f"自定义主题 {timestamp}")
            focus_x = params.get("focusX", 0.5)
            focus_y = params.get("focusY", 0.5)
            colors = params.get("colors", {})

            theme_json = {
                "id": theme_id,
                "name": theme_name,
                "author": "用户",
                "version": "1.0.0",
                "created": self._now_iso(),
                "art": {
                    "focusX": focus_x,
                    "focusY": focus_y,
                    "safeArea": params.get("safeArea", "auto"),
                    "taskMode": params.get("taskMode", "auto")
                },
                "colors": colors
            }

            # 8. 保存配置文件
            (theme_dir / "theme.json").write_text(
                json.dumps(theme_json, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            # 9. 生成基础 CSS
            css_content = """/* 自定义主题样式 */
/* 由 Codex助手 自动生成 */
"""
            if colors:
                css_content += "\n:root {\n"
                for name, color in colors.items():
                    css_content += f"  --theme-{name}: {color};\n"
                css_content += "}\n"

            (theme_dir / "theme.css").write_text(css_content, encoding="utf-8")

            result["success"] = True
            result["theme_id"] = theme_id
            result["message"] = "主题创建成功"
            result["theme"] = {
                "id": theme_id,
                "name": theme_name,
                "path": str(theme_dir)
            }

        except Exception as e:
            result["message"] = str(e)

        return result


# 全局单例
theme_manager = ThemeManager()