# 开源化与玻璃风 UI 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Codex助手 改造成无需激活、无需远程服务即可使用的开源客户端，并在现有信息架构上完成深色玻璃风 UI 优化。

**Architecture:** 保留本地 `web_api.py`、`core.py`、`adapter.py` 和现有配置数据结构；移除激活/设备绑定/远程上报链路及 `admin/` 管理后台。前端继续使用单文件 HTML，通过保留旧模型数据、限制新增表单选项为 APINest/自定义来实现兼容迁移；视觉层集中调整现有 CSS 变量、卡片、导航和表单样式，不重写业务状态逻辑。

**Tech Stack:** Python 3.10 标准库、原生 HTML/CSS/JavaScript、PyInstaller、现有 Python 测试。

---

## 文件范围

- Modify: `src/web_api.py`，移除激活路由、启动前激活拦截、远程错误上报调用。
- Modify: `src/activation.py`，删除生产依赖；保留文件不参与运行，避免升级时删除用户文件。
- Modify: `src/core.py`，清理启动/切换流程中的授权依赖（如存在），保持本地适配器逻辑。
- Modify: `web/index.html`，移除授权 UI/请求，新增表单只显示 APINest/自定义，并升级玻璃风样式。
- Modify: `README.md`，改为纯客户端开源项目说明，删除激活后台与服务器部署章节。
- Delete: `admin/`，删除独立授权管理后台及其数据库和构建产物。
- Delete: 服务端部署脚本 `deploy.sh`、`update_admin.sh`、`update_upload.sh`（仅在文件存在且仅服务于 admin 时删除）。
- Modify: `build_dmg.sh`、`build_app.sh`、`build_windows_portable.sh`，确认打包只收集客户端资源并递增版本号。
- Modify: `src/tests/test_core.py`，加入无激活启动和 provider 过滤相关回归测试（按现有测试风格）。

## Task 1: 建立基线与测试

- [ ] 运行 `python3 -m py_compile src/*.py`，记录当前语法基线。
- [ ] 运行 `python3 src/tests/test_core.py`，确认现有核心测试结果。
- [ ] 搜索 `web_api.py`、`core.py`、`web/index.html` 中所有 activation、report-error、provider 配置入口，列出要移除的具体调用点。
- [ ] 检查三个打包脚本是否引用 `admin/` 或激活资源，避免误删客户端必需文件。

## Task 2: 移除客户端授权依赖

**Files:** `src/web_api.py`、`src/core.py`、`web/index.html`

- [ ] 在 `web_api.py` 删除 `import activation`、`/api/activation/status`、`/api/activation/activate` 分支及对应 handler。
- [ ] 删除启动/切换动作中 `activation.is_activated()` 判断，让本地配置校验和适配器启动直接执行。
- [ ] 删除 `activation.report_error()` 调用，保留本地 `error-log.json` 写入路径和现有错误响应。
- [ ] 在前端删除激活遮罩 DOM、激活状态请求、提交激活码逻辑、设备码展示和激活错误文案。
- [ ] 确认 `core.py` 不再导入或调用 activation；若存在授权分支，仅删除授权条件，不改变 provider、备份、恢复和 gatekeeper 行为。
- [ ] 添加/更新测试：删除或重命名 `activation.json` 后，调用本地启动处理路径不返回 `need_activation`；API Key/Base URL/模型缺失仍返回本地校验错误。
- [ ] 运行 `python3 -m py_compile src/*.py` 与 `python3 src/tests/test_core.py`。
- [ ] 提交：`git add src/web_api.py src/core.py web/index.html src/tests/test_core.py && git commit -m "feat: remove activation requirement"`。

## Task 3: 精简新增模型服务商

**Files:** `web/index.html`、相关 provider 配置代码

- [ ] 将新增模型表单的 provider `<select>` 改为只渲染 `APINest` 和 `自定义`，不直接改写旧模型保存数据。
- [ ] 保留 APINest 预设 Base URL 和模型列表；选中 APINest 时展示预设地址、模型下拉和 API Key。
- [ ] 选中自定义时展示 Base URL、模型名称和 API Key，并允许 OpenAI 兼容地址。
- [ ] 编辑已有旧 provider 模型时继续显示原 provider 和原配置，保证旧数据可用；仅新增时限制选项。
- [ ] 更新 provider 选择、模型下拉、编辑回填和 URL 测试逻辑，确保切换两项时不会残留错误字段。
- [ ] 使用静态检查确认新增表单中只出现两个 provider option，运行现有核心测试。
- [ ] 提交：`git add web/index.html src/tests/test_core.py && git commit -m "feat: limit new providers to APINest and custom"`。

## Task 4: 删除服务端与文档中的授权内容

**Files:** `admin/`、部署脚本、`README.md`、发布说明

- [ ] 删除 `admin/` 目录，确保仅删除仓库服务端代码、数据库和前端构建产物。
- [ ] 删除只用于管理后台部署的 `deploy.sh`、`update_admin.sh`、`update_upload.sh`；若脚本包含客户端逻辑，先拆除服务端段落后再保留。
- [ ] 更新 README 项目简介、特性、用法、项目结构和构建说明，删除激活码、设备绑定、管理后台、数据库和服务端部署内容。
- [ ] 添加“纯本地运行”和“无账号/无激活”说明，注明 API Key 仅按现有方式保存在本机。
- [ ] 更新版本号说明，确保不再引用旧版本号或激活流程。
- [ ] 搜索仓库确认生产代码、文档和打包配置不再引用远程激活服务器或 admin。
- [ ] 提交：`git add -A && git commit -m "chore: remove activation backend and server docs"`。

## Task 5: 按现有 UI 优化玻璃风

**Files:** `web/index.html`

- [ ] 保留现有侧边栏、首页、模型中心、统计、主题和设置 DOM 结构，集中调整 CSS 变量与公共组件样式。
- [ ] 设置深色多层渐变背景、蓝紫/青色低强度光晕和半透明面板回退色。
- [ ] 为侧边栏、卡片、弹窗、模型卡片、表单区域增加透明背景、低透明度边框、`backdrop-filter: blur()` 和柔和阴影。
- [ ] 优化当前模型与服务状态层级，启动/停止按钮增加状态色和轻微光晕，避免仅靠颜色表达状态。
- [ ] 为卡片和按钮增加低幅度 hover/focus 动效，保留减少动画偏好支持。
- [ ] 将模型 provider 选择做成两个玻璃风选项卡或并列选择块，适配 APINest/自定义表单状态。
- [ ] 检查文字对比度、键盘 focus、窄窗口和不支持 backdrop-filter 环境下的纯色回退。
- [ ] 使用本地浏览器预览现有页面，确认无激活遮罩、玻璃层次正常、旧功能入口仍可达。
- [ ] 提交：`git add web/index.html && git commit -m "feat: refine client UI with glass visual system"`。

## Task 6: 打包与发布验收

**Files:** `build_dmg.sh`、`build_app.sh`、`build_windows_portable.sh`、版本文件

- [ ] 按项目版本约定递增 patch 版本，并同步 `build_dmg.sh`、`web/index.html` HTML 文本和 `APP_VERSION` 变量。
- [ ] 运行 `python3 -m py_compile src/*.py`。
- [ ] 运行 `python3 src/tests/test_core.py`。
- [ ] 执行 `bash build_dmg.sh`，检查产物启动所需资源齐全。
- [ ] 检查包内不含 `admin/`、激活后台运行时或服务端数据库。
- [ ] 检查包内前端不含激活弹窗执行逻辑，新增 provider 选项只有 APINest/自定义。
- [ ] 做一次无网络、无激活文件的启动/配置回归，确认本地服务可启动。
- [ ] 提交打包相关变更：`git add build_dmg.sh build_app.sh build_windows_portable.sh web/index.html && git commit -m "build: package open-source client release"`。
