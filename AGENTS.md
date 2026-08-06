# AGENTS.md — Codex助手 AI 协作指南

> 本文件供 AI 编码助手（Codex / Claude / Cursor 等）阅读，描述项目架构、代码规范和开发约定。

## 项目概述

Codex助手是一个桌面应用，为 OpenAI Codex App 接入第三方大模型（DeepSeek / Kimi / 智谱 / 通义等）提供本地适配器服务。支持 macOS 和 Windows 双平台，内置激活码管理系统和 Codex 主题注入功能。

**当前版本**：v1.0.42

## 技术栈

| 层 | 技术 |
|---|---|
| 桌面应用 | Python 3.10+ / pywebview 5.x |
| 前端 | 单文件 HTML + 原生 JS + CSS |
| 适配器 | Python `http.server` + `urllib` |
| 管理后台 | Next.js 14 + TypeScript + Arco Design |
| 数据库 | SQLite（后台）/ JSON 文件（客户端） |
| 打包 | PyInstaller（macOS .app/.dmg + Windows 便携版） |

## 核心模块

### 客户端（`src/`）

| 文件 | 职责 |
|---|---|
| `core.py` | 配置管理、provider 注册表、适配器启停、Key 存储 |
| `adapter.py` | Codex Responses API → OpenAI Chat Completions 转发，含 SSL 重试和错误处理 |
| `web_api.py` | HTTP 控制 API（端口 18668），托管前端页面 |
| `web_launcher.py` | pywebview 桌面启动器，暴露 JS API |
| `theme_manager.py` | Codex 主题注入（CDP 协议），20 个内置主题 |
| `activation.py` | 激活码验证、设备绑定 |

### 管理后台（`admin/`）

| 路径 | 职责 |
|---|---|
| `app/api/` | REST API（激活码 CRUD、版本管理、日志） |
| `app/codes/` | 激活码管理页面 |
| `app/versions/` | 版本管理页面（含安装包上传） |
| `lib/db.ts` | 数据库连接（SQLite / MySQL 兼容） |
| `lib/auth.ts` | Token 认证中间件 |
| `middleware.ts` | CORS 跨域处理 |

### 前端（`web/index.html`）

单文件应用，包含：模型配置、用量统计、主题切换、设置面板、更新检测。

## 端口约定

| 端口 | 用途 |
|---|---|
| 18667 | 适配器服务（Codex 请求入口） |
| 18668 | 控制 API + 前端页面 |
| 9222 / 9341 | Codex CDP 调试端口（主题注入） |
| 3000 | 管理后台（服务器） |
| 8080 | 管理后台 API（服务器，用于版本检查） |

## 开发规范

### Python

- 使用标准库优先，不引入不必要的第三方依赖
- `urllib` 而非 `requests`（减少打包体积）
- SSL 请求必须使用 `certifi` 证书，并实现重试机制
- 日志写入 `~/.codex-helper/data/` 目录
- 配置文件使用 JSON 格式，存储在 `~/.codex-helper/data/`

### TypeScript / Next.js

- 使用 App Router（`app/` 目录）
- API 响应统一使用 `success()` / `error()` 包装
- 认证使用 Bearer Token
- 文件上传需设置 `bodySizeLimit: '200mb'`

### 前端 HTML

- 单文件架构，所有 JS/CSS 内联在 `index.html` 中
- 版本号必须同步更新两处：HTML 文本和 JS 变量
- 主题相关 CSS 变量和选择器参照 `assets/dream-skin/dream-skin-base.css`

### 版本号管理

每次发布版本时，必须同步更新以下 3 处：

1. `build_dmg.sh` 中的 `VERSION="x.x.x"`
2. `web/index.html` 中 `id="app-version"` 的显示文本
3. `web/index.html` 中 `var APP_VERSION = "x.x.x"`

版本号自动递增 patch 号（如 1.0.42 → 1.0.43）。

### 打包注意事项

- `--add-data` 必须包含所有引用的图片资源
- `assets/dream-skin/` 目录需整体打包
- DMG 创建需先建空白镜像再拷贝（沙箱限制）

## 关键约定

1. **SSL 错误重试**：`adapter.py` 的 `fetch_upstream` 遇到 UNEXPECTED_EOF 等瞬时错误时最多重试 2 次，重试时降级到 TLS 1.0+
2. **上游错误处理**：`_extract_upstream_error()` 兼容 4 种错误格式（OpenAI 标准、非标准 code+message、无 choices、finish_reason 异常）
3. **主题注入**：使用 CDP `Runtime.evaluate` 方法（不是 `Page.addStyleSheetToDocument`）
4. **CDP WebSocket**：帧必须带掩码，不发送 Origin 头
5. **背景图注入**：使用 base64 → Blob URL 方式（不用 file://，避免 CSP 拦截）
6. **主题持久化**：watcher 后台线程监控 CDP 端口，Codex 启动后自动注入，含重试机制（3s → 5s → 8s → 12s）

## 数据存储

| 文件 | 内容 |
|---|---|
| `~/.codex-helper/data/codex-helper-config.json` | 适配器当前配置 |
| `~/.codex-helper/data/switcher-keys.json` | API Key 存储 |
| `~/.codex-helper/data/switcher-custom-providers.json` | 自定义 provider |
| `~/.codex-helper/data/token-usage.json` | Token 用量统计 |
| `~/.codex-helper/theme_config.json` | 主题配置 |
| `~/.codex-helper/activation.json` | 激活码缓存 |
| `~/.codex/config.toml` | Codex 主配置 |
| `~/.codex/config.toml.openai-backup` | 切换前备份 |

## 常见任务

### 添加新模型提供商

在 `src/core.py` 的 `PROVIDERS` 字典中添加一行：

```python
"newprovider": {
    "label": "NewProvider",
    "upstream": "https://api.newprovider.com/chat/completions",
    "models": ["model-v1", "model-v2"],
    "docs": "https://docs.newprovider.com",
},
```

### 添加新内置主题

1. 在 `assets/dream-skin/builtin-themes/` 下创建主题目录
2. 包含 `theme.json`（主题配置）、`background.jpg`（背景图）、`theme.css`（可选覆盖样式）
3. 主题会自动被 `theme_manager.py` 扫描加载

### 修改管理后台

1. 编辑 `admin/app/` 下的对应文件
2. 本地运行 `cd admin && npm run dev` 开发
3. 部署使用 `update_admin.sh` 脚本

## 测试

```bash
# 运行沙箱测试
python src/tests/test_core.py
```

## 部署

### 客户端打包

```bash
bash build_dmg.sh          # macOS DMG
bash build_windows_portable.sh  # Windows 便携版
```

### 管理后台部署

```bash
bash deploy.sh             # 首次部署
bash update_admin.sh       # 更新代码
bash update_upload.sh      # 修复上传限制
```
