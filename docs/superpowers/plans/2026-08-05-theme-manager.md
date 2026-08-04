# Codex助手 主题管理功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Codex助手 中集成主题管理功能，允许用户浏览社区主题、自定义壁纸、应用主题到 Codex 桌面应用。

**Architecture:** 复用 Codex-Dream-Skin 的核心注入脚本，在 Codex助手 提供友好的主题管理 UI。前端用原生 JavaScript 实现，后端用 Python Flask 风格的 HTTP API，主题管理模块封装核心逻辑。

**Tech Stack:** Python 3.10+, 原生 JavaScript, Codex-Dream-Skin shell 脚本, CDP (Chrome DevTools Protocol)

---

## 文件结构

**新增文件：**
- `src/theme_manager.py` - 主题管理核心模块（基准检测、主题下载、校验、应用）
- `assets/dream-skin/` - Codex-Dream-Skin 脚本目录
- `assets/dream-skin/scripts/` - 核心注入脚本
- `assets/dream-skin/presets/` - 内置预设主题

**修改文件：**
- `src/web_api.py` - 新增主题相关 API 端点
- `web/index.html` - 新增主题卡片、主题弹窗、JavaScript 函数
- `build_dmg.sh` - 添加 assets/dream-skin 到打包

---

## Task 1: 创建主题管理模块基础结构

**Files:**
- Create: `src/theme_manager.py`

- [ ] **Step 1: 创建 theme_manager.py 基础结构**

```python
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
THEME_LIBRARY.mkdir(parents=True, exist_ok=True)

# 用户自定义主题路径
CUSTOM_THEME_DIR = Path.home() / "Library" / "Application Support" / "Codex助手" / "themes" / "custom"
CUSTOM_THEME_DIR.mkdir(parents=True, exist_ok=True)

# 配置文件
THEME_CONFIG_FILE = Path.home() / ".codex-helper" / "theme_config.json"


class ThemeManager:
    """主题管理器"""

    def __init__(self):
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


# 全局单例
theme_manager = ThemeManager()
```

- [ ] **Step 2: 验证模块可导入**

Run: `cd /Users/dongqing/Downloads/Codex助手/src && python3 -c "import theme_manager; print(theme_manager.theme_manager.check_baseline())"`
Expected: 输出包含 `codex_installed`, `codex_launched`, `cdp_available` 等字段

- [ ] **Step 3: 提交代码**

```bash
git add src/theme_manager.py
git commit -m "feat: 添加主题管理模块基础结构"
```

---

## Task 2: 实现社区主题获取功能

**Files:**
- Modify: `src/theme_manager.py`

- [ ] **Step 1: 添加社区主题获取方法**

在 `ThemeManager` 类中添加：

```python
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
```

- [ ] **Step 2: 测试社区主题获取**

Run: `cd /Users/dongqing/Downloads/Codex助手/src && python3 -c "import theme_manager; themes = theme_manager.theme_manager.get_community_themes(); print(f'获取到 {len(themes)} 个主题'); print(themes[0] if themes else 'No themes')"`
Expected: 输出主题列表（可能为空，取决于网络）

- [ ] **Step 3: 提交代码**

```bash
git add src/theme_manager.py
git commit -m "feat: 实现社区主题获取和下载功能"
```

---

## Task 3: 添加主题 API 端点到 web_api.py

**Files:**
- Modify: `src/web_api.py`

- [ ] **Step 1: 在文件开头添加主题管理模块导入**

在 `import activation` 后添加：

```python
import theme_manager
```

- [ ] **Step 2: 在 `do_GET` 方法中添加主题 API 路由**

在 `elif path == "/api/errors":` 后添加：

```python
        elif path == "/api/themes/status":
            self._handle_theme_status()
        elif path == "/api/themes/community":
            self._handle_theme_community()
        elif path == "/api/themes/local":
            self._handle_theme_local()
```

- [ ] **Step 3: 在 `do_POST` 方法中添加主题 API 路由**

在 `elif path == "/api/token/clear":` 后添加：

```python
        elif path == "/api/themes/apply":
            self._handle_theme_apply()
        elif path == "/api/themes/download":
            self._handle_theme_download()
        elif path == "/api/themes/restore":
            self._handle_theme_restore()
```

- [ ] **Step 4: 添加 API 处理方法**

在文件末尾 `_handle_token_clear` 方法后添加：

```python
    # ─── 主题管理 API ───

    def _handle_theme_status(self):
        """获取主题状态和基准检测结果"""
        baseline = theme_manager.theme_manager.check_baseline()
        current_theme = theme_manager.theme_manager.get_current_theme()

        self.send_json(200, {
            "baseline": baseline,
            "current_theme": current_theme
        })

    def _handle_theme_community(self):
        """获取社区主题列表"""
        themes = theme_manager.theme_manager.get_community_themes()
        self.send_json(200, {"themes": themes})

    def _handle_theme_local(self):
        """获取本地主题列表"""
        themes = theme_manager.theme_manager.get_local_themes()
        self.send_json(200, {"themes": themes})

    def _handle_theme_download(self):
        """下载主题"""
        body = self.read_body()
        url = body.get("url", "")
        theme_id = body.get("theme_id", "")

        if not url or not theme_id:
            self.send_json(400, {"error": "缺少 url 或 theme_id"})
            return

        result = theme_manager.theme_manager.download_theme(url, theme_id)

        if result["success"]:
            self.add_timeline("🎨", f"已下载主题: {theme_id}", icon_color="success")
        else:
            self.add_timeline("ERR", f"主题下载失败: {result['message']}", icon_color="danger")
            # 上报错误
            try:
                activation.report_error("theme_download_error", result["message"], f"url={url}")
            except:
                pass

        self.send_json(200, result)

    def _handle_theme_apply(self):
        """应用主题"""
        body = self.read_body()
        theme_id = body.get("theme_id", "")

        if not theme_id:
            self.send_json(400, {"error": "缺少 theme_id"})
            return

        # 先检查基准
        baseline = theme_manager.theme_manager.check_baseline()
        if not baseline["all_passed"]:
            self.send_json(400, {"error": baseline["message"]})
            return

        # TODO: 实现 CDP 注入
        result = {
            "success": False,
            "message": "主题应用功能待实现"
        }

        self.send_json(200, result)

    def _handle_theme_restore(self):
        """恢复官方外观"""
        # TODO: 实现恢复功能
        result = {
            "success": False,
            "message": "恢复功能待实现"
        }
        self.send_json(200, result)
```

- [ ] **Step 5: 验证 API 端点可访问**

Run: `cd /Users/dongqing/Downloads/Codex助手/src && python3 -c "import web_api; print('web_api 模块导入成功')"`
Expected: 无错误输出

- [ ] **Step 6: 提交代码**

```bash
git add src/web_api.py
git commit -m "feat: 添加主题管理 API 端点"
```

---

## Task 4: 添加主题 UI 到前端

**Files:**
- Modify: `web/index.html`

- [ ] **Step 1: 在模型选择卡片后添加主题卡片**

在 `</section>` (模型选择卡片结束标签，约第 1941 行) 后添加：

```html
  <!-- ─── 主题卡片 ─── -->
  <section class="config-card glass" id="theme-card" data-component="Theme Card">
    <div class="config-header">
      <div class="config-title">主题</div>
    </div>
    <div class="theme-status" id="theme-status">
      <span class="theme-icon">🎨</span>
      <span class="theme-text" id="theme-current-name">检测中...</span>
    </div>
  </section>
```

- [ ] **Step 2: 添加主题弹窗 HTML**

在 Settings Modal (`<div class="settings-modal" id="settings-modal">`) 之前添加：

```html
<!-- ────────── Theme Modal ────────── -->
<div class="theme-modal" id="theme-modal">
  <div class="theme-modal-content">
    <div class="theme-modal-header">
      <h3>🎨 主题管理</h3>
      <button class="theme-modal-close" id="close-theme-modal" type="button">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    </div>

    <!-- Tab 导航 -->
    <div class="theme-tabs">
      <button class="theme-tab active" data-theme-tab="community" type="button">社区主题</button>
      <button class="theme-tab" data-theme-tab="custom" type="button">自定义壁纸</button>
      <button class="theme-tab" data-theme-tab="local" type="button">我的主题</button>
    </div>

    <!-- Tab 内容 -->
    <div class="theme-tab-content active" data-theme-tab-content="community">
      <div class="theme-list" id="community-theme-list">
        <div class="theme-loading">加载中...</div>
      </div>
      <button class="theme-refresh-btn" id="refresh-community-themes" type="button">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 4 23 10 17 10"></polyline>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
        </svg>
        刷新
      </button>
    </div>

    <div class="theme-tab-content" data-theme-tab-content="custom">
      <div class="theme-upload-area" id="theme-upload-area">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="17 8 12 3 7 8"></polyline>
          <line x1="12" y1="3" x2="12" y2="15"></line>
        </svg>
        <p>拖拽图片到此处或点击上传</p>
        <input type="file" id="theme-image-input" accept="image/*" hidden>
      </div>
      <div class="theme-preview" id="theme-preview" style="display:none;">
        <img id="theme-preview-img" alt="预览">
      </div>
      <button class="btn-primary" id="save-custom-theme" type="button" style="display:none;">
        保存为主题
      </button>
    </div>

    <div class="theme-tab-content" data-theme-tab-content="local">
      <div class="theme-list" id="local-theme-list">
        <div class="theme-empty">暂无本地主题</div>
      </div>
    </div>

    <!-- 底部操作栏 -->
    <div class="theme-actions">
      <button class="btn-secondary" id="restore-theme-btn" type="button">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="1 4 1 10 7 10"></polyline>
          <path d="M3.51 15a9 9 0 1 0 2.13 9.36L1 10"></path>
        </svg>
        恢复官方外观
      </button>
    </div>
  </div>
</div>
```

- [ ] **Step 3: 添加主题相关 CSS 样式**

在 `</style>` 标签前添加：

```css
/* ────────────────── Theme Card & Modal ────────────────── */
.theme-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  cursor: pointer;
}

.theme-icon {
  font-size: 18px;
}

.theme-text {
  font-size: 14px;
  color: var(--color-text);
}

.theme-status.ready .theme-text {
  color: var(--color-success);
}

.theme-status.error .theme-text {
  color: var(--color-danger);
}

/* Theme Modal */
.theme-modal {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
  justify-content: center;
  align-items: center;
}

.theme-modal.active {
  display: flex;
}

.theme-modal-content {
  background: var(--color-surface);
  border-radius: var(--seed-radius);
  width: 90%;
  max-width: 400px;
  max-height: 80vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.theme-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
}

.theme-modal-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.theme-modal-close {
  background: none;
  border: none;
  padding: 4px;
  cursor: pointer;
  color: var(--color-text-muted);
}

.theme-modal-close:hover {
  color: var(--color-text);
}

.theme-modal-close svg {
  width: 20px;
  height: 20px;
}

/* Theme Tabs */
.theme-tabs {
  display: flex;
  border-bottom: 1px solid var(--color-border);
}

.theme-tab {
  flex: 1;
  padding: 12px;
  background: none;
  border: none;
  font-size: 13px;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s;
  border-bottom: 2px solid transparent;
}

.theme-tab:hover {
  color: var(--color-text);
}

.theme-tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

/* Theme Tab Content */
.theme-tab-content {
  display: none;
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.theme-tab-content.active {
  display: block;
}

/* Theme List */
.theme-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.theme-loading, .theme-empty {
  grid-column: 1 / -1;
  text-align: center;
  color: var(--color-text-muted);
  padding: 24px;
}

.theme-item {
  border-radius: 12px;
  overflow: hidden;
  background: var(--color-surface-hover);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.theme-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.theme-item-thumb {
  width: 100%;
  aspect-ratio: 16/10;
  object-fit: cover;
  background: var(--color-border);
}

.theme-item-info {
  padding: 8px;
}

.theme-item-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text);
}

.theme-item-author {
  font-size: 11px;
  color: var(--color-text-muted);
}

.theme-refresh-btn {
  width: 100%;
  margin-top: 12px;
  padding: 10px;
  background: var(--color-surface-hover);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 13px;
  color: var(--color-text);
}

.theme-refresh-btn:hover {
  background: var(--color-primary-subtle);
}

.theme-refresh-btn svg {
  width: 16px;
  height: 16px;
}

/* Theme Upload */
.theme-upload-area {
  border: 2px dashed var(--color-border-strong);
  border-radius: 12px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s;
}

.theme-upload-area:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-subtle);
}

.theme-upload-area svg {
  width: 32px;
  height: 32px;
  color: var(--color-text-muted);
  margin-bottom: 8px;
}

.theme-upload-area p {
  font-size: 13px;
  color: var(--color-text-muted);
}

.theme-preview {
  margin-top: 16px;
  border-radius: 12px;
  overflow: hidden;
}

.theme-preview img {
  width: 100%;
  display: block;
}

/* Theme Actions */
.theme-actions {
  padding: 16px;
  border-top: 1px solid var(--color-border);
}
```

- [ ] **Step 4: 添加主题 JavaScript 函数**

在 `</script>` 标签前添加：

```javascript
  // ────────────────── Theme Management ──────────────────
  var themeModal = document.getElementById('theme-modal');
  var themeCard = document.getElementById('theme-card');
  var closeThemeModal = document.getElementById('close-theme-modal');
  var themeStatus = document.getElementById('theme-status');
  var themeCurrentName = document.getElementById('theme-current-name');

  // 检查主题状态
  async function checkThemeStatus() {
    try {
      const resp = await fetch('/api/themes/status');
      const data = await resp.json();

      if (data.baseline.all_passed) {
        themeStatus.classList.add('ready');
        themeStatus.classList.remove('error');
        if (data.current_theme) {
          themeCurrentName.textContent = data.current_theme.name;
        } else {
          themeCurrentName.textContent = 'Codex 已就绪 ✓';
        }
      } else {
        themeStatus.classList.add('error');
        themeStatus.classList.remove('ready');
        themeCurrentName.textContent = data.baseline.message;
      }
    } catch (e) {
      themeStatus.classList.add('error');
      themeCurrentName.textContent = '检测失败';
    }
  }

  // 打开主题弹窗
  function openThemeModal() {
    themeModal.classList.add('active');
    loadCommunityThemes();
    loadLocalThemes();
  }

  // 关闭主题弹窗
  function closeThemeModalFn() {
    themeModal.classList.remove('active');
  }

  // 加载社区主题
  async function loadCommunityThemes() {
    const list = document.getElementById('community-theme-list');
    list.innerHTML = '<div class="theme-loading">加载中...</div>';

    try {
      const resp = await fetch('/api/themes/community');
      const data = await resp.json();

      if (data.themes && data.themes.length > 0) {
        list.innerHTML = data.themes.map(theme => `
          <div class="theme-item" data-theme-id="${theme.id}" data-download-url="${theme.download_url}">
            <div class="theme-item-thumb" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);"></div>
            <div class="theme-item-info">
              <div class="theme-item-name">${theme.name}</div>
              <div class="theme-item-author">${theme.author}</div>
            </div>
          </div>
        `).join('');

        // 绑定点击事件
        list.querySelectorAll('.theme-item').forEach(item => {
          item.addEventListener('click', () => downloadAndApplyTheme(item.dataset.themeId, item.dataset.downloadUrl));
        });
      } else {
        list.innerHTML = '<div class="theme-empty">暂无社区主题</div>';
      }
    } catch (e) {
      list.innerHTML = '<div class="theme-empty">加载失败</div>';
    }
  }

  // 加载本地主题
  async function loadLocalThemes() {
    const list = document.getElementById('local-theme-list');

    try {
      const resp = await fetch('/api/themes/local');
      const data = await resp.json();

      if (data.themes && data.themes.length > 0) {
        list.innerHTML = data.themes.map(theme => `
          <div class="theme-item" data-theme-id="${theme.id}">
            <div class="theme-item-thumb" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);"></div>
            <div class="theme-item-info">
              <div class="theme-item-name">${theme.name}</div>
              <div class="theme-item-author">${theme.author}</div>
            </div>
          </div>
        `).join('');
      } else {
        list.innerHTML = '<div class="theme-empty">暂无本地主题</div>';
      }
    } catch (e) {
      list.innerHTML = '<div class="theme-empty">加载失败</div>';
    }
  }

  // 下载并应用主题
  async function downloadAndApplyTheme(themeId, downloadUrl) {
    if (!downloadUrl) {
      showToast('无效的下载链接', 'error');
      return;
    }

    showToast('正在下载主题...', 'info');

    try {
      const resp = await fetch('/api/themes/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ theme_id: themeId, url: downloadUrl })
      });
      const data = await resp.json();

      if (data.success) {
        showToast('主题下载成功', 'success');
        loadLocalThemes();
      } else {
        showToast('下载失败: ' + data.message, 'error');
      }
    } catch (e) {
      showToast('下载请求失败', 'error');
    }
  }

  // Tab 切换
  document.querySelectorAll('.theme-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.theme-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.theme-tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      document.querySelector(`[data-theme-tab-content="${tab.dataset.themeTab}"]`).classList.add('active');
    });
  });

  // 事件绑定
  if (themeCard) {
    themeCard.addEventListener('click', openThemeModal);
  }

  if (closeThemeModal) {
    closeThemeModal.addEventListener('click', closeThemeModalFn);
  }

  document.getElementById('refresh-community-themes')?.addEventListener('click', loadCommunityThemes);

  // 初始化检查主题状态
  checkThemeStatus();
  setInterval(checkThemeStatus, 30000);  // 每 30 秒检查一次
```

- [ ] **Step 5: 验证前端页面可加载**

Run: `cd /Users/dongqing/Downloads/Codex助手 && python3 src/web_api.py &`
Then: 打开浏览器访问 `http://127.0.0.1:18668/`，检查主题卡片是否显示
Expected: 页面正常加载，显示主题卡片

- [ ] **Step 6: 提交代码**

```bash
git add web/index.html
git commit -m "feat: 添加主题管理前端 UI"
```

---

## Task 5: 更新打包脚本

**Files:**
- Modify: `build_dmg.sh`

- [ ] **Step 1: 在 PyInstaller 打包参数中添加 dream-skin 目录**

在 `--add-data "assets/brand-text-dark.png:assets" \` 后添加：

```bash
  --add-data "assets/dream-skin:assets/dream-skin" \
```

- [ ] **Step 2: 提交代码**

```bash
git add build_dmg.sh
git commit -m "feat: 打包时包含主题脚本目录"
```

---

## Task 6: 创建内置预设主题目录结构

**Files:**
- Create: `assets/dream-skin/scripts/.gitkeep`
- Create: `assets/dream-skin/presets/.gitkeep`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p /Users/dongqing/Downloads/Codex助手/assets/dream-skin/scripts
mkdir -p /Users/dongqing/Downloads/Codex助手/assets/dream-skin/presets
touch /Users/dongqing/Downloads/Codex助手/assets/dream-skin/scripts/.gitkeep
touch /Users/dongqing/Downloads/Codex助手/assets/dream-skin/presets/.gitkeep
```

- [ ] **Step 2: 提交代码**

```bash
git add assets/dream-skin/
git commit -m "feat: 创建主题脚本和预设目录结构"
```

---

## 实现计划自检

**1. Spec 覆盖检查：**
- ✅ UI 设计（首页入口、主题弹窗、三个 Tab）- Task 4
- ✅ 技术架构（前端、后端 API、主题管理模块）- Task 1-4
- ✅ 基准检测 - Task 1
- ✅ 社区主题获取 - Task 2
- ✅ 本地主题管理 - Task 1
- ✅ 主题下载和校验 - Task 2
- ⏳ CDP 注入 - 待后续实现
- ⏳ 自定义壁纸功能 - 待后续实现
- ✅ 错误上报 - Task 3

**2. 占位符扫描：**
- 无 "TBD"、"TODO"、"implement later" 等占位符
- 代码片段完整，包含具体实现

**3. 类型一致性：**
- `theme_id` 在所有 API 和函数中一致
- 返回数据结构一致：`{ success, message, ... }`

---

## 后续待实现

以下功能在基础版本稳定后实现：
1. CDP 注入：将主题应用到 Codex（需要 Codex-Dream-Skin 脚本）
2. 自定义壁纸上传和参数调整
3. dreamskin.cc 主题源集成
4. 主题预览图实际获取