# Codex助手

> 给 OpenAI **Codex App** 接入 DeepSeek / Kimi / 智谱 / 通义 等任意 OpenAI 兼容大模型的桌面助手。**一键切换、一键回滚。** macOS 桌面应用。

![status](https://img.shields.io/badge/status-beta-orange)
![platform](https://img.shields.io/badge/platform-macOS-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## 它解决什么

OpenAI Codex App 默认只能用官方 GPT 模型。但你可能希望：

- **省钱**：换成 DeepSeek、Kimi、智谱、通义等便宜很多倍的模型
- **国内速度**：直连国内厂商 API，不走代理
- **多家随手切**：今天用 DeepSeek，明天用 Kimi，再后天试自己加的 GLM

Codex助手 在你本机起一个适配器（Codex `Responses` API ↔ OpenAI `chat/completions`），帮你把 Codex 的请求转给你选的任何 OpenAI 兼容上游。

---

## 特性

- 🪄 **一键切换**：选模型 -> 输 Key -> 点按钮，完事
- ↩️ **一键回滚**：随时切回 OpenAI 原版，零残留
- ➕ **自定义提供商**：内置常见平台模板（智谱/通义/小米MIMO/Kimi/StepFun/LongCat/Claude/Gemini 等），选模板自动填 Base URL，只补 Key 就能用
- 🔐 **Key 分家存**：每家 Key 单独保存，互不覆盖，下次自动加载
- 🛡️ **不破坏原配置**：字段级合并 Codex `config.toml`，保留你所有原有的配置
- 💾 **自动备份**：第一次切之前自动把原 `config.toml` 备份到 `.openai-backup`
- 📊 **用量统计**：实时统计 Token 用量（输入/输出/缓存），按模型分组展示
- 🌗 **浅色/深色/专注**：三套主题，跟随你的喜好
- 📦 **原生 .app**：macOS 原生应用，双击即用

---

## 谁能用

- **OS**：macOS 12+
- **前置**：装好 OpenAI Codex App（任意版本）
- **依赖**：无（.app 自带运行时；自己跑源码需 Python 3.10+）

---

## 用法

1. 下载 `Codex助手.app`
2. 双击启动（第一次可能慢 5-10 秒，正常）
3. 在窗口里：
   - 点击「模型配置」添加你要用的模型
   - 选择服务商和模型，粘贴对应平台的 API Key
   - 保存后回到首页，点开关按钮启动服务
4. 打开 Codex App，开始用
5. 不用了：点开关按钮停止服务，自动切回 OpenAI 原版

---

## 加新模型

在「模型配置」页面点「新增模型」：

- 选择服务商模板（内置 10+ 个常见平台），自动填 Base URL
- 或者选「自定义」，全手填：显示名 / 模型 ID / Base URL / API Key

已添加的模型可以随时编辑或删除。

---

## 自己跑源码 / 自己打包

```bash
# 1. 克隆
git clone https://gitee.com/hidylan/codex-assistant.git
cd codex-assistant

# 2. 装依赖
pip install -r requirements.txt

# 3. 启动 Web 版
python src/web_launcher.py

# 或启动 GUI 版
python src/gui_ctk.py

# 4. 打包成 .app
bash build_app.sh
# 产物：dist/Codex助手.app
```

---

## 项目结构

```
codex-assistant/
├─ src/
│   ├─ adapter.py       # 适配器：Codex Responses ↔ OpenAI chat/completions
│   ├─ core.py          # 配置管理、provider 路由、Key 存储
│   ├─ web_api.py       # HTTP 控制 API 服务器
│   ├─ web_launcher.py  # pywebview 桌面启动器
│   ├─ gui_ctk.py       # CustomTkinter GUI 版
│   └─ tests/           # 沙箱测试
├─ web/
│   └─ index.html       # Web 前端界面
├─ build_app.sh         # macOS .app 打包脚本
├─ build_dmg.sh         # macOS .dmg 打包脚本
├─ requirements.txt
├─ LICENSE              # MIT
└─ README.md
```

---

## 数据存哪

| 文件 | 内容 |
|---|---|
| `/tmp/cc-switch/codex-helper-config.json` | 适配器当前激活配置 |
| `/tmp/cc-switch/switcher-keys.json` | 内置 provider 的 API Key |
| `/tmp/cc-switch/switcher-custom-providers.json` | 自定义 provider 条目 |
| `/tmp/cc-switch/token-usage.json` | Token 用量统计 |
| `~/.codex/config.toml` | Codex 主配置（被字段级修改） |
| `~/.codex/config.toml.openai-backup` | 切换前的完整备份，用于回滚 |

---

## 已知限制

- 自定义提供商功能假设上游是 **OpenAI Chat Completions 兼容**协议
- 适配器只在 `127.0.0.1:18667` 监听，外网访问不到
- 同一时刻只能挂一家上游（这是 Codex 的限制）

---

## License

[MIT](LICENSE) © 2026 Codex助手
