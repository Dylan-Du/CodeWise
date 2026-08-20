"""主题管理模块：基准检测、主题下载、校验、应用。"""
import json
import os
import sys
import ssl
import socket
import subprocess
import urllib.request
import urllib.error
import zipfile
import shutil
import hashlib
import tempfile
import base64
from pathlib import Path
from typing import Optional

# 主题库路径
THEME_LIBRARY = Path.home() / "Library" / "Application Support" / "CodexDreamSkinStudio" / "themes"

# 用户自定义主题路径
CUSTOM_THEME_DIR = Path.home() / "Library" / "Application Support" / "Codex助手" / "themes" / "custom"

# 配置文件
THEME_CONFIG_FILE = Path.home() / ".codex-helper" / "theme_config.json"

# 内置主题资源目录（兼容开发环境和 PyInstaller 打包环境）
if getattr(sys, 'frozen', False):
    BUILTIN_THEMES_DIR = Path(sys._MEIPASS) / "assets" / "dream-skin" / "builtin-themes"
    DREAM_SKIN_BASE_CSS = Path(sys._MEIPASS) / "assets" / "dream-skin" / "dream-skin-base.css"
else:
    _project_root = Path(__file__).parent.parent
    BUILTIN_THEMES_DIR = _project_root / "assets" / "dream-skin" / "builtin-themes"
    DREAM_SKIN_BASE_CSS = _project_root / "assets" / "dream-skin" / "dream-skin-base.css"


def _ensure_dir(path: Path):
    """安全创建目录"""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        pass


class ThemeManager:
    """主题管理器"""

    # watcher 重试配置
    _WATCHER_INITIAL_WAIT = 5   # 检测到 CDP 后首次等待秒数
    _WATCHER_MAX_RETRIES = 4    # 最大重试次数
    _WATCHER_RETRY_DELAYS = [3, 5, 8, 12]  # 每次重试间隔秒数（递增）

    def __init__(self):
        _ensure_dir(THEME_LIBRARY)
        _ensure_dir(CUSTOM_THEME_DIR)
        self.current_theme = self._load_config().get("current_theme")
        self._ssl_ctx = self._create_ssl_context()
        self._watcher_started = False
        self._last_cdp_state = False
        self._ensure_cdp_enabled()
        self._start_watcher()

    def _ensure_cdp_enabled(self):
        """确保 ChatGPT.app 启动时带有 --remote-debugging-port=9222。
        创建一个包装脚本，通过 LaunchAgent 在登录时自动以 CDP 模式启动 ChatGPT。
        """
        try:
            launch_dir = Path.home() / "Library" / "LaunchAgents"
            launch_dir.mkdir(parents=True, exist_ok=True)

            # 1. 创建包装脚本
            script_dir = Path.home() / "Library" / "Application Support" / "Codex助手"
            script_dir.mkdir(parents=True, exist_ok=True)
            script_path = script_dir / "launch_chatgpt_cdp.sh"
            script_content = """#!/bin/bash
# Codex助手 生成：以 CDP 调试模式启动 ChatGPT
CHATGPT_APP="/Applications/ChatGPT.app"
if [ ! -d "$CHATGPT_APP" ]; then
    exit 0
fi

# 检查 CDP 端口是否已在监听（避免重复启动）
if lsof -i :9222 >/dev/null 2>&1; then
    exit 0
fi

# 延迟 3 秒等待系统就绪
sleep 3

# 以 CDP 模式启动 ChatGPT
open -a "$CHATGPT_APP" --args --remote-debugging-port=9222
"""
            script_path.write_text(script_content, encoding="utf-8")
            script_path.chmod(0o755)

            # 2. 创建 LaunchAgent（登录时自动执行脚本）
            plist_file = launch_dir / "com.codexhelper.cdp-enabler.plist"
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.codexhelper.cdp-enabler</string>
    <key>ProgramArguments</key>
    <array>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
            plist_file.write_text(plist_content, encoding="utf-8")
            print("[ThemeManager] 已创建 CDP 启动 LaunchAgent（登录后自动以 CDP 模式启动 ChatGPT）")
        except Exception as e:
            print(f"[ThemeManager] 创建 CDP LaunchAgent 失败: {e}")

    def _is_cdp_available(self) -> bool:
        """检查 CDP 端口是否可用"""
        for port in [9222, 9341]:
            try:
                sock = socket.create_connection(("127.0.0.1", port), timeout=1)
                sock.close()
                return True
            except:
                pass
        return False

    def _restart_codex_with_cdp(self) -> bool:
        """重启 ChatGPT.app 并附带 CDP 调试端口参数。
        返回 True 表示 CDP 端口已就绪。
        """
        import time

        chatgpt_app = "/Applications/ChatGPT.app"
        if not Path(chatgpt_app).exists():
            print("[ThemeManager] ChatGPT.app 不存在")
            return False

        # 1. 如果 CDP 已可用，无需重启
        if self._is_cdp_available():
            return True

        # 2. 杀掉现有 ChatGPT 进程（优雅退出）
        try:
            subprocess.run(
                ["pkill", "-f", "ChatGPT.app/Contents/MacOS/ChatGPT"],
                capture_output=True, timeout=5
            )
            time.sleep(2)
        except Exception as e:
            print(f"[ThemeManager] 停止 ChatGPT 失败: {e}")

        # 3. 以 CDP 模式重新启动
        try:
            subprocess.Popen(
                ["open", "-a", chatgpt_app, "--args", "--remote-debugging-port=9222"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("[ThemeManager] 正在以 CDP 模式重启 ChatGPT...")
        except Exception as e:
            print(f"[ThemeManager] 启动 ChatGPT 失败: {e}")
            return False

        # 4. 等待 CDP 端口就绪（最多 20 秒）
        for i in range(20):
            time.sleep(1)
            if self._is_cdp_available():
                # 额外等待页面加载
                time.sleep(3)
                print(f"[ThemeManager] CDP 端口已就绪（等待 {i+1} 秒）")
                return True

        print("[ThemeManager] CDP 端口等待超时")
        return False

    def _ensure_cdp_available(self, auto_restart=True) -> bool:
        """确保 CDP 端口可用，必要时自动重启 ChatGPT。
        返回 True 表示 CDP 已就绪可以注入主题。
        """
        if self._is_cdp_available():
            return True

        if not auto_restart:
            return False

        # 检查 ChatGPT 是否安装
        if not Path("/Applications/ChatGPT.app").exists():
            return False

        # 自动重启 ChatGPT 并启用 CDP
        return self._restart_codex_with_cdp()

    def _start_watcher(self):
        """启动后台监控线程，检测 Codex 启动后自动注入主题"""
        if self._watcher_started:
            return
        self._watcher_started = True

        import threading

        def watcher_loop():
            import time
            while True:
                try:
                    # 检测 CDP 端口
                    cdp_available = self._is_cdp_available()

                    # 如果 CDP 从不可用变为可用，说明 Codex 刚启动
                    if cdp_available and not self._last_cdp_state:
                        # Codex 刚启动，等待页面加载
                        time.sleep(self._WATCHER_INITIAL_WAIT)
                        # 检查是否有已保存的主题
                        config = self._load_config()
                        saved_theme = config.get("current_theme")
                        if saved_theme:
                            print(f"[ThemeWatcher] Codex 已启动，自动应用主题: {saved_theme}")
                            self._watcher_inject_with_retries(saved_theme, config)

                    self._last_cdp_state = cdp_available
                except Exception as e:
                    print(f"[ThemeWatcher] 监控异常: {e}")

                time.sleep(5)

        t = threading.Thread(target=watcher_loop, daemon=True)
        t.start()

    def _watcher_inject_with_retries(self, theme_id: str, config: dict):
        """带重试和页面就绪检测的主题注入。

        当 Codex 重启后，SPA 页面可能需要数秒才能完全加载。
        此方法会多次尝试注入，直到成功或重试次数用完。
        """
        import time

        for attempt in range(self._WATCHER_MAX_RETRIES + 1):
            try:
                css_content, theme_data, theme_dir = self._resolve_theme_full(theme_id, config)
                if not css_content:
                    print(f"[ThemeWatcher] 无法获取主题 CSS: {theme_id}")
                    return

                # 检查页面是否已就绪（DOM 元素是否存在）
                if self._is_codex_page_ready():
                    self._inject_css_to_codex(css_content, theme_data, theme_dir)
                    print(f"[ThemeWatcher] 主题已自动注入: {theme_id} (第 {attempt+1} 次尝试)")
                    return
                else:
                    print(f"[ThemeWatcher] 页面尚未就绪，等待重试 (第 {attempt+1} 次)")

            except Exception as e:
                print(f"[ThemeWatcher] 注入失败 (第 {attempt+1} 次): {e}")

            # 如果还有重试机会，等待后重试
            if attempt < self._WATCHER_MAX_RETRIES:
                delay = self._WATCHER_RETRY_DELAYS[min(attempt, len(self._WATCHER_RETRY_DELAYS) - 1)]
                time.sleep(delay)

        print(f"[ThemeWatcher] 主题注入失败，已用完 {self._WATCHER_MAX_RETRIES + 1} 次重试")

    def _create_ssl_context(self) -> ssl.SSLContext:
        """创建 SSL 上下文，兼容证书缺失的环境"""
        try:
            import certifi
            return ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            pass
        # 尝试默认证书
        try:
            ctx = ssl.create_default_context()
            # 测试请求验证是否可用
            test_req = urllib.request.Request("https://api.github.com", headers={"User-Agent": "test"})
            with urllib.request.urlopen(test_req, timeout=3) as resp:
                resp.read()
            return ctx
        except Exception:
            # 回退到不验证证书（开发环境兼容）
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx

    def _load_config(self) -> dict:
        """加载主题配置"""
        config_paths = [
            THEME_CONFIG_FILE,  # 主路径
            Path.home() / "Library" / "Application Support" / "Codex助手" / "theme_config.json",  # 备选路径
            Path.home() / ".codex-helper" / "theme_config.json",  # 简化路径
            Path(tempfile.gettempdir()) / "codex_helper_theme_config.json"  # 临时路径
        ]
        
        for config_file in config_paths:
            if config_file.exists():
                try:
                    return json.loads(config_file.read_text(encoding="utf-8"))
                except Exception:
                    continue
        
        return {}

    def _save_config(self, data: dict):
        """保存主题配置"""
        config_paths = [
            THEME_CONFIG_FILE,  # 主路径
            Path.home() / "Library" / "Application Support" / "Codex助手" / "theme_config.json",  # 备选路径
            Path.home() / ".codex-helper" / "theme_config.json"  # 简化路径
        ]
        
        for config_file in config_paths:
            try:
                config_file.parent.mkdir(parents=True, exist_ok=True)
                config_file.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                return  # 成功后立即返回
            except (PermissionError, OSError) as e:
                continue  # 失败后尝试下一个路径
        
        # 如果所有路径都失败，使用临时文件
        temp_file = Path(tempfile.gettempdir()) / "codex_helper_theme_config.json"
        temp_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def check_baseline(self) -> dict:
        """检查主题功能状态（不再限制使用）"""
        results = {
            "codex_installed": False,
            "codex_launched": False,
            "cdp_available": False,
            "all_passed": True,  # 始终允许使用
            "message": "主题功能可用"
        }

        # 检查 Codex 是否安装（仅作状态显示）
        codex_app = Path("/Applications/ChatGPT.app")
        results["codex_installed"] = codex_app.exists()

        # 检查 Codex 是否启动过
        config_toml = Path.home() / ".codex" / "config.toml"
        results["codex_launched"] = config_toml.exists()

        # 检查 CDP 端口是否可用
        if self._is_cdp_available():
            results["cdp_available"] = True
            results["message"] = "Codex 已就绪，可立即应用主题"
        else:
            results["cdp_available"] = False
            results["message"] = "点击应用主题时会自动以调试模式启动 Codex"

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

    def get_builtin_themes(self) -> list[dict]:
        """获取内置主题列表（含背景缩略图 base64）"""
        themes = []
        if not BUILTIN_THEMES_DIR.exists():
            return themes

        for theme_dir in sorted(BUILTIN_THEMES_DIR.iterdir()):
            if not theme_dir.is_dir():
                continue
            theme_json = theme_dir / "theme.json"
            if not theme_json.exists():
                continue
            try:
                data = json.loads(theme_json.read_text(encoding="utf-8"))
                theme_id = f"builtin-{data.get('id', theme_dir.name)}"

                # 获取背景图缩略图（base64 编码）
                thumb_b64 = self._get_thumbnail_base64(theme_dir)

                themes.append({
                    "id": theme_id,
                    "name": data.get("name", theme_dir.name),
                    "author": data.get("author", "Codex助手"),
                    "appearance": data.get("appearance", "auto"),
                    "thumbnail": thumb_b64,
                    "dir_name": theme_dir.name,
                })
            except Exception:
                pass
        return themes

    def _get_thumbnail_base64(self, theme_dir: Path) -> Optional[str]:
        """获取主题缩略图的 base64 编码（用于前端直接展示）"""
        # 先查找缩略图
        for ext in ["png", "jpg", "jpeg", "webp"]:
            thumb = theme_dir / f"thumbnail.{ext}"
            if thumb.exists():
                return self._encode_image_base64(thumb)
        # 使用背景图
        bg_path = self._find_background_image(theme_dir)
        if bg_path:
            return self._encode_image_base64(bg_path)
        return None

    def _encode_image_base64(self, image_path: Path) -> Optional[str]:
        """将图片文件编码为 base64 data URL"""
        try:
            data = image_path.read_bytes()
            b64 = base64.b64encode(data).decode("utf-8")
            ext = image_path.suffix.lower().replace(".", "")
            if ext in ["jpg", "jpeg"]:
                mime = "image/jpeg"
            elif ext == "png":
                mime = "image/png"
            elif ext == "webp":
                mime = "image/webp"
            else:
                mime = f"image/{ext}"
            return f"data:{mime};base64,{b64}"
        except Exception:
            return None

    def build_builtin_theme_css(self, dir_name: str) -> Optional[str]:
        """根据内置主题目录名构建完整 CSS（含背景图 base64）"""
        theme_dir = BUILTIN_THEMES_DIR / dir_name
        if not theme_dir.exists():
            return None

        theme_json = theme_dir / "theme.json"
        if not theme_json.exists():
            return None

        try:
            theme_data = json.loads(theme_json.read_text(encoding="utf-8"))
        except Exception:
            return None

        return self._build_theme_css(theme_dir, theme_data)

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

        # 检查是否是内置主题
        if self.current_theme.startswith("builtin-"):
            # 先从内置主题目录查找（新方式）
            for theme_info in self.get_builtin_themes():
                if theme_info["id"] == self.current_theme:
                    config = self._load_config()
                    return {
                        "id": self.current_theme,
                        "name": config.get("current_theme_name") or theme_info["name"],
                        "author": theme_info.get("author", "Built-in"),
                        "thumbnail": theme_info.get("thumbnail"),
                    }

            # 回退：旧版硬编码内置主题
            old_builtin = {
                "builtin-default": {"name": "默认"},
                "builtin-dark": {"name": "深色"},
                "builtin-nature": {"name": "自然"},
                "builtin-ocean": {"name": "海洋"}
            }
            if self.current_theme in old_builtin:
                config = self._load_config()
                return {
                    "id": self.current_theme,
                    "name": config.get("current_theme_name") or old_builtin[self.current_theme]["name"],
                    "author": "Built-in",
                    "thumbnail": None
                }
        
        # 外部主题：从主题库目录读取
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

            # 3. 保存当前主题配置（始终保存）
            config = self._load_config()
            config["current_theme"] = theme_id
            config["last_applied"] = self._now_iso()
            self._save_config(config)
            self.current_theme = theme_id

            # 4. 确保 CDP 可用（必要时自动重启 ChatGPT）
            css_content = self._build_theme_css(theme_dir, theme_data)
            if self._ensure_cdp_available(auto_restart=True):
                # CDP 已就绪，立即注入主题
                self._inject_css_to_codex(css_content, theme_data, theme_dir)
                result["success"] = True
                result["message"] = "主题已立即应用"
            else:
                # CDP 不可用（ChatGPT 未安装或启动失败），主题已保存
                result["success"] = True
                result["message"] = "主题已保存，打开 Codex 后生效"

        except Exception as e:
            result["message"] = str(e)

        return result

    def _resolve_theme_css(self, theme_id: str, config: dict) -> Optional[str]:
        """根据主题 ID 解析并构建 CSS（支持内置主题和外部主题）"""
        css, _, _ = self._resolve_theme_full(theme_id, config)
        return css

    def _resolve_theme_full(self, theme_id: str, config: dict) -> tuple:
        """根据主题 ID 解析并构建完整主题信息（CSS + theme_data + theme_dir）。
        返回 (css_content, theme_data, theme_dir) 或 (None, None, None)。
        """
        if not theme_id:
            return (None, None, None)

        # 内置主题（builtin- 前缀）
        if theme_id.startswith("builtin-"):
            # 先尝试从内置主题目录构建（新方式，含背景图）
            dir_name = config.get("builtin_dir_name", "")
            if dir_name:
                theme_dir = BUILTIN_THEMES_DIR / dir_name
                if theme_dir.exists():
                    theme_json = theme_dir / "theme.json"
                    if theme_json.exists():
                        try:
                            theme_data = json.loads(theme_json.read_text(encoding="utf-8"))
                            css = self._build_theme_css(theme_dir, theme_data)
                            if css:
                                return (css, theme_data, theme_dir)
                        except Exception:
                            pass

            # 回退：使用配置中存储的 CSS（旧方式，简单配色）
            stored_css = config.get("builtin_css", "")
            if stored_css:
                return (stored_css, {}, None)

            return (None, None, None)

        # 外部主题（从主题库目录读取）
        theme_dir = THEME_LIBRARY / theme_id
        if not theme_dir.exists():
            # 尝试在子目录中查找
            for d in THEME_LIBRARY.iterdir():
                if d.is_dir():
                    sub_json = d / "theme.json"
                    if sub_json.exists():
                        try:
                            data = json.loads(sub_json.read_text(encoding="utf-8"))
                            if data.get("id") == theme_id or d.name == theme_id:
                                theme_dir = d
                                break
                        except Exception:
                            pass

        if not theme_dir.exists():
            return (None, None, None)

        theme_json = theme_dir / "theme.json"
        if not theme_json.exists():
            return (None, None, None)

        try:
            theme_data = json.loads(theme_json.read_text(encoding="utf-8"))
            css = self._build_theme_css(theme_dir, theme_data)
            return (css, theme_data, theme_dir)
        except Exception:
            return (None, None, None)

    # 原版 CSS 占位符 → 实际 CSS 选择器映射表
    # 来源：https://github.com/Fei-Away/Codex-Dream-Skin/tools/selectors.json
    # 适配 Codex 最新 DOM 结构（CDP 检测结果）
    SELECTOR_TOKENS = {
        "__DREAM_SELECTOR_SHELL_MAIN__": "main[class*='MainContentSurface']",
        "__DREAM_SELECTOR_LEFT_PANEL__": "aside.app-shell-left-panel",
        "__DREAM_SELECTOR_HEADER_TINT__": "header[class*='draggable']",
        "__DREAM_SELECTOR_HOME_ICON__": '[data-testid="home-icon"]',
        "__DREAM_SELECTOR_HOME_ROUTE__": '[role="main"]:has([data-testid="home-icon"])',
        "__DREAM_SELECTOR_HOME_ROUTE_CSS__": '[role="main"]',
        "__DREAM_SELECTOR_HOME_BANNERS__": ".home-banners",
        "__DREAM_SELECTOR_COMPOSER_CHROME__": "[class*='ComposerLayoutBody']",
        "__DREAM_SELECTOR_COMPOSER_TOOLBAR__": "[class*='ComposerLayoutFooter']",
        "__DREAM_SELECTOR_HOME_UTILITY__": '[class*="_homeUtilityBar_"]',
        "__DREAM_SELECTOR_GAME_SOURCE__": '[data-feature="game-source"]',
        "__DREAM_SELECTOR_HOME_SUGGESTIONS__": ".group\\/home-suggestions",
        "__DREAM_SELECTOR_PROJECT_SELECTOR__": ".group\\/project-selector",
        "__DREAM_SELECTOR_MARKDOWN__": '[class*="_markdown"]',
        "__DREAM_SELECTOR_THREAD_SURFACE__": ".thread-scroll-container",
        "__DREAM_SELECTOR_MESSAGE__": "[data-message-author-role]",
        "__DREAM_SELECTOR_APPEARANCE_RADIO__": 'input[name="appearance-theme"]',
        "__DREAM_SELECTOR_OVERLAY_MENU__": '[role="menu"]',
        "__DREAM_SELECTOR_OVERLAY_DIALOG__": '[role="dialog"]',
        "__DREAM_SELECTOR_OVERLAY_POPPER__": "[data-radix-popper-content-wrapper]",
        "__DREAM_SELECTOR_MAIN_CONTENT_TOP_FADE__": "[class*='MainContentTopFade']",
    }

    def _build_theme_css(self, theme_dir: Path, theme_data: dict) -> str:
        """构建主题 CSS：使用原版 Codex-Dream-Skin 完整 CSS（56KB）作为基础样式。

        原版 CSS 包含数百个选择器，覆盖 Codex 全部 UI 元素。
        CSS 中的 __DREAM_SELECTOR_*__ 占位符需替换为实际选择器。
        主题颜色通过 CSS 变量在注入 JS 中设置。
        """
        # 加载原版基础 CSS（56KB，包含所有选择器和样式规则）
        try:
            base_css = DREAM_SKIN_BASE_CSS.read_text(encoding="utf-8")
        except Exception as e:
            print(f"[ThemeManager] 加载基础 CSS 失败: {e}")
            base_css = ""

        # 替换 CSS 中的占位符为实际选择器（关键步骤！）
        for token, selector in self.SELECTOR_TOKENS.items():
            base_css = base_css.replace(token, selector)

        # 追加主题自带的 CSS（如果有）
        if theme_dir:
            theme_css_file = theme_dir / "theme.css"
            if theme_css_file.exists():
                custom_css = theme_css_file.read_text(encoding="utf-8")
                base_css += "\n/* 主题自定义 CSS */\n" + custom_css + "\n"

        return base_css

    def _build_injection_js(self, css_content: str, theme_data: dict, bg_base64: str = "") -> str:
        """构建完整的注入 JS（参照原版 Codex-Dream-Skin renderer-inject.js）
        
        核心策略：
        1. 注入原版 56KB 完整 CSS（包含所有选择器和样式规则）
        2. 通过 CSS 变量覆盖主题颜色（--ds-bg, --ds-panel 等 + RGB 变体）
        3. 将背景图 base64 → Blob URL，设置 --dream-skin-art
        4. 设置 html 属性激活主题（data-dream-skin, data-dream-shell, data-dream-art-safe 等）
        5. MutationObserver 持续维护主题状态
        """
        colors = theme_data.get("colors", {})
        art = theme_data.get("art", {})
        appearance = theme_data.get("appearance", "auto")

        # 提取颜色值（使用原版默认值作为回退）
        bg_color = colors.get("background", "#111318")
        panel_color = colors.get("panel", "#191c22")
        panel_alt_color = colors.get("panelAlt", "#20242b")
        accent_color = colors.get("accent", "#8298a3")
        accent_alt_color = colors.get("accentAlt", "#a0adb3")
        secondary_color = colors.get("secondary", "#8da397")
        highlight_color = colors.get("highlight", "#9d94a3")
        text_color = colors.get("text", "#edf0f1")
        muted_color = colors.get("muted", "#a3aaae")
        line_color = colors.get("line", "rgba(130, 152, 163, .24)")

        focus_x = art.get("focusX", 0.5)
        focus_y = art.get("focusY", 0.5)
        safe_area = art.get("safeArea", "left")
        task_mode = art.get("taskMode", "ambient")

        # hex → RGB 三元组（用于 --ds-*-rgb 变量）
        def hex_to_rgb(hex_str):
            h = str(hex_str).lstrip("#")
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            try:
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                return f"{r} {g} {b}"
            except Exception:
                return None

        bg_rgb = hex_to_rgb(bg_color) or "17 19 24"
        panel_rgb = hex_to_rgb(panel_color) or "25 28 34"
        panel_alt_rgb = hex_to_rgb(panel_alt_color) or "32 36 43"
        accent_rgb = hex_to_rgb(accent_color) or "130 152 163"
        accent_alt_rgb = hex_to_rgb(accent_alt_color) or "160 173 179"
        secondary_rgb = hex_to_rgb(secondary_color) or "141 163 151"
        highlight_rgb = hex_to_rgb(highlight_color) or "157 148 163"
        text_rgb = hex_to_rgb(text_color) or "237 240 241"
        muted_rgb = hex_to_rgb(muted_color) or "163 170 174"

        focus_x_pct = f"{focus_x * 100:.2f}%"
        focus_y_pct = f"{focus_y * 100:.2f}%"

        # 构建 JS 代码（使用模板替换，避免转义问题）
        js_template = """(function() {
  var CSS_TEXT = __CSS_TEXT__;
  var ART_BASE64 = __ART_BASE64__;
  var APPEARANCE = __APPEARANCE__;
  var STYLE_ID = "codex-dream-skin-style";
  var SHEET_FLAG = "_dreamSkinSheet";
  var STATE_KEY = "__CODEX_DREAM_SKIN_STATE__";

  // 主题颜色变量（hex + RGB 三元组）
  var THEME_VARS = {
    "--ds-bg": __BG__, "--ds-panel": __PANEL__, "--ds-panel-2": __PANEL_ALT__,
    "--ds-green": __ACCENT__, "--ds-lime": __ACCENT_ALT__,
    "--ds-cyan": __SECONDARY__, "--ds-purple": __HIGHLIGHT__,
    "--ds-text": __TEXT__, "--ds-muted": __MUTED__, "--ds-line": __LINE__,
    "--ds-bg-rgb": __BG_RGB__, "--ds-panel-rgb": __PANEL_RGB__,
    "--ds-panel-2-rgb": __PANEL_ALT_RGB__, "--ds-accent-rgb": __ACCENT_RGB__,
    "--ds-accent-alt-rgb": __ACCENT_ALT_RGB__, "--ds-secondary-rgb": __SECONDARY_RGB__,
    "--ds-highlight-rgb": __HIGHLIGHT_RGB__, "--ds-text-rgb": __TEXT_RGB__,
    "--ds-muted-rgb": __MUTED_RGB__,
    "--ds-accent": "var(--ds-green)", "--ds-accent-soft": "var(--ds-lime)",
    "--ds-secondary": "var(--ds-cyan)", "--ds-highlight": "var(--ds-purple)",
    "--ds-on-accent": "rgb(var(--ds-bg-rgb) / 1)"
  };
  var FOCUS_X = __FOCUS_X__;
  var FOCUS_Y = __FOCUS_Y__;
  var SAFE_AREA = __SAFE_AREA__;
  var TASK_MODE = __TASK_MODE__;

  // 幂等清理
  var previous = window[STATE_KEY];
  if (previous && typeof previous.cleanup === "function") {
    try { previous.cleanup(); } catch(e) {}
  }

  // 1. 背景图：base64 -> Blob URL
  var artUrl = "";
  if (ART_BASE64) {
    try {
      var comma = ART_BASE64.indexOf(",");
      var mime = /^data:([^;,]+)/.exec(ART_BASE64) || ["", "image/png"];
      var binary = atob(ART_BASE64.slice(comma + 1));
      var bytes = new Uint8Array(binary.length);
      for (var i = 0; i < binary.length; i++) { bytes[i] = binary.charCodeAt(i); }
      artUrl = URL.createObjectURL(new Blob([bytes], { type: mime[1] }));
    } catch(e) {
      console.warn("[DreamSkin] Blob URL creation failed:", e);
      artUrl = ART_BASE64;
    }
  }

  // 2. 注入 CSS（<style> 元素 + adoptedStyleSheets 双保险）
  function installStyle() {
    try {
      var oldStyle = document.getElementById(STYLE_ID);
      if (oldStyle) oldStyle.remove();
      try {
        var retained = [];
        for (var i = 0; i < document.adoptedStyleSheets.length; i++) {
          if (!document.adoptedStyleSheets[i][SHEET_FLAG]) { retained.push(document.adoptedStyleSheets[i]); }
        }
        document.adoptedStyleSheets = retained;
      } catch(e) {}
      var styleNode = document.createElement("style");
      styleNode.id = STYLE_ID;
      styleNode.textContent = CSS_TEXT;
      (document.head || document.documentElement).appendChild(styleNode);
      try {
        var sheet = new CSSStyleSheet();
        sheet.replaceSync(CSS_TEXT);
        sheet[SHEET_FLAG] = true;
        document.adoptedStyleSheets = (document.adoptedStyleSheets || []).concat([sheet]);
      } catch(e) {}
    } catch(e) { console.warn("[DreamSkin] CSS injection failed:", e); }
  }

  // 3. 应用主题状态
  function applyTheme() {
    var root = document.documentElement;
    root.setAttribute("data-dream-skin", "active");
    var shell = APPEARANCE;
    if (shell !== "dark" && shell !== "light") {
      if (root.classList.contains("electron-dark")) shell = "dark";
      else if (root.classList.contains("electron-light")) shell = "light";
      else { try { shell = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; } catch(e) { shell = "dark"; } }
    }
    root.setAttribute("data-dream-shell", shell);
    if (artUrl) { root.style.setProperty("--dream-skin-art", 'url("' + artUrl + '")'); }
    root.style.setProperty("--dream-skin-focus-x", FOCUS_X);
    root.style.setProperty("--dream-skin-focus-y", FOCUS_Y);
    root.style.setProperty("--dream-art-focus-x", FOCUS_X);
    root.style.setProperty("--dream-art-focus-y", FOCUS_Y);
    root.style.setProperty("--dream-art-position", FOCUS_X + " " + FOCUS_Y);
    root.style.setProperty("--dream-skin-art-position", FOCUS_X + " " + FOCUS_Y);
    root.setAttribute("data-dream-art-safe", SAFE_AREA);
    root.setAttribute("data-dream-art-safe-area", SAFE_AREA);
    root.setAttribute("data-dream-task-mode", TASK_MODE);
    root.setAttribute("data-dream-art-task-mode", TASK_MODE);
    try { root.setAttribute("data-dream-art-wide", (window.innerWidth || 0) > 800 ? "true" : "false"); } catch(e) {}
    for (var name in THEME_VARS) { root.style.setProperty(name, THEME_VARS[name]); }
    root.style.setProperty("--ds-theme-surface-radius", "12px");
    root.style.setProperty("--ds-theme-surface-opacity", "1");
    root.style.setProperty("--ds-theme-surface-blur", "0px");
    root.style.setProperty("--ds-theme-surface-border-alpha", "0.14");
    root.style.setProperty("--ds-theme-font-family", "system");
    root.style.setProperty("--ds-theme-font-scale", "1");
    root.style.setProperty("--ds-theme-image-zoom", "1");
    root.style.setProperty("--ds-theme-image-dim", "0");
    root.style.setProperty("--ds-theme-density-scale", "standard");
    root.style.setProperty("--ds-theme-motion-level", "standard");
    root.style.setProperty("--codex-titlebar-tint", "rgb(var(--ds-panel-rgb) / .90)");

    // 直接在 body 上设置内联 !important 背景图
    // Codex 的 .electron-opaque body 规则会覆盖 CSS 中的背景图，
    // 只有内联 !important 才能确保背景图始终显示
    if (artUrl && document.body) {
      document.body.style.setProperty("background-image", 'url("' + artUrl + '")', "important");
      document.body.style.setProperty("background-size", "cover", "important");
      document.body.style.setProperty("background-position", FOCUS_X + " " + FOCUS_Y, "important");
      document.body.style.setProperty("background-repeat", "no-repeat", "important");
      document.body.style.setProperty("background-attachment", "fixed", "important");
    }
  }

  // 4. 标记 Codex DOM 元素
  function markParts() {
    try {
      var selectors = {
        "sidebar": ["aside.app-shell-left-panel", "aside[class*='left-panel']", "nav[class*='sidebar']"],
        "header": ["header.app-header-tint", "header[class*='header-tint']", "header[class*='app-header']", "header[class*='shell-header']", "header[class*='draggable']", "main[class*='MainContentSurface'] > header", "div[class*='app-header']", "div[class*='header-tint']", "header.sticky"],
        "composer": [".composer-surface-chrome", "[class*='composer-chrome']", "[class*='composer-surface']", "[class*='ComposerLayoutBody']", "[class*='ComposerLayoutRoot']", "[class*='ComposerLayoutFooter']", "form[class*='composer']", "[data-testid*='composer']"],
        "main": ["main.main-surface", "main[class*='main-surface']", "main[class*='MainContentSurface']"],
        "home": ["[class*='home-route']", "[class*='HomeRoute']"],
        "thread": ["[class*='thread-surface']", "[class*='thread-scroll']", ".thread-scroll-container"],
        "project-list": ["[class*='project-selector']", "[class*='ProjectSelector']"]
      };
      for (var part in selectors) {
        for (var i = 0; i < selectors[part].length; i++) {
          var els = document.querySelectorAll(selectors[part][i]);
          for (var j = 0; j < els.length; j++) { els[j].setAttribute("data-ds-part", part); }
        }
      }
      // 单独标记 [role="main"] 为 home（不是 main），避免与 shell main 冲突导致背景图重复
      var homeRoute = document.querySelector('[role="main"]');
      if (homeRoute && !homeRoute.hasAttribute('data-ds-part')) {
        homeRoute.setAttribute('data-ds-part', 'home');
      }
    } catch(e) {}
  }

  // 5. 初始化
  function init() { installStyle(); applyTheme(); markParts(); }
  init();

  // 6. MutationObserver 持续维护
  var observer = new MutationObserver(function(mutations) {
    var needsReapply = false;
    for (var i = 0; i < mutations.length; i++) {
      if (mutations[i].addedNodes.length > 0) { needsReapply = true; break; }
    }
    if (needsReapply) {
      if (document.documentElement.getAttribute("data-dream-skin") !== "active") { applyTheme(); }
      if (!document.getElementById(STYLE_ID)) { installStyle(); }
      markParts();
    }
    // 检查 body 背景图是否被 Codex 覆盖，如果是则重新设置
    if (artUrl && document.body) {
      var currentBg = document.body.style.getPropertyValue("background-image");
      var expectedBg = 'url("' + artUrl + '")';
      if (currentBg !== expectedBg) {
        document.body.style.setProperty("background-image", expectedBg, "important");
        document.body.style.setProperty("background-size", "cover", "important");
        document.body.style.setProperty("background-position", FOCUS_X + " " + FOCUS_Y, "important");
        document.body.style.setProperty("background-repeat", "no-repeat", "important");
        document.body.style.setProperty("background-attachment", "fixed", "important");
      }
    }
  });
  observer.observe(document.body || document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["style", "class"] });

  // 7. 定期检查（兜底）
  var checkInterval = setInterval(function() {
    if (document.documentElement.getAttribute("data-dream-skin") !== "active") { applyTheme(); }
    if (!document.getElementById(STYLE_ID)) { installStyle(); }
    // 兜底：确保 body 背景图始终存在
    if (artUrl && document.body) {
      var currentBg = document.body.style.getPropertyValue("background-image");
      var expectedBg = 'url("' + artUrl + '")';
      if (currentBg !== expectedBg) {
        document.body.style.setProperty("background-image", expectedBg, "important");
        document.body.style.setProperty("background-size", "cover", "important");
        document.body.style.setProperty("background-position", FOCUS_X + " " + FOCUS_Y, "important");
        document.body.style.setProperty("background-repeat", "no-repeat", "important");
        document.body.style.setProperty("background-attachment", "fixed", "important");
      }
    }
  }, 3000);

  // 8. 清理函数
  window[STATE_KEY] = {
    cleanup: function() {
      try {
        observer.disconnect();
        clearInterval(checkInterval);
        var s = document.getElementById(STYLE_ID);
        if (s) s.remove();
        var root = document.documentElement;
        root.removeAttribute("data-dream-skin");
        root.removeAttribute("data-dream-shell");
        root.removeAttribute("data-dream-art-safe");
        root.removeAttribute("data-dream-art-safe-area");
        root.removeAttribute("data-dream-task-mode");
        root.removeAttribute("data-dream-art-task-mode");
        root.removeAttribute("data-dream-art-wide");
        var props = ["--dream-skin-art", "--dream-skin-focus-x", "--dream-skin-focus-y",
          "--dream-art-focus-x", "--dream-art-focus-y", "--dream-art-position",
          "--dream-skin-art-position", "--ds-theme-surface-radius",
          "--ds-theme-surface-opacity", "--ds-theme-surface-blur",
          "--ds-theme-surface-border-alpha", "--ds-theme-font-family",
          "--ds-theme-font-scale", "--ds-theme-image-zoom",
          "--ds-theme-image-dim", "--ds-theme-density-scale",
          "--ds-theme-motion-level", "--codex-titlebar-tint"];
        for (var i = 0; i < props.length; i++) { root.style.removeProperty(props[i]); }
        for (var name in THEME_VARS) { root.style.removeProperty(name); }
        // 清理 body 上的内联背景样式
        if (document.body) {
          var bgProps = ["background-image", "background-size", "background-position",
            "background-repeat", "background-attachment"];
          for (var i = 0; i < bgProps.length; i++) { document.body.style.removeProperty(bgProps[i]); }
        }
        try {
          var kept = [];
          for (var i = 0; i < document.adoptedStyleSheets.length; i++) {
            if (!document.adoptedStyleSheets[i][SHEET_FLAG]) { kept.push(document.adoptedStyleSheets[i]); }
          }
          document.adoptedStyleSheets = kept;
        } catch(e) {}
        var parts = document.querySelectorAll("[data-ds-part]");
        for (var i = 0; i < parts.length; i++) { parts[i].removeAttribute("data-ds-part"); }
      } catch(e) {}
    }
  };
})();"""
        js = js_template
        js = js.replace("__CSS_TEXT__", json.dumps(css_content))
        js = js.replace("__ART_BASE64__", json.dumps(bg_base64))
        js = js.replace("__APPEARANCE__", json.dumps(appearance))
        js = js.replace("__BG__", json.dumps(bg_color))
        js = js.replace("__PANEL__", json.dumps(panel_color))
        js = js.replace("__PANEL_ALT__", json.dumps(panel_alt_color))
        js = js.replace("__ACCENT__", json.dumps(accent_color))
        js = js.replace("__ACCENT_ALT__", json.dumps(accent_alt_color))
        js = js.replace("__SECONDARY__", json.dumps(secondary_color))
        js = js.replace("__HIGHLIGHT__", json.dumps(highlight_color))
        js = js.replace("__TEXT__", json.dumps(text_color))
        js = js.replace("__MUTED__", json.dumps(muted_color))
        js = js.replace("__LINE__", json.dumps(line_color))
        js = js.replace("__BG_RGB__", json.dumps(bg_rgb))
        js = js.replace("__PANEL_RGB__", json.dumps(panel_rgb))
        js = js.replace("__PANEL_ALT_RGB__", json.dumps(panel_alt_rgb))
        js = js.replace("__ACCENT_RGB__", json.dumps(accent_rgb))
        js = js.replace("__ACCENT_ALT_RGB__", json.dumps(accent_alt_rgb))
        js = js.replace("__SECONDARY_RGB__", json.dumps(secondary_rgb))
        js = js.replace("__HIGHLIGHT_RGB__", json.dumps(highlight_rgb))
        js = js.replace("__TEXT_RGB__", json.dumps(text_rgb))
        js = js.replace("__MUTED_RGB__", json.dumps(muted_rgb))
        js = js.replace("__FOCUS_X__", json.dumps(focus_x_pct))
        js = js.replace("__FOCUS_Y__", json.dumps(focus_y_pct))
        js = js.replace("__SAFE_AREA__", json.dumps(safe_area))
        js = js.replace("__TASK_MODE__", json.dumps(task_mode))

        return js


    def _find_background_image(self, theme_dir: Path, theme_data: dict = None) -> Optional[Path]:
        """查找主题背景图（优先使用 theme.json 中指定的 image 字段）"""
        # 优先检查 theme.json 中的 image 字段
        if theme_data:
            image_name = theme_data.get("image", "")
            if image_name:
                img_path = theme_dir / image_name
                if img_path.exists():
                    return img_path

        # 回退：按常见名称查找
        for name in ["background", "bg", "wallpaper"]:
            for ext in ["webp", "jpg", "jpeg", "png"]:
                path = theme_dir / f"{name}.{ext}"
                if path.exists():
                    return path
        return None

    def _inject_css_to_codex(self, css_content: str, theme_data: dict = None, theme_dir: Path = None):
        """通过 CDP 注入主题到 Codex（参照 Codex-Dream-Skin 实现）
        
        1. 将背景图转 base64（避免 file:// 被 CSP 拦截）
        2. 构建 JS 注入脚本（base64→Blob URL + adoptedStyleSheets + MutationObserver）
        3. 通过 Runtime.evaluate 执行注入
        """
        ws_url = self._find_codex_cdp_page()
        if not ws_url:
            raise ValueError("未找到 Codex 调试页面，请确保 Codex 已启动")

        # 获取背景图的 base64 编码
        bg_base64 = ""
        if theme_dir:
            bg_path = self._find_background_image(theme_dir, theme_data)
            if bg_path:
                bg_base64 = self._encode_image_base64(bg_path) or ""

        if theme_data is None:
            theme_data = {}

        # 构建完整的注入 JS
        js_code = self._build_injection_js(css_content, theme_data, bg_base64)

        # 批量发送：Page.enable → Runtime.enable → Runtime.evaluate
        # 不需要 setBypassCSP，因为 Runtime.evaluate 本身在特权上下文执行，天然绕过 CSP
        self._send_cdp_commands_batch(ws_url, [
            ("Page.enable", {}),
            ("Runtime.enable", {}),
            ("Runtime.evaluate", {"expression": js_code, "returnByValue": False}),
        ])

    def _send_cdp_single(self, ws_url: str, method: str, params: dict):
        """通过 WebSocket 连接发送 CDP 命令（先 Runtime.enable 再执行目标命令）"""
        import socket
        import os
        from urllib.parse import urlparse

        parsed = urlparse(ws_url)
        host = parsed.hostname
        port = parsed.port or 9222

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30)
        sock.connect((host, port))

        try:
            # WebSocket 握手（不发送 Origin 头，避免 Chromium 111+ 的 Origin 检查）
            key = base64.b64encode(os.urandom(16)).decode()
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
            sock.sendall(handshake.encode())

            # 读取握手响应
            resp = b""
            while b"\r\n\r\n" not in resp:
                chunk = sock.recv(4096)
                if not chunk:
                    raise ValueError("WebSocket 握手失败：连接关闭")
                resp += chunk

            resp_str = resp.decode("utf-8", errors="replace")
            if "101" not in resp_str.split("\r\n")[0]:
                raise ValueError(f"WebSocket 握手失败: {resp_str.split(chr(13))[0]}")

            # 1. 先发送 Runtime.enable
            enable_cmd = json.dumps({"id": 1, "method": "Runtime.enable", "params": {}})
            sock.sendall(self._build_websocket_frame(enable_cmd))
            self._read_cdp_response(sock, 1, timeout=5)

            # 2. 发送目标命令
            command = json.dumps({"id": 2, "method": method, "params": params})
            frame = self._build_websocket_frame(command)
            # 分块发送大帧
            chunk_size = 65536
            for i in range(0, len(frame), chunk_size):
                sock.sendall(frame[i:i + chunk_size])

            # 读取响应
            try:
                response = self._read_cdp_response(sock, 2, timeout=15)
                if response and "error" in response:
                    print(f"[CDP] {method} 返回错误: {response['error']}")
            except Exception as e:
                print(f"[CDP] 读取响应超时（命令可能已执行）: {e}")

        finally:
            sock.close()

    def _is_codex_page_ready(self) -> bool:
        """检查 Codex 页面是否已完全加载（DOM 元素是否可用）。

        通过 CDP 执行简单 JS 检测关键 DOM 元素是否存在，
        避免 SPA 尚未加载完成时就注入主题导致失败。
        """
        try:
            ws_url = self._find_codex_cdp_page()
            if not ws_url:
                return False

            # 通过 Runtime.evaluate 检测页面是否已渲染关键元素
            check_js = """
                (function() {
                    // 检查 body 是否存在且有子元素
                    if (!document.body || document.body.children.length === 0) return false;
                    // 检查 #root 或 #__next 等 SPA 根节点是否存在
                    var root = document.getElementById('root') || document.getElementById('__next') || document.querySelector('[id*="root"]');
                    if (!root) return false;
                    // 检查根节点是否有子元素（说明 SPA 已渲染）
                    if (root.children.length === 0) return false;
                    return true;
                })()
            """

            # 使用 _send_cdp_command_safe 发送检测命令
            import socket
            import os
            from urllib.parse import urlparse

            parsed = urlparse(ws_url)
            host = parsed.hostname
            port = parsed.port or 9222

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((host, port))

            try:
                key = base64.b64encode(os.urandom(16)).decode()
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
                sock.sendall(handshake.encode())

                resp = b""
                while b"\r\n\r\n" not in resp:
                    chunk = sock.recv(4096)
                    if not chunk:
                        return False
                    resp += chunk

                resp_str = resp.decode("utf-8", errors="replace")
                if "101" not in resp_str.split("\r\n")[0]:
                    return False

                # 发送 Runtime.enable
                enable_cmd = json.dumps({"id": 1, "method": "Runtime.enable", "params": {}})
                sock.sendall(self._build_websocket_frame(enable_cmd))
                self._read_cdp_response(sock, 1, timeout=5)

                # 发送页面就绪检测
                eval_cmd = json.dumps({
                    "id": 2,
                    "method": "Runtime.evaluate",
                    "params": {"expression": check_js, "returnByValue": True}
                })
                sock.sendall(self._build_websocket_frame(eval_cmd))

                response = self._read_cdp_response(sock, 2, timeout=10)
                if response and "result" in response:
                    result = response["result"].get("result", {})
                    return result.get("value", False)
                return False
            finally:
                sock.close()

        except Exception as e:
            print(f"[ThemeWatcher] 页面就绪检测失败: {e}")
            return False

    def _find_codex_cdp_page(self) -> Optional[str]:
        """查找 Codex 的 CDP 调试页面 WebSocket URL"""
        import http.client

        # 尝试多个可能的 CDP 端口
        for port in [9222, 9341]:
            try:
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
                conn.request("GET", "/json")
                resp = conn.getresponse()
                pages = json.loads(resp.read().decode("utf-8"))
                conn.close()

                if not pages:
                    continue

                # 第一优先级：app:// 主页面（不含 initialRoute 参数）
                for page in pages:
                    if page.get("type") != "page":
                        continue
                    ws_url = page.get("webSocketDebuggerUrl")
                    if not ws_url:
                        continue
                    url = page.get("url", "")
                    if url.startswith("app://") and "initialRoute" not in url:
                        return ws_url

                # 第二优先级：任意 app:// 或 codex/chatgpt 页面
                for page in pages:
                    if page.get("type") != "page":
                        continue
                    ws_url = page.get("webSocketDebuggerUrl")
                    if not ws_url:
                        continue
                    url = page.get("url", "")
                    if url.startswith("app://") or "codex" in url.lower() or "chatgpt" in url.lower():
                        return ws_url

                # 回退：取第一个 page 类型
                for page in pages:
                    if page.get("type") == "page":
                        ws_url = page.get("webSocketDebuggerUrl")
                        if ws_url:
                            return ws_url
            except Exception:
                continue

        return None

    def _send_cdp_command_safe(self, ws_url: str, method: str, params: dict):
        """安全发送 CDP 命令（改进的 WebSocket 实现）"""
        import socket
        import os
        from urllib.parse import urlparse

        parsed = urlparse(ws_url)
        host = parsed.hostname
        port = parsed.port or 9222

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((host, port))

        try:
            # WebSocket 握手（使用随机 Key）
            key = base64.b64encode(os.urandom(16)).decode()
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
            sock.sendall(handshake.encode())

            # 读取并验证握手响应
            resp = b""
            while b"\r\n\r\n" not in resp:
                chunk = sock.recv(4096)
                if not chunk:
                    raise ValueError("WebSocket 握手失败：连接关闭")
                resp += chunk

            # 验证 101 状态码
            resp_str = resp.decode("utf-8", errors="replace")
            if "101" not in resp_str.split("\r\n")[0]:
                raise ValueError(f"WebSocket 握手失败: {resp_str.split(chr(13))[0]}")

            # 发送 CDP 命令
            command = json.dumps({
                "id": 1,
                "method": method,
                "params": params
            })

            frame = self._build_websocket_frame(command)
            sock.sendall(frame)

            # 读取响应（跳过非文本帧）
            try:
                self._read_cdp_response(sock, 1, timeout=10)
            except Exception:
                pass

        finally:
            sock.close()

    def _send_cdp_commands_batch(self, ws_url: str, commands: list):
        """通过 WebSocket 连接批量发送多个 CDP 命令"""
        import socket
        import os
        from urllib.parse import urlparse

        parsed = urlparse(ws_url)
        host = parsed.hostname
        port = parsed.port or 9222

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30)
        sock.connect((host, port))

        try:
            key = base64.b64encode(os.urandom(16)).decode()
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
            sock.sendall(handshake.encode())

            resp = b""
            while b"\r\n\r\n" not in resp:
                chunk = sock.recv(4096)
                if not chunk:
                    raise ValueError("WebSocket 握手失败：连接关闭")
                resp += chunk

            resp_str = resp.decode("utf-8", errors="replace")
            if "101" not in resp_str.split("\r\n")[0]:
                raise ValueError(f"WebSocket 握手失败: {resp_str.split(chr(13))[0]}")

            for idx, (method, params) in enumerate(commands, 1):
                command = json.dumps({"id": idx, "method": method, "params": params})
                frame = self._build_websocket_frame(command)
                chunk_size = 65536
                for i in range(0, len(frame), chunk_size):
                    sock.sendall(frame[i:i + chunk_size])
                try:
                    self._read_cdp_response(sock, idx, timeout=10)
                except Exception as e:
                    print(f"[CDP] {method} 响应超时: {e}")

        finally:
            sock.close()

    def _build_websocket_frame(self, data: str) -> bytes:
        """构建 WebSocket 文本帧（客户端发送的帧必须带掩码）"""
        payload = data.encode("utf-8")
        length = len(payload)
        mask_key = os.urandom(4)
        masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

        # FIN + opcode (text) + MASK 位
        frame = bytearray([0x81])

        if length <= 125:
            frame.append(0x80 | length)
        elif length <= 65535:
            frame.extend([0x80 | 126, (length >> 8) & 0xFF, length & 0xFF])
        else:
            frame.append(0x80 | 127)
            for i in range(7, -1, -1):
                frame.append((length >> (8 * i)) & 0xFF)

        frame.extend(mask_key)
        frame.extend(masked)
        return bytes(frame)

    def _read_cdp_response(self, sock, target_id: int, timeout: int = 15) -> Optional[dict]:
        """循环读取 WebSocket 帧，跳过事件，直到找到匹配 id 的 CDP 响应"""
        sock.settimeout(timeout)

        def _recv_exact(n: int) -> bytes:
            data = b""
            while len(data) < n:
                chunk = sock.recv(n - len(data))
                if not chunk:
                    raise ValueError("连接关闭")
                data += chunk
            return data

        while True:
            header = _recv_exact(2)
            opcode = header[0] & 0x0F
            plen = header[1] & 0x7F
            if plen == 126:
                plen = int.from_bytes(_recv_exact(2), "big")
            elif plen == 127:
                plen = int.from_bytes(_recv_exact(8), "big")
            if header[1] & 0x80:
                mk = _recv_exact(4)
                pdata = _recv_exact(plen)
                pdata = bytes(b ^ mk[i % 4] for i, b in enumerate(pdata))
            else:
                pdata = _recv_exact(plen)
            if opcode == 0x01:  # 文本帧
                try:
                    msg = json.loads(pdata.decode("utf-8"))
                    if msg.get("id") == target_id:
                        return msg
                except Exception:
                    pass
            elif opcode == 0x08:  # 关闭帧
                return None

    def restore_default(self) -> dict:
        """恢复官方外观"""
        result = {
            "success": False,
            "message": ""
        }

        try:
            # 确保 CDP 可用（必要时自动重启 ChatGPT）
            if not self._ensure_cdp_available(auto_restart=True):
                # CDP 不可用，仅清除配置
                config = self._load_config()
                config["current_theme"] = None
                self._save_config(config)
                self.current_theme = None
                result["success"] = True
                result["message"] = "已清除主题配置"
                return result

            # 查找 Codex CDP 页面
            ws_url = self._find_codex_cdp_page()
            if not ws_url:
                raise ValueError("Codex 未运行或未找到调试页面")

            # 通过 Runtime.evaluate 移除注入的样式（调用注入时保存的 cleanup 函数）
            js_code = (
                "(function(){"
                "var state = window.__CODEX_DREAM_SKIN_STATE__;"
                "if (state && typeof state.cleanup === 'function') {"
                "  state.cleanup();"
                "} else {"
                "  var s = document.getElementById('codex-dream-skin-style');"
                "  if (s) s.remove();"
                "  document.documentElement.removeAttribute('data-dream-skin');"
                "  document.documentElement.removeAttribute('data-dream-shell');"
                "  document.documentElement.style.removeProperty('--ds-art-url');"
                "  document.documentElement.style.removeProperty('--dream-skin-focus-x');"
                "  document.documentElement.style.removeProperty('--dream-skin-focus-y');"
                "}"
                "})()"
            )
            self._send_cdp_commands_batch(ws_url, [
                ("Runtime.enable", {}),
                ("Page.enable", {}),
                ("Runtime.evaluate", {"expression": js_code, "returnByValue": False}),
            ])

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

            # 10. 自动应用刚创建的主题（确保 CDP 可用）
            config = self._load_config()
            config["current_theme"] = theme_id
            config["last_applied"] = self._now_iso()
            self._save_config(config)
            self.current_theme = theme_id

            if self._ensure_cdp_available(auto_restart=True):
                css_full = self._build_theme_css(theme_dir, theme_json)
                self._inject_css_to_codex(css_full, theme_json, theme_dir)
                result["message"] = "主题已创建并应用"
            else:
                result["message"] = "主题已创建，打开 Codex 后生效"

        except Exception as e:
            result["message"] = str(e)

        return result


# 全局单例
theme_manager = ThemeManager()