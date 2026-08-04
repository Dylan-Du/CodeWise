# Codex助手 主题管理功能设计文档

## 1. 功能概述

在 Codex助手 首页（模型选择卡片下方）添加"主题"入口，用户可以通过该功能管理官方 Codex 桌面应用的主题。

**核心能力**：
- 浏览并应用社区主题（从 GitHub Releases + dreamskin.cc 获取）
- 上传自定义图片生成主题
- 调整主题参数（焦点、安全区域、配色等）
- 一键应用/恢复官方外观

**技术方案**：复用 Codex-Dream-Skin 的核心注入脚本，在 Codex助手 UI 中提供友好的主题管理界面。

---

## 2. UI 设计

### 2.1 首页入口

**位置**：模型选择卡片下方

**布局**：
```
┌─────────────────────────────┐
│  [模型选择卡片]              │
│  当前：GPT-4o ▼             │
├─────────────────────────────┤
│  [主题卡片]                  │
│  🎨 当前主题：Gothic Void    │
│  Codex 已就绪 ✓             │
└─────────────────────────────┘
```

**状态显示**：
- 基准检测通过：显示"✓ Codex 已就绪"，可点击进入
- 基准检测失败：显示具体问题，点击显示解决步骤

### 2.2 主题弹窗

**尺寸**：与现有弹窗风格一致，宽度约 360px

**结构**：Tab 切换式

**Tab 1：社区主题**
- 主题列表（缩略图 + 名称 + 作者）
- 搜索框、筛选（按风格/颜色）
- 点击主题卡片预览，再次点击应用
- 底部：刷新按钮

**Tab 2：自定义壁纸**
- 图片上传区域（拖拽或点击选择）
- 图片预览区（显示焦点、安全区域标记）
- 参数调整面板：
  - 焦点位置（X/Y 滑块或拖拽）
  - 安全区域（下拉：自动/左/右/居中/无）
  - 任务模式（下拉：自动/氛围/横幅/全幅/关闭）
  - 配色（颜色选择器，支持自动提取）
- 底部：保存为主题按钮

**Tab 3：我的主题**
- 已保存主题列表（缩略图 + 名称 + 创建时间）
- 每个主题卡片：应用/删除/编辑按钮
- 当前应用的主题有高亮标记

### 2.3 主题应用状态

- 应用中：显示进度条和"正在应用主题..."
- 应用成功：Toast 提示"主题已应用"
- 应用失败：Toast 提示错误信息，按钮变为"重试"

---

## 3. 技术架构

### 3.1 前端 (`web/index.html`)

**新增组件**：
- 主题卡片（首页入口）
- 主题弹窗组件
- 主题列表渲染
- 图片上传组件
- 参数调整面板
- 颜色选择器

**新增 JavaScript 函数**：
- `openThemeModal()` - 打开主题弹窗
- `loadCommunityThemes()` - 加载社区主题列表
- `loadLocalThemes()` - 加载本地主题列表
- `applyTheme(themeId)` - 应用主题
- `uploadCustomImage(file)` - 上传自定义图片
- `customizeTheme(params)` - 自定义主题参数
- `restoreTheme()` - 恢复官方外观
- `checkThemeBaseline()` - 检查基准条件

### 3.2 后端 API (`src/web_api.py`)

**新增端点**：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/themes/status` | GET | 获取主题状态和基准检测结果 |
| `/api/themes/community` | GET | 获取社区主题列表 |
| `/api/themes/local` | GET | 获取本地已保存主题列表 |
| `/api/themes/apply` | POST | 应用指定主题 |
| `/api/themes/customize` | POST | 自定义主题并保存 |
| `/api/themes/upload` | POST | 上传自定义图片 |
| `/api/themes/restore` | POST | 恢复官方外观 |
| `/api/themes/delete` | POST | 删除本地主题 |

### 3.3 主题管理模块 (`src/theme_manager.py`)

**核心类**：`ThemeManager`

**主要方法**：
- `check_baseline()` - 基准检测
- `get_community_themes()` - 获取社区主题
- `get_local_themes()` - 获取本地主题列表
- `download_theme(url)` - 下载主题包
- `validate_theme(path)` - 校验主题包
- `apply_theme(theme_id)` - 应用主题
- `create_custom_theme(image_path, params)` - 创建自定义主题
- `restore_default()` - 恢复默认外观
- `inject_to_codex(theme)` - 执行 CDP 注入

### 3.4 依赖集成

**Codex-Dream-Skin 核心脚本位置**：
- 打包时内置：`assets/dream-skin/scripts/`
- 运行时解压到：`~/.codex/codex-dream-skin-studio/scripts/`

**核心脚本**：
- `switch-theme-macos.sh` - 切换主题
- `customize-theme-macos.sh` - 自定义主题
- `restore-macos.sh` - 恢复默认外观
- `load-image-theme-macos.sh` - 加载图片主题

---

## 4. 数据流

### 4.1 应用社区主题流程

```
用户点击主题卡片
        ↓
check_baseline() → 不满足？→ 显示提示，禁用功能
        ↓ 满足
打开主题弹窗 → 加载社区主题列表
        ↓
用户选择主题 → 点击应用
        ↓
download_theme() → validate_theme() → 不通过？→ 上报错误
        ↓ 通过
apply_theme() → inject_to_codex()
        ↓
成功？→ 更新 UI 状态 → Toast 提示
失败？→ 上报错误 → 显示重试按钮
```

### 4.2 自定义主题流程

```
用户上传图片 → uploadCustomImage()
        ↓
图片校验（大小、格式）→ 不通过？→ 上报错误
        ↓ 通过
显示预览 → 自动检测焦点和颜色
        ↓
用户调整参数 → customizeTheme()
        ↓
create_custom_theme() → 保存到本地主题库
        ↓
apply_theme() → inject_to_codex()
```

---

## 5. 目录结构

```
Codex助手/
├── src/
│   ├── theme_manager.py      # 主题管理模块（新增）
│   ├── web_api.py             # 新增主题相关 API 端点
│   ├── activation.py          # 现有
│   ├── core.py                # 现有
│   └── adapter.py             # 现有
├── assets/
│   ├── dream-skin/            # Codex-Dream-Skin 核心脚本（新增）
│   │   ├── scripts/
│   │   │   ├── switch-theme-macos.sh
│   │   │   ├── customize-theme-macos.sh
│   │   │   ├── restore-macos.sh
│   │   │   └── load-image-theme-macos.sh
│   │   └── presets/           # 内置预设主题
│   │       └── preset-gothic-void-crusade/
│   ├── icon-1024.png          # 现有
│   └── logo.svg               # 现有
├── web/
│   └── index.html             # 新增主题弹窗 UI
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-08-05-theme-manager-design.md  # 本文档
```

---

## 6. 本地存储

### 6.1 主题库

- macOS: `~/Library/Application Support/CodexDreamSkinStudio/themes/`
- 每个主题一个目录，包含：
  - `theme.json` - 主题元数据
  - `theme.css` - 样式文件
  - `background.jpg/png/webp` - 背景图片
  - `manifest.json` - 清单文件（可选）

### 6.2 用户上传图片

- 路径: `~/Library/Application Support/Codex助手/themes/custom/`
- 文件命名: `custom_{timestamp}_{hash}.jpg`

### 6.3 配置文件

- 路径: `~/.codex-helper/theme_config.json`
- 内容:
  ```json
  {
    "current_theme": "preset-gothic-void-crusade",
    "baseline_checked": true,
    "last_update": "2026-08-05T12:00:00"
  }
  ```

---

## 7. 基准检测

### 7.1 检测项

| 检测项 | 检查方式 | 失败提示 | 解决步骤 |
|--------|----------|----------|----------|
| Codex 已安装 | `/Applications/Codex.app` 存在 | 请先安装 Codex 桌面应用 | 从官网下载安装 |
| Codex 已启动过 | `~/.codex/config.toml` 存在 | 请先启动一次 Codex | 打开 Codex 应用 |
| CDP 可用 | 检测端口 9222 | 请启动 Codex 后重试 | 确保 Codex 正在运行 |

### 7.2 检测时机

- 首页加载时自动检测
- 用户点击主题卡片时再次检测
- 应用主题前最终检测

### 7.3 状态显示

- 全部通过：显示"✓ Codex 已就绪"，主题入口可点击
- 部分失败：显示具体问题，点击显示解决步骤弹窗
- 检测中：显示"检测中..."

---

## 8. 错误处理与日志上报

### 8.1 必须上报的错误

| 错误类型 | 错误代码 | 描述 |
|----------|----------|------|
| 主题下载失败 | `theme_download_error` | 下载社区主题包失败 |
| 主题校验失败 | `theme_validation_error` | 主题包格式或内容不符合规范 |
| CDP 连接失败 | `theme_cdp_error` | 无法连接到 Codex 的调试端口 |
| 注入脚本失败 | `theme_inject_error` | 主题注入脚本执行失败 |
| 图片处理失败 | `theme_image_error` | 图片上传、处理或转换失败 |
| 基准检测失败 | `theme_baseline_error` | Codex 未安装/未启动 |

### 8.2 上报方式

复用现有 `reportErrorToServer()` 函数：

```javascript
function reportThemeError(errorType, message, details) {
  reportErrorToServer(errorType, message, details);
}
```

### 8.3 错误展示

- Toast 提示：简要错误信息
- 弹窗详情：完整错误原因和解决建议
- 重试按钮：允许用户手动重试

---

## 9. 社区主题来源

### 9.1 GitHub Releases

**API**: `https://api.github.com/repos/Fei-Away/Codex-Dream-Skin/releases`

**解析逻辑**：
1. 获取最新 release
2. 解析 assets 中的 `.zip` 文件
3. 提取主题元数据（名称、描述、预览图）

### 9.2 dreamskin.cc

**主题库 API**:
- 列表接口：获取主题列表
- 详情接口：获取主题详情和下载链接

**数据结构**：
```json
{
  "id": "gothic-void-crusade",
  "name": "Gothic Void Crusade",
  "author": "seansong-ideogram",
  "thumbnail": "https://...",
  "download_url": "https://...",
  "tags": ["dark", "gothic", "scifi"]
}
```

### 9.3 缓存策略

- 本地缓存主题列表 24 小时
- 用户可手动刷新
- 下载的主题包本地持久化

---

## 10. 安全边界

### 10.1 网络安全

- CDP 只绑 `127.0.0.1`，不暴露到外网
- 所有网络请求使用 HTTPS

### 10.2 文件安全

- 不修改官方 Codex 安装目录与签名
- 主题包大小限制：压缩后 ≤ 32MB，解压后 ≤ 64MB
- 主题包条目限制：≤ 32 个文件

### 10.3 CSS 安全校验

- 只允许注入特定 CSS 属性
- 禁止 `url()` 指向外部资源
- 禁止 `expression()` 等 JS 执行

---

## 11. 版本兼容

### 11.1 Codex 版本适配

- 记录每个 Codex 版本对应的主题注入参数
- Codex 更新后自动检测并提示重新应用主题

### 11.2 主题格式版本

- 主题包包含 `manifest.json` 声明最低客户端版本
- 版本不兼容时提示用户更新 Codex助手

---

## 12. 后续扩展

### 12.1 可能的功能扩展

- 主题分享：用户可将自定义主题分享到社区
- 主题同步：多设备间同步主题设置
- 定时切换：根据时间自动切换主题

### 12.2 预留接口

- `/api/themes/share` - 分享主题到社区
- `/api/themes/sync` - 同步主题设置
- `/api/themes/schedule` - 设置定时切换

---

## 附录

### A. 主题包格式规范

```
theme.zip
├── manifest.json      # 必需：清单文件
├── theme.json         # 必需：主题元数据
├── theme.css          # 必需：样式文件
├── background.jpg     # 必需：背景图片
├── LICENSE.txt        # 可选：许可证
└── manifest.sig       # 预留：签名文件
```

### B. theme.json 格式

```json
{
  "id": "preset-gothic-void-crusade",
  "name": "Gothic Void Crusade",
  "author": "seansong-ideogram",
  "version": "1.0.0",
  "appearance": "auto",
  "art": {
    "focusX": 0.72,
    "focusY": 0.45,
    "safeArea": "auto",
    "taskMode": "auto"
  },
  "colors": {
    "accent": "#7cff46",
    "secondary": "#36d7e8",
    "highlight": "#642a8c"
  }
}
```

### C. 基准检测实现参考

```python
import os
import socket
from pathlib import Path

def check_baseline():
    """检查主题功能的前置条件"""
    results = {
        "codex_installed": False,
        "codex_launched": False,
        "cdp_available": False,
        "all_passed": False
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
    
    return results
```