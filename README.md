# Codex助手

> 给 OpenAI **Codex App** 接入 APINest 或任意 OpenAI 兼容大模型的纯本地桌面助手。**无需账号、无需激活，开箱即用。** 支持 macOS / Windows，内置 Codex 主题皮肤。

![status](https://img.shields.io/badge/status-beta-orange)
![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![version](https://img.shields.io/badge/version-1.0.75-blue)

## 特性

- **纯本地运行**：无需账号、无需激活、无需设备绑定，不依赖授权服务器
- **一键切换**：选择模型、填写 API Key 后即可启动本地适配器
- **一键回滚**：随时切回 OpenAI 原版，自动保留配置备份
- **新增服务商**：新增模型仅提供 `APINest` 和 `自定义` 两个选项；历史 provider 配置继续兼容
- **本地存储**：API Key、模型配置、统计和主题配置保存在本机
- **用量统计**：实时统计输入、输出、缓存 Token，并支持调用历史
- **错误处理**：记录本地错误日志，兼容多种上游错误格式
- **主题皮肤**：20 个内置 Codex 主题，支持 CDP 注入、持久化和自定义壁纸
- **双平台支持**：macOS 原生 `.app/.dmg` 与 Windows 便携版
- **发布包更新**：客户端不执行远程版本检查，更新从项目发布页获取新安装包

## 支持的模型

内置配置保留 DeepSeek、Kimi、智谱、通义、小米 MiMo、StepFun、LongCat、Claude、Gemini、APINest 等历史 provider，便于升级兼容。

新增模型时请选择：

- `APINest`：使用 APINest 预设地址和模型列表
- `自定义`：填写任意 OpenAI Chat Completions 兼容的 Base URL、模型名称和 API Key

## 用法

1. 下载对应平台的安装包并启动
2. 安装后直接使用，无需输入激活码或登录账号
3. 打开「模型配置」，选择 `APINest` 或 `自定义`
4. 填写模型、Base URL 和 API Key，保存配置
5. 回到首页启动本地服务，然后打开 Codex App
6. 不使用第三方模型时，停止服务即可恢复官方 OpenAI 配置

历史第三方会话在适配器关闭后可能仍指向本地端口。重新打开 Codex助手时，内置 gatekeeper 会自动尝试将历史会话迁移到官方 OpenAI，按提示关闭并重新打开对应会话即可继续使用。

## 适配器工作原理

```text
Codex App --[Responses API]--> 127.0.0.1:18667 本地适配器 --[Chat Completions]--> 上游模型 API
                                  │
                                  └── 127.0.0.1:18668 本地控制 API + Web UI
```

- 接收 Codex Responses API 请求并转换为 OpenAI Chat Completions 格式
- 支持流式输出、非流式输出和函数调用
- API Key 仅用于本地转发配置，不经过第三方授权服务
- 支持 SSL 自动重试和多格式上游错误解析
- 适配器只监听 `127.0.0.1`，不对外网开放

## 主题皮肤

Codex助手内置 20 个主题，支持一键切换、Codex 重启后自动恢复、自定义壁纸和玻璃风界面。主题注入依赖 Codex 的 CDP 调试端口。

## 自己运行和打包

```bash
git clone https://github.com/Dylan-Du/CodeWise.git
cd CodeWise
pip install -r requirements.txt

# 启动 Web 版
python src/web_launcher.py

# 或启动 GUI 版
python src/gui_ctk.py

# macOS
bash build_app.sh
bash build_dmg.sh

# Windows 便携版
bash build_windows_portable.sh
```

源码运行需要 Python 3.10+；发布包自带运行时。构建产物位于 `dist/`，发布前请从项目发布页上传并分发安装包。

## 项目结构

```text
codex-assistant/
├─ src/
│  ├─ adapter.py            # Responses API ↔ Chat Completions 适配器
│  ├─ core.py               # 配置、provider、Key 存储、启停和回滚
│  ├─ web_api.py            # 本地控制 API 和页面托管
│  ├─ web_launcher.py       # pywebview 桌面启动器
│  ├─ theme_manager.py      # Codex 主题注入
│  ├─ macos_permissions.py  # macOS 权限管理
│  └─ tests/                # 测试
├─ web/index.html           # 单文件 Web UI
├─ assets/dream-skin/       # 主题系统
├─ build_app.sh             # macOS App 打包
├─ build_dmg.sh             # macOS DMG 打包
├─ build_windows_portable.sh# Windows 便携版打包
├─ requirements.txt
├─ AGENTS.md
├─ LICENSE
└─ README.md
```

## 数据存储

| 文件 | 内容 |
|---|---|
| `~/.codex-helper/data/codex-helper-config.json` | 当前适配器配置 |
| `~/.codex-helper/data/switcher-keys.json` | API Key |
| `~/.codex-helper/data/switcher-custom-providers.json` | 自定义模型条目 |
| `~/.codex-helper/data/token-usage.json` | Token 用量统计 |
| `~/.codex-helper/theme_config.json` | 主题配置 |
| `~/.codex/config.toml` | Codex 主配置 |
| `~/.codex/config.toml.openai-backup` | 切换前的官方配置备份 |

旧版本留下的本地授权文件不会被新版本读取，也不会影响启动；客户端不会主动删除用户历史数据。

## 测试

```bash
python3 -m py_compile src/*.py
python3 src/tests/test_core.py
```

## 已知限制

- 自定义 provider 需要兼容 OpenAI Chat Completions 协议
- 同一时刻只能挂载一家上游模型服务
- 主题注入需要 Codex 以 CDP 调试模式启动
- 客户端更新通过发布包完成，不在应用内访问版本服务器

## License

[MIT](LICENSE) © 2026 Codex助手
