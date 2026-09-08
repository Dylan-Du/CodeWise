# Codex助手品牌整理实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留“Codex助手”产品名称和现有功能兼容性的前提下，清理开发过程痕迹、统一旧内部命名，并重制应用与官网使用的品牌资源。

**Architecture:** 采用“可见层优先、兼容层不动”的策略。先集中处理界面、文档、官网和打包元数据，再处理资源替换；本地数据目录、历史配置键、旧 provider 标识和适配器协议保持兼容。第三方来源、商标免责和许可信息单独审核，不通过删除来源来制造原创假象。

**Tech Stack:** Python 3.10+、原生 HTML/CSS/JavaScript、pywebview、CustomTkinter、Shell/Batch 打包脚本、SVG/PNG 资源、Git。

---

## 文件变更地图

- 修改 `web/index.html`：统一应用内可见产品名称、兼容性说明和品牌资源引用。
- 修改 `src/gui_ctk.py`：统一原生窗口标题、状态栏和日志中的可见名称。
- 修改 `src/web_launcher.py`、`src/terminal_launcher.py`：只调整用户可见提示，不改变历史配置键和内部适配器标识。
- 修改 `README.md`、`AGENTS.md`、`website/index.html`、`codex-user-guide/codex-user-guide.html`：清理过程性措辞，统一产品定位、商标说明和资源展示。
- 修改 `NOTICE`：区分项目原创代码、第三方代码/数据、主题资源和依赖许可，避免过宽的版权声明。
- 修改 `build_app.sh`、`build_windows.bat`、`build_windows_portable.sh`：统一构建展示名称、图标引用和安装包元数据，保留历史数据路径兼容。
- 修改或替换 `assets/logo.svg`、`assets/brand-text.png`、`assets/brand-text-dark.png`、`assets/mascot-3d.png` 及 `website/assets/` 中对应资源。
- 检查 `src/theme_manager.py` 和 `assets/dream-skin/`：保留必要来源，修正不准确或过宽的说明。
- 新增静态检查脚本 `src/tests/test_branding.py`：验证旧内部品牌只出现在允许的兼容位置、可见文件不含过程性措辞、资源引用存在。

### Task 1: 建立品牌引用清单与测试基线

**Files:**
- Create: `src/tests/test_branding.py`
- Inspect: `web/index.html`
- Inspect: `README.md`
- Inspect: `website/index.html`
- Inspect: `codex-user-guide/codex-user-guide.html`
- Inspect: `src/`、`build_app.sh`、`build_windows.bat`、`build_windows_portable.sh`

- [ ] **Step 1: 写品牌静态检查测试**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VISIBLE_FILES = (
    ROOT / "web/index.html",
    ROOT / "README.md",
    ROOT / "website/index.html",
    ROOT / "codex-user-guide/codex-user-guide.html",
    ROOT / "src/gui_ctk.py",
    ROOT / "src/web_launcher.py",
    ROOT / "src/terminal_launcher.py",
    ROOT / "build_app.sh",
    ROOT / "build_windows.bat",
    ROOT / "build_windows_portable.sh",
)


def test_visible_files_keep_product_name():
    for path in VISIBLE_FILES:
        assert "Codex助手" in path.read_text(encoding="utf-8"), path


def test_visible_files_do_not_expose_process_phrase():
    forbidden = ("过程性品牌措辞", "匹配 HTML 设计稿", "抄袭", "仿制")
    for path in VISIBLE_FILES:
        text = path.read_text(encoding="utf-8")
        assert not any(item in text for item in forbidden), path


def test_required_compatibility_copy_remains():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "OpenAI" in readme
    assert "Codex" in readme


def test_brand_assets_exist():
    for relative in (
        "assets/logo.svg",
        "assets/brand-text.png",
        "assets/brand-text-dark.png",
        "assets/mascot-3d.png",
    ):
        assert (ROOT / relative).exists(), relative
```

- [ ] **Step 2: 运行基线测试**

Run: `python3 src/tests/test_branding.py`

Expected: 当前测试可能因旧过程性措辞或旧资源引用失败；记录失败文件和具体字符串，作为后续修改清单，不修改测试断言来绕过问题。

- [ ] **Step 3: 建立允许保留的兼容标识集合**

在测试文件中增加明确的允许范围说明：`codex_helper_adapter`、历史 JSON 数据目录名、历史 provider 标识和第三方来源 URL 仅允许出现在兼容实现、迁移逻辑或许可说明中，不允许出现在用户可见主标题、官网主视觉或安装包展示名称中。

- [ ] **Step 4: 提交测试基线**

```bash
git add src/tests/test_branding.py
git commit -m "test: define branding cleanup checks"
```

### Task 2: 清理界面与用户文案

**Files:**
- Modify: `web/index.html`
- Modify: `src/gui_ctk.py`
- Modify: `src/web_launcher.py`
- Modify: `src/terminal_launcher.py`

- [ ] **Step 1: 替换用户可见过程性文字**

将内部调整记录、设计稿匹配、开发过程说明等内容删除或改为功能描述；保留 `Codex助手` 作为产品名。状态文案使用“本地适配器”“模型连接”“Codex 兼容”等准确术语。

- [ ] **Step 2: 收敛兼容性说明**

在设置、关于或帮助区域保留一处明确兼容说明，例如“Codex助手是面向 OpenAI Codex 的本地模型适配器”，不要在每个状态标签中重复 OpenAI/Codex 品牌。不得修改 `model_provider = "codex_helper_adapter"` 等历史配置值。

- [ ] **Step 3: 统一原生 GUI 标题和状态文本**

保留 `APP_TITLE = "Codex助手"`，将状态栏中的旧内部品牌、问号占位符和不完整文案改为稳定的模型连接描述。只修改显示文本，不改变配置读写、端口或适配器调用。

- [ ] **Step 4: 运行 Python 编译检查**

Run: `python3 -m py_compile src/*.py`

Expected: `src` 下 Python 文件全部编译通过。

- [ ] **Step 5: 提交界面文案清理**

```bash
git add web/index.html src/gui_ctk.py src/web_launcher.py src/terminal_launcher.py
git commit -m "refactor: clean visible branding copy"
```

### Task 3: 清理 README、官网和用户手册

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `website/index.html`
- Modify: `codex-user-guide/codex-user-guide.html`

- [ ] **Step 1: 统一产品定位**

标题、描述、页眉、页脚和下载区域统一使用“Codex助手”。将产品描述集中为“纯本地桌面适配器”，说明 APINest、自定义服务商、主题系统和本地数据处理能力。

- [ ] **Step 2: 收敛 Codex/OpenAI 词频**

保留产品确实需要的兼容性说明、配置步骤和商标免责；删除重复的宣传式表述，不将 OpenAI/Codex 写成项目所属品牌，不删除技术上必须保留的 API 和配置说明。

- [ ] **Step 3: 删除开发过程痕迹**

删除内部调整记录、设计稿匹配、来源不明的自我描述和任何暗示复制过程的句子。用户手册只保留安装、配置、主题、故障排查和数据迁移步骤。

- [ ] **Step 4: 检查静态引用**

Run: `python3 -m pytest src/tests/test_branding.py -q`

Expected: 文案检查通过；若资源尚未替换导致资源断言失败，记录为 Task 4 的预期失败，不删除断言。

- [ ] **Step 5: 提交文档清理**

```bash
git add README.md AGENTS.md website/index.html codex-user-guide/codex-user-guide.html
git commit -m "docs: unify product and compatibility messaging"
```

### Task 4: 重制并统一品牌资源

**Files:**
- Modify: `assets/logo.svg`
- Replace: `assets/brand-text.png`
- Replace: `assets/brand-text-dark.png`
- Replace: `assets/mascot-3d.png`
- Modify: `website/assets/`
- Modify: `build_app.sh`
- Modify: `build_windows.bat`

- [ ] **Step 1: 定义资源约束**

主视觉继续显示“Codex助手”，使用原创的简洁桥接/连接符号，不复制第三方产品图标结构。Logo 必须提供 SVG 主源文件；PNG 仅作为导出物，浅色和深色版本使用同一字形与间距规则。

- [ ] **Step 2: 更新 SVG 主 Logo**

在 `assets/logo.svg` 中保留清晰的矢量尺寸、透明背景和可缩放路径，避免引用外部字体或网络资源。Logo 文字使用“Codex助手”，图形只表达本地连接与模型桥接，不使用第三方品牌图形。

- [ ] **Step 3: 更新应用和官网资源引用**

将 `web/index.html`、`website/index.html` 和构建脚本中的资源路径改为实际存在的文件。不要保留已经删除的 `CodexSwitch` 或旧 mascot 文件名作为可见入口。

- [ ] **Step 4: 处理 APINest 资源**

如果无法确认 `assets/apinest-logo.png` 的使用授权，则在服务商选择界面改为文字标识或通用服务商图标；不得把 APINest 标识融入 Codex助手主 Logo。

- [ ] **Step 5: 运行资源引用检查**

Run: `python3 - <<'PY'
from pathlib import Path
import re
root = Path('.')
for path in [root / 'web/index.html', root / 'website/index.html']:
    text = path.read_text(encoding='utf-8')
    for value in re.findall(r'(?:src|href)=["\']([^"\']+)', text):
        if value.startswith(('http://', 'https://', '#', 'data:')):
            continue
        assert (path.parent / value).exists(), f'{path}: {value}'
print('asset references: ok')
PY`

Expected: 输出 `asset references: ok`。

- [ ] **Step 6: 提交资源和构建入口变更**

```bash
git add assets web/index.html website/index.html build_app.sh build_windows.bat
# 若资源文件是二进制，确认 git diff --stat 中包含预期替换
git commit -m "refactor: refresh Codex助手 brand assets"
```

### Task 5: 审核来源、许可和版权说明

**Files:**
- Modify: `NOTICE`
- Modify: `src/theme_manager.py`
- Modify: `assets/dream-skin/` 中需要修正的 manifest
- Inspect: `LICENSE`

- [ ] **Step 1: 保留第三方选择器来源**

检查 `src/theme_manager.py` 中的 Fei-Away/Codex-Dream-Skin 来源对应的实际复用内容和许可证。若许可证要求署名，保留来源并补充用途说明；若代码已不再使用该数据，删除无效引用，但不能只为隐藏来源而删除有效署名。

- [ ] **Step 2: 修正 NOTICE**

将“所有源代码版权归 Codex助手所有”改为分层说明：项目原创代码归项目作者或贡献者；第三方代码、选择器、主题背景、插画和依赖库按各自许可证执行。不得声明项目拥有无法证明的图片或第三方代码版权。

- [ ] **Step 3: 审核主题 manifest**

对每个来源不清的背景资源，保留准确的来源说明，或替换为可确认来源/自制资源。不得把“网图+AI”改成虚假的原创来源，也不得删除权利人联系和替换说明。

- [ ] **Step 4: 运行来源文本检查**

Run: `python3 -m pytest src/tests/test_branding.py -q`

Expected: 版权、来源和兼容性相关文本保留，过程性品牌措辞不再出现。

- [ ] **Step 5: 提交法律与来源说明修订**

```bash
git add NOTICE src/theme_manager.py assets/dream-skin
 git commit -m "docs: clarify third-party attribution"
```

### Task 6: 更新打包元数据并验证兼容性

**Files:**
- Modify: `build_app.sh`
- Modify: `build_windows.bat`
- Modify: `build_windows_portable.sh`
- Test: `src/tests/test_core.py`
- Test: `src/tests/test_branding.py`

- [ ] **Step 1: 保留历史数据和配置键**

确认 `~/.codex-helper/data/`、`codex_helper_adapter`、历史 provider 配置和官方配置备份路径不变；只调整应用显示名、安装器显示名、图标和包内资源。

- [ ] **Step 2: 统一 macOS 构建展示名称**

让 `build_app.sh` 使用新的 Logo 导出物和统一的 `Codex助手` 显示名称，同时保留必要的 Python 模块、主题目录和 APINest 资源。禁止把后台、激活或远程授权文件重新打入包内。

- [ ] **Step 3: 统一 Windows 构建展示名称**

让 `build_windows.bat` 的窗口标题、EXE 名称、安装包名称、发布者显示和图标引用统一；不更改旧注册表路径或本地数据目录，避免升级时丢失配置。

- [ ] **Step 4: 验证基础功能**

Run: `python3 -m py_compile src/*.py && python3 src/tests/test_core.py && python3 -m pytest src/tests/test_branding.py -q`

Expected: 编译成功，核心测试全部通过，品牌静态检查全部通过。

- [ ] **Step 5: 检查包内容**

Run: `bash build_app.sh` 和 `bash build_windows_portable.sh`（按当前平台和脚本依赖执行）。

Expected: 生成 macOS/Windows 包；包内不包含 `activation.py`、`admin/`、远程授权服务或旧品牌作为用户可见主名称。

- [ ] **Step 6: 提交构建调整**

```bash
git add build_app.sh build_windows.bat build_windows_portable.sh
git commit -m "build: align package branding"
```

### Task 7: 完成发布前验收

**Files:**
- Inspect: 全部变更文件
- Test: `src/tests/test_core.py`
- Test: `src/tests/test_branding.py`

- [ ] **Step 1: 扫描过程性措辞和旧可见品牌**

Run: `git grep -n -E '过程性品牌措辞|匹配 HTML 设计稿|CodexSwitch|CodexHelper|抄袭|仿制' -- ':!docs/superpowers/specs/**' ':!docs/superpowers/plans/**'`

Expected: 无用户可见主品牌或过程性措辞；仅允许兼容键、迁移逻辑和历史构建注释中的必要保留项，并逐项人工确认。

- [ ] **Step 2: 扫描资源引用**

Run: 前述资源引用脚本，并检查 `git diff --check`。

Expected: 所有相对资源存在，Git 空白检查通过。

- [ ] **Step 3: 运行完整测试**

Run: `python3 -m py_compile src/*.py && python3 src/tests/test_core.py && python3 -m pytest src/tests/test_branding.py -q`

Expected: 全部通过。

- [ ] **Step 4: 检查 Git 历史边界**

Run: `git log --oneline -10`

Expected: 不自动重写既有提交历史；新提交信息使用功能或文档描述，不使用“品牌清理”作为公开过程性标题。

- [ ] **Step 5: 创建最终汇总提交**

```bash
git status --short
git diff --stat
git commit -m "chore: finalize Codex助手 brand refresh"
```

Expected: 工作树干净，提交内容只包含本方案范围内的文案、资源、构建和测试变更。
