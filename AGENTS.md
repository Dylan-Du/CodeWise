# AGENTS.md — Codex助手 AI 协作指南

> 本文件供 AI 编码助手阅读，描述项目架构、代码规范和开发约定。

## 项目概述

Codex助手是一个纯本地桌面应用，为 OpenAI Codex App 接入 APINest 和其他 OpenAI 兼容大模型。支持 macOS 和 Windows，内置 Codex 主题注入和深色玻璃风 Web UI。客户端无需账号、激活码、设备绑定或远程授权服务。

**当前版本**：v1.0.75

## 技术栈

| 层 | 技术 |
|---|---|
| 桌面应用 | Python 3.10+ / pywebview 5.x |
| 前端 | 单文件 HTML + 原生 JS + CSS |
| 适配器 | Python `http.server` + `urllib` |
| 数据存储 | 本地 JSON 文件 |
| 打包 | PyInstaller（macOS `.app/.dmg` + Windows 便携版） |

## 核心模块

### 客户端（`src/`）

| 文件 | 职责 |
|---|---|
| `core.py` | 配置管理、provider 注册表、适配器启停、Key 存储、官方配置回滚 |
| `adapter.py` | Codex Responses API → OpenAI Chat Completions 转发，含 SSL 重试和错误处理 |
| `web_api.py` | 本地 HTTP 控制 API（端口 18668），托管前端页面 |
| `web_launcher.py` | pywebview 桌面启动器 |
| `theme_manager.py` | Codex 主题注入（CDP 协议），内置主题和自定义壁纸 |

### 前端（`web/index.html`）

单文件应用，包含模型配置、用量统计、主题切换、设置面板、状态管理和玻璃风视觉样式。客户端更新通过发布包完成，页面不请求远程版本服务。

## 端口约定

| 端口 | 用途 |
|---|---|
| 18667 | 本地适配器服务（Codex 请求入口） |
| 18668 | 本地控制 API + 前端页面 |
| 9222 / 9341 | Codex CDP 调试端口（主题注入） |

## 开发规范

### Python

- 使用标准库优先，不引入不必要的第三方依赖
- 使用 `urllib` 而非 `requests`，减少打包体积
- SSL 请求使用 `certifi` 证书并实现重试机制
- 日志写入 `~/.codex-helper/data/`
- 配置文件使用 JSON，保存在 `~/.codex-helper/data/`
- 不新增远程授权、错误上报或版本检查依赖

### 前端 HTML

- 单文件架构，所有 JS/CSS 内联在 `web/index.html`
- 新增模型服务商只能是 `APINest` 或 `自定义`
- 历史 provider 配置可读取和编辑，不得破坏兼容性
- 版本号同步更新 HTML 文本和 `APP_VERSION` 变量
- 主题相关 CSS 变量和选择器参照 `assets/dream-skin/dream-skin-base.css`

### 版本号管理

每次发布版本时同步更新：

1. `build_dmg.sh` 中的 `VERSION="x.x.x"`
2. `web/index.html` 中 `id="app-version"` 的显示文本
3. `web/index.html` 中 `var APP_VERSION = "x.x.x"`

版本号按 patch 号递增，例如 `1.0.75` → `1.0.76`。

### 打包注意事项

- `--add-data` 必须包含所有引用的图片资源
- `assets/dream-skin/` 目录需整体打包
- DMG 创建需先建空白镜像再拷贝
- 发布包中不得包含服务端后台、激活模块或数据库

## 关键约定

1. **SSL 错误重试**：`adapter.py` 的 `fetch_upstream` 遇到 `UNEXPECTED_EOF` 等瞬时错误时最多重试 2 次
2. **上游错误处理**：`_extract_upstream_error()` 兼容 OpenAI 标准、非标准 `code + message`、无 choices 和异常 `finish_reason`
3. **主题注入**：使用 CDP `Runtime.evaluate` 方法
4. **CDP WebSocket**：帧必须带掩码，不发送 Origin 头
5. **背景图注入**：使用 base64 → Blob URL，避免 CSP 拦截
6. **主题持久化**：后台 watcher 监控 CDP 端口，Codex 启动后自动注入并重试
7. **历史会话迁移**：gatekeeper 可将仍指向旧本地适配器的历史第三方会话迁移到官方 OpenAI

## 数据存储

| 文件 | 内容 |
|---|---|
| `~/.codex-helper/data/codex-helper-config.json` | 当前适配器配置 |
| `~/.codex-helper/data/switcher-keys.json` | API Key |
| `~/.codex-helper/data/switcher-custom-providers.json` | 自定义 provider |
| `~/.codex-helper/data/token-usage.json` | Token 用量统计 |
| `~/.codex-helper/theme_config.json` | 主题配置 |
| `~/.codex/config.toml` | Codex 主配置 |
| `~/.codex/config.toml.openai-backup` | 切换前备份 |

旧版本留下的本地授权文件不会被读取，也不会影响新版本启动；客户端不主动删除用户历史数据。

## 常见任务

### 添加新内置主题

1. 在 `assets/dream-skin/builtin-themes/` 创建主题目录
2. 包含 `theme.json`、`background.jpg` 和可选的 `theme.css`
3. 主题会被 `theme_manager.py` 自动扫描

## 测试

```bash
python3 -m py_compile src/*.py
python3 src/tests/test_core.py
```

## 打包

```bash
bash build_app.sh
bash build_dmg.sh
bash build_windows_portable.sh
```
