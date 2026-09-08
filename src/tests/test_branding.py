"""品牌整理静态验收测试。

本测试只检查用户可见入口和核心资源，不修改业务代码。
历史配置键、数据目录和协议 User-Agent 属于兼容面，允许继续保留；
它们不能作为产品名称、窗口标题或用户界面文案使用。
"""
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]

# 用户可见的品牌入口。内部设计记录不纳入本清单，避免把实施过程当作产品文案。
VISIBLE_FILES = (
    "README.md",
    "NOTICE",
    "AGENTS.md",
    "web/index.html",
    "website/index.html",
    "codex-user-guide/codex-user-guide.html",
    "release/使用说明.txt",
)

# 这些标识只允许存在于兼容实现中，不得回到可见主品牌。
# 每项是“兼容范围”的明确约束：文件 + 必须出现的中性/技术上下文。
ALLOWED_COMPATIBILITY_MARKERS = {
    "README.md": (
        "~/.codex-helper/data/",
        "旧版本留下的本地授权文件",
    ),
    "AGENTS.md": (
        "~/.codex-helper/data/",
        "旧版本留下的本地授权文件",
    ),
}

PRODUCT_NAME = "Codex助手"
REQUIRED_COMPATIBILITY_TERMS = ("OpenAI", "Codex")
FORBIDDEN_PROCESS_WORDING = (
    "优化UI与品牌清理",
    "抄袭",
    "仿制",
    "匹配某设计稿",
)
LEGACY_BRAND_MARKERS = ("CodexSwitch", "CodexHelper")
CORE_BRAND_ASSETS = (
    "assets/logo.svg",
    "assets/brand-text.png",
    "assets/brand-text-dark.png",
    "assets/icon.icns",
    "assets/icon.ico",
)


class BrandingTest(unittest.TestCase):
    def read_visible_files(self):
        return {
            relative: (REPO_ROOT / relative).read_text(encoding="utf-8")
            for relative in VISIBLE_FILES
        }

    def test_visible_surfaces_keep_product_name(self):
        """用户可见入口应保留 Codex助手 作为产品名称。"""
        for relative, content in self.read_visible_files().items():
            with self.subTest(file=relative):
                self.assertIn(PRODUCT_NAME, content)

    def test_visible_surfaces_exclude_process_wording(self):
        """用户可见入口不得暴露品牌整理或仿制等过程性措辞。"""
        for relative, content in self.read_visible_files().items():
            for wording in FORBIDDEN_PROCESS_WORDING:
                with self.subTest(file=relative, wording=wording):
                    self.assertNotIn(wording, content)

    def test_visible_surfaces_explain_required_codex_compatibility(self):
        """至少一个公开入口应准确说明 OpenAI Codex 兼容关系。"""
        visible_text = "\n".join(self.read_visible_files().values())
        for term in REQUIRED_COMPATIBILITY_TERMS:
            with self.subTest(term=term):
                self.assertIn(term, visible_text)
        self.assertRegex(visible_text, r"OpenAI.{0,80}Codex|Codex.{0,80}OpenAI")

    def test_legacy_markers_are_limited_to_compatibility_scope(self):
        """旧标识只能留在明确的历史兼容说明中，不能成为可见主品牌。"""
        for relative, content in self.read_visible_files().items():
            for marker in LEGACY_BRAND_MARKERS:
                with self.subTest(file=relative, marker=marker):
                    if marker not in content:
                        continue
                    allowed_contexts = ALLOWED_COMPATIBILITY_MARKERS.get(relative, ())
                    self.assertTrue(
                        any(context in content for context in allowed_contexts),
                        f"{relative} 中的 {marker} 不在允许的兼容范围内",
                    )
                    self.assertNotIn(
                        f"产品名称：{marker}", content,
                    )
                    self.assertNotIn(
                        f"<title>{marker}", content,
                    )

    def test_core_brand_assets_exist(self):
        """主 Logo、深浅色品牌文字和应用图标资源必须存在。"""
        for relative in CORE_BRAND_ASSETS:
            with self.subTest(asset=relative):
                asset = REPO_ROOT / relative
                self.assertTrue(asset.is_file(), f"缺少核心品牌资源：{relative}")
                self.assertGreater(asset.stat().st_size, 0, f"核心品牌资源为空：{relative}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
