# Codex助手

> 给 OpenAI **Codex App** 接入 DeepSeek / Kimi / 智谱 / 通义 / 小米MiMo / LongCat 等任意 OpenAI 兼容大模型的桌面助手。**一键切换、一键回滚。** macOS / Windows 双平台支持，内置激活码管理系统。

![status](https://img.shields.io/badge/status-beta-orange)
![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## 它解决什么

OpenAI Codex App 默认只能用官方 GPT 模型。但你可能希望：

- **省钱**：换成 DeepSeek、Kimi、智谱、通义、小米MiMo 等便宜很多倍的模型
- **国内速度**：直连国内厂商 API，不走代理
- **多家随手切**：今天用 DeepSeek，明天用 Kimi，再后天试自己加的小米 MiMo

Codex助手 在你本机起一个适配器（Codex `Responses` API ↔ OpenAI `chat/completions`），帮你把 Codex 的请求转给你选的任何 OpenAI 兼容上游。

---

## 特性

- 🪄 **一键切换**：选模型 -> 输 Key -> 点按钮，完事
- ↩️ **一键回滚**：随时切回 OpenAI 原版，零残留
- ➕ **自定义提供商**：内置常见平台模板（DeepSeek / Kimi / 智谱 / 通义 / 小米MiMo / StepFun / LongCat / Claude / Gemini / APINest），选模板自动填 Base URL 和模型名，只补 Key 就能用
- 🔐 **Key 分家存**：每家 Key 单独保存，互不覆盖，下次自动加载
- 🛡️ **不破坏原配置**：字段级合并 Codex `config.toml`，保留你所有原有的配置
- 💾 **自动备份**：第一次切之前自动把原 `config.toml` 备份到 `.openai-backup`
- 📊 **用量统计**：实时统计 Token 用量（输入/输出/缓存），按模型分组展示，支持调用历史记录
- 🚨 **错误追踪**：自动记录上游 API 错误，方便排查问题
- 🌗 **浅色/深色/专注**：三套主题，品牌图随主题自动切换
- 📦 **双平台支持**：macOS 原生 .app + Windows 便携版，开箱即用
- 🔑 **激活码系统**：内置激活码管理后台，支持按天/永久两种授权模式，设备绑定防滥用

---

## 谁能用

- **OS**：macOS 12+ / Windows 10+
- **前置**：装好 OpenAI Codex App（任意版本）
- **依赖**：无（macOS .app 和 Windows 便携版均自带运行时；自己跑源码需 Python 3.10+）

---

## 内置支持的平台

| 平台 | 模型示例 | Base URL |
|------|---------|----------|
| DeepSeek | deepseek-v4-pro / deepseek-v4-flash | api.deepseek.com |
| Kimi CN | kimi-k3 / kimi-k2.7-code / kimi-k2.6 | api.moonshot.cn |
| 智谱 | glm-5.2 / glm-5.1 / glm-5-turbo | open.bigmodel.cn |
| 通义 | qwen3.8-max-preview / qwen3.7-max / qwen3.7-plus | dashscope.aliyuncs.com |
| 小米MiMo | mimo-v2.5-pro / mimo-v2.5 | api.xiaomimimo.com |
| StepFun | step-3.7-flash / step-3.5-flash | api.stepfun.com |
| LongCat | LongCat-2.0 / LongCat-Flash | api.longcat.chat |
| Claude | claude-opus-5 / claude-sonnet-5 | api.anthropic.com |
| Gemini | gemini-3.6-flash / gemini-3.5-flash | generativelanguage.googleapis.com |
| APINest | 多模型聚合 | apinest.eu.cc |

> 也可以选「自定义」，手动填写任意 OpenAI 兼容的 Base URL / 模型名 / API Key。

---

## 用法

1. 下载 `Codex助手.dmg`（macOS）或 `Codex助手-Windows-portable.zip`（Windows）
2. 安装并启动
3. 首次使用需要输入激活码（联系管理员获取）
4. 在窗口里：
   - 点击「模型配置」添加你要用的模型
   - 选择服务商和模型，粘贴对应平台的 API Key
   - 保存后回到首页，点开关按钮启动服务
5. 打开 Codex App，开始用
6. 不用了：点开关按钮停止服务，自动切回 OpenAI 原版

---

## 激活码管理后台

项目内置一个独立的 Web 管理后台，用于管理激活码：

- 创建/删除/禁用激活码
- 支持按天授权和永久授权两种模式
- 查看激活码绑定状态和设备信息
- 查看操作日志
- 设备绑定，一码一机

### 后台部署

```bash
# 1. 进入 admin 目录
cd admin

# 2. 安装依赖
npm install

# 3. 配置环境变量
cat > .env << 'EOF'
ADMIN_TOKEN=your-secure-token
PORT=3000
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_NAME=codex_admin
EOF

# 4. 启动开发模式
npm run dev

# 5. 或构建生产模式
npm run build
npm run start
```

后台基于 Next.js 14 + MySQL + Arco Design 构建。

---

## 加新模型

在「模型配置」页面点「新增模型」：

- 选择服务商模板（内置 10+ 个常见平台），自动填 Base URL 和模型名
- 或者选「自定义」，全手填：显示名 / 模型 ID / Base URL / API Key

已添加的模型可以随时编辑或删除。

---

## 适配器工作原理

```
Codex App  --[Responses API]-->  适配器 (127.0.0.1:18667)  --[chat/completions]-->  上游模型 API
```

- 适配器在本地 `127.0.0.1:18667` 监听，接收 Codex 的 Responses API 请求
- 自动转换为 OpenAI Chat Completions 格式，转发给你配置的上游 API
- 支持**流式输出**和**非流式**两种模式
- 支持**函数调用**（Function Calling / Tool Use）
- 请求中的 Authorization 头会被替换为你配置的 API Key
- `requires_openai_auth = false`，无论 Codex 用 API Key 登录还是账号登录都能正常工作

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

# 4. 打包 macOS .app
bash build_app.sh
# 产物：dist/Codex助手.app

# 5. 打包 macOS .dmg
bash build_dmg.sh
# 产物：dist/Codex助手.dmg

# 6. 打包 Windows 便携版
bash build_windows_portable.sh
# 产物：dist/Codex助手-Windows-portable.zip
```

---

## 项目结构

```
codex-assistant/
├─ src/
│   ├─ adapter.py       # 适配器：Codex Responses ↔ OpenAI chat/completions
│   ├─ core.py          # 配置管理、provider 路由、Key 存储、适配器启停
│   ├─ web_api.py       # HTTP 控制 API 服务器 + 状态管理
│   ├─ web_launcher.py  # pywebview 桌面启动器
│   ├─ activation.py    # 激活码验证与设备绑定
│   ├─ gui_ctk.py       # CustomTkinter GUI 版
│   └─ tests/           # 沙箱测试
├─ web/
│   └─ index.html       # Web 前端界面（含三套主题）
├─ admin/               # 激活码管理后台（Next.js）
│   ├─ app/             # Next.js App Router 页面和 API
│   ├─ lib/             # 数据库、工具库
│   └─ package.json
├─ assets/              # 品牌图片、图标、吉祥物
├─ build_app.sh         # macOS .app 打包脚本
├─ build_dmg.sh         # macOS .dmg 打包脚本
├─ build_windows_portable.sh  # Windows 便携版打包脚本
├─ deploy_all_in_one.sh      # 服务器一键部署脚本
├─ requirements.txt
├─ LICENSE              # MIT
└─ README.md
```

---

## 数据存哪

| 文件 | 内容 |
|---|---|
| `系统临时目录/cc-switch/codex-helper-config.json` | 适配器当前激活配置（upstream / model / api_key） |
| `系统临时目录/cc-switch/switcher-keys.json` | 内置 provider 的 API Key |
| `系统临时目录/cc-switch/switcher-custom-providers.json` | 自定义 provider 条目 |
| `系统临时目录/cc-switch/token-usage.json` | Token 用量统计 |
| `~/.codex/config.toml` | Codex 主配置（被字段级修改） |
| `~/.codex/config.toml.openai-backup` | 切换前的完整备份，用于回滚 |
| `~/.codex-helper/activation.json` | 激活码本地缓存（设备绑定信息） |

> macOS 沙箱环境下，系统临时目录通常在 `/var/folders/.../T/`。

---

## 已知限制

- 自定义提供商功能假设上游是 **OpenAI Chat Completions 兼容**协议
- 适配器只在 `127.0.0.1:18667` 监听，外网访问不到
- 同一时刻只能挂一家上游（这是 Codex 的限制）

---

## License

[MIT](LICENSE) © 2026 Codex助手
