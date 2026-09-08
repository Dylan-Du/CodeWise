"""品牌整理静态验收测试。

测试覆盖品牌整理计划中的应用入口、构建入口和核心资源。历史配置键、数据
目录、provider 标识以及真实第三方 URL 属于兼容面，只有出现在明确技术上下文
中才允许保留；它们不得成为产品名称或用户界面主品牌。
"""
from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]

# 品牌整理计划明确列出的入口；NOTICE、AGENTS 和 release 不是产品名断言范围。
BRAND_SURFACE_FILES = (
    "src/gui_ctk.py",
    "src/web_launcher.py",
    "src/terminal_launcher.py",
    "build_app.sh",
    "build_windows.bat",
    "build_windows_portable.sh",
    "web/index.html",
    "website/index.html",
    "codex-user-guide/codex-user-guide.html",
)

PRODUCT_NAME = "Codex助手"
FORBIDDEN_PROCESS_WORDING = (
    "优化UI与品牌清理",
    "抄袭",
    "仿制",
    "匹配 HTML 设计稿",
)
LEGACY_BRAND_MARKERS = ("CodexSwitch", "CodexHelper")
CORE_BRAND_ASSETS = (
    "assets/logo.svg",
    "assets/brand-text.png",
    "assets/brand-text-dark.png",
    "assets/mascot-3d.png",
    "assets/icon.icns",
    "assets/icon.ico",
)

# 兼容性约束按类别明确限定：允许保留，但不能被误判为新的产品品牌。
COMPATIBILITY_CONTEXTS = {
    "codex_helper_adapter": (
        "model_provider",
        "model_providers",
        "THREAD_PROVIDER_ADAPTER",
        "历史对话",
        "历史会话",
    ),
    "~/.codex-helper/": (
        "数据",
        "配置",
        "日志",
        "历史",
        "data/",
    ),
    "provider": (
        "provider",
        "服务商",
        "模型",
        "upstream",
        "兼容",
    ),
}

# README 需要独立说明产品与 OpenAI/Codex 的真实兼容关系。
README_REQUIRED_TERMS = ("OpenAI", "Codex")


class BrandingTest(unittest.TestCase):
    def read_files(self, relatives):
        return {
            relative: (REPO_ROOT / relative).read_text(encoding="utf-8")
            for relative in relatives
        }

    def test_planned_brand_surfaces_keep_product_name(self):
        """计划中的应用入口和构建入口应使用统一产品名。"""
        for relative, content in self.read_files(BRAND_SURFACE_FILES).items():
            with self.subTest(file=relative):
                self.assertIn(PRODUCT_NAME, content)

    def test_readme_separately_explains_openai_codex_compatibility(self):
        """README 单独断言 OpenAI 和 Codex，而非扩大到所有文档。"""
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for term in README_REQUIRED_TERMS:
            with self.subTest(term=term):
                self.assertIn(term, readme)
        self.assertRegex(readme, r"OpenAI.{0,100}Codex|Codex.{0,100}OpenAI")

    def test_brand_surfaces_exclude_exact_forbidden_wording(self):
        """用户可见入口不得暴露品牌整理或仿制等过程性措辞。"""
        for relative, content in self.read_files(
            (*BRAND_SURFACE_FILES, "README.md")
        ).items():
            for wording in FORBIDDEN_PROCESS_WORDING:
                with self.subTest(file=relative, wording=wording):
                    self.assertNotIn(wording, content)

    def test_legacy_markers_are_limited_to_compatibility_scope(self):
        """旧标识只能保留在明确的兼容、迁移或构建技术上下文中。"""
        all_files = tuple(BRAND_SURFACE_FILES) + (
            "README.md",
            "src/core.py",
            "src/web_api.py",
        )
        for relative, content in self.read_files(all_files).items():
            for marker in LEGACY_BRAND_MARKERS:
                if marker not in content:
                    continue
                with self.subTest(file=relative, marker=marker):
                    self.assertFalse(
                        re.search(rf"产品名称\s*[:：]\s*{re.escape(marker)}", content)
                    )
                    self.assertFalse(
                        re.search(rf"<title>\s*{re.escape(marker)}", content, re.I)
                    )
                    # CodexHelper 仍可作为历史目录/安装注册表或内部兼容名；
                    # CodexSwitch 仍可作为旧构建/配置文件标识。
                    context = {
                        "CodexHelper": ("历史", "兼容", "注册表", "Install", "目录", "路径"),
                        "CodexSwitch": ("兼容", "历史", "构建", "配置", ".spec"),
                    }[marker]
                    self.assertTrue(
                        any(term in content for term in context),
                        f"{relative} 中的 {marker} 不在允许的兼容范围内",
                    )

    def test_compatibility_markers_have_explicit_allowed_contexts(self):
        """明确锁定适配器标识、历史数据目录、provider 和第三方 URL 的允许范围。"""
        sources = self.read_files((
            "src/core.py",
            "src/web_api.py",
            "src/web_launcher.py",
            "src/terminal_launcher.py",
            "README.md",
            "AGENTS.md",
        ))
        combined = "\n".join(sources.values())
        for marker, contexts in COMPATIBILITY_CONTEXTS.items():
            self.assertIn(marker, combined)
            self.assertTrue(
                any(context in combined for context in contexts),
                f"{marker} 缺少明确的兼容上下文",
            )

        # URL 允许出现在 provider 配置、帮助链接和 release 链接中；
        # 测试只禁止把第三方域名作为产品名/标题，而不禁止真实服务地址。
        for relative, content in sources.items():
            third_party_urls = re.findall(r"https?://[^\s'\"<>]+", content)
            for url in third_party_urls:
                self.assertNotRegex(
                    content,
                    rf"(?:产品名称|<title>)[^\n<>]*{re.escape(url)}",
                )

    def test_core_brand_assets_exist(self):
        """主 Logo、品牌文字、吉祥物和应用图标资源必须存在且非空。"""
        for relative in CORE_BRAND_ASSETS:
            with self.subTest(asset=relative):
                asset = REPO_ROOT / relative
                self.assertTrue(asset.is_file(), f"缺少核心品牌资源：{relative}")
                self.assertGreater(asset.stat().st_size, 0, f"核心品牌资源为空：{relative}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
