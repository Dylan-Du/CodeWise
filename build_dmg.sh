#!/bin/bash
# Codex助手 — DMG 打包脚本
# 用法: bash build_dmg.sh
# 产物: dist/Codex助手-1.0.0.dmg

set -eo pipefail

# 清除 TRAE 终端的别名干扰
unalias rm 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Codex助手"
VERSION="1.0.75"
DIST_DIR="dist"
APP_DIR="${DIST_DIR}/Codex助手.app"
DMG_FINAL="${DIST_DIR}/${APP_NAME}-${VERSION}.dmg"

echo "═══════════════════════════════════════"
echo "  打包 ${APP_NAME} v${VERSION}"
echo "═══════════════════════════════════════"

# ─── 检查 Python ───
PY="$(command -v python3)"
echo "Python: $("$PY" --version 2>&1) ($PY)"
"$PY" -c "import webview; import tomlkit" || { echo "缺少依赖，请运行: pip install pywebview==5.3.2 tomlkit"; exit 1; }

# ─── 生成图标 ───
echo ""
echo "[1/2] 生成图标..."
ICONSET="build/icon.iconset"
rm -rf "$ICONSET"
mkdir -p "$ICONSET"

RSVG="rsvg-convert"
if ! command -v rsvg-convert &>/dev/null; then
  TRAE_RSVG="$HOME/Library/Application Support/TRAE SOLO CN/ModularData/ai-agent/vm/tools/bin/rsvg-convert"
  [ -f "$TRAE_RSVG" ] && RSVG="$TRAE_RSVG"
fi

LOGO_SVG="assets/logo.svg"
for SIZE in 16 32 128 256 512; do
  "$RSVG" -w "$SIZE" -h "$SIZE" "$LOGO_SVG" > "$ICONSET/icon_${SIZE}x${SIZE}.png" 2>/dev/null || true
  [ "$SIZE" -lt 512 ] && "$RSVG" -w "$((SIZE*2))" -h "$((SIZE*2))" "$LOGO_SVG" > "$ICONSET/icon_${SIZE}x${SIZE}@2x.png" 2>/dev/null || true
done
"$RSVG" -w 1024 -h 1024 "$LOGO_SVG" > "$ICONSET/icon_512x512@2x.png" 2>/dev/null || true
iconutil -c icns "$ICONSET" -o "assets/icon.icns"
rm -rf "$ICONSET"
echo "  图标生成完成"

# ─── PyInstaller 打包 ───
echo ""
echo "[2/2] PyInstaller 打包..."
rm -rf build dist/*.app

export PYINSTALLER_CONFIG_DIR="$SCRIPT_DIR/.pyinstaller_cache"
mkdir -p "$PYINSTALLER_CONFIG_DIR"

"$PY" -m PyInstaller \
  --clean --noconfirm --windowed \
  --name "Codex助手" \
  --icon "assets/icon.icns" \
  --add-data "web:web" \
  --add-data "assets/mascot-3d.png:assets" \
  --add-data "assets/brand-text.png:assets" \
  --add-data "assets/brand-text-dark.png:assets" \
  --add-data "assets/icon-1024.png:assets" \
  --add-data "assets/dream-skin:assets/dream-skin" \
  --add-data "assets/codex-model-template.json:assets" \
  --hidden-import webview \
  --hidden-import webview.platforms.cocoa \
  --hidden-import werkzeug \
  --hidden-import werkzeug.serving \
  --hidden-import tomlkit \
  --hidden-import tomlkit.api \
  --hidden-import tomlkit.container \
  --hidden-import tomlkit.items \
  --hidden-import tomlkit.parser \
  --hidden-import tomlkit.toml_document \
  --hidden-import tomlkit.toml_file \
  --hidden-import jinja2 \
  --hidden-import markupsafe \
  --hidden-import itsdangerous \
  --hidden-import click \
  --osx-bundle-identifier com.codexhelper.app \
  --exclude-module tkinter --exclude-module matplotlib \
  --exclude-module numpy --exclude-module pandas --exclude-module PIL \
  --exclude-module scipy --exclude-module wx \
  --exclude-module PyQt5 --exclude-module PyQt6 \
  --exclude-module PySide2 --exclude-module PySide6 \
  src/web_launcher.py 2>&1 | tail -5

rm -rf "$PYINSTALLER_CONFIG_DIR" *.spec

[ -d "$APP_DIR" ] || { echo "打包失败"; exit 1; }

# ─── 写入正确版本号到 Info.plist（PyInstaller 默认 0.0.0）───
PLIST="$APP_DIR/Contents/Info.plist"
if command -v /usr/libexec/PlistBuddy &>/dev/null; then
  /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$PLIST" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $VERSION" "$PLIST"
  /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$PLIST" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $VERSION" "$PLIST"
  echo "  Info.plist 版本号已写入: $VERSION"
fi

# ─── 改完 Info.plist 后必须重新签名 ───
# PyInstaller 已对 bundle 做过 ad-hoc 签名；PlistBuddy 改版本号会破坏签名，
# 导致 macOS 提示「已损坏」（且不给「仍要打开」选项）而不是「无法验证开发者」。
# 这里重新做 ad-hoc 签名，让 Gatekeeper 走「仍要打开」路径。
echo "  重新签名 (ad-hoc)..."
codesign --force --deep --sign - "$APP_DIR" 2>&1 | tail -2
codesign --verify --deep --strict --verbose=2 "$APP_DIR" 2>&1 | tail -2
echo "  签名完成"

# ─── 创建 DMG（定制背景 + 双文件居中）───
# 使用 dmgbuild 直接写 .DS_Store（bwsp 窗口配置 + Iloc 图标位置 + 背景图 alias），
# 完全绕开新版 macOS Finder AppleScript 对卷根 symlink 位置设置的限制。
echo ""
echo "创建 DMG（定制背景图 + 图标居中）..."

# 确保 dmgbuild 可用
"$PY" -c "import dmgbuild" 2>/dev/null || "$PY" -m pip install --break-system-packages -q dmgbuild 2>&1 | tail -1
"$PY" -c "import dmgbuild" || { echo "dmgbuild 安装失败，无法定制 DMG 布局"; exit 1; }

DMG_HELPER="$SCRIPT_DIR/.dmg_build_helper.py"
cat > "$DMG_HELPER" <<'PYEOF'
# -*- coding: utf-8 -*-
import os
from dmgbuild import build_dmg

BASE = os.path.dirname(os.path.abspath(__file__))
VERSION = os.environ.get("CODEX_HELPER_VERSION", "1.0.51")
OUT = os.path.join(BASE, "dist", "Codex助手-%s.dmg" % VERSION)
APP = os.path.join(BASE, "dist", "Codex助手.app")
BG = os.path.join(BASE, "assets", "dmg-background.png")
ICON = os.path.join(BASE, "assets", "icon.icns")

settings = {
    "filename": OUT,
    "volume_name": "Codex助手",
    "format": "UDZO",
    "filesystem": "HFS+",
    "size": None,
    "files": [APP],
    "symlinks": {"Applications": "/Applications"},
    "icon": ICON,
    "background": BG,
    "show_status_bar": False,
    "show_toolbar": False,
    "show_pathbar": False,
    "show_sidebar": False,
    "default_view": "icon-view",
    "arrange_by": None,
    "icon_size": 116.0,
    "text_size": 15.0,
    "show_item_info": False,
    "label_pos": "bottom",
    "window_rect": ((120, 150), (540, 278)),
    "icon_locations": {
        "Codex助手.app": (135, 130),
        "Applications": (405, 130),
    },
}
build_dmg(OUT, "Codex助手", settings=settings)
PYEOF
if CODEX_HELPER_VERSION="$VERSION" "$PY" "$DMG_HELPER"; then
  echo "  背景图 + 双文件居中布局写入成功"
else
  echo "DMG 创建失败"
  rm -f "$DMG_HELPER"
  exit 1
fi
rm -f "$DMG_HELPER"

# ─── 后处理：把 Finder 视图背景色改为深蓝（保证文件名白色可读）───
# dmgbuild 写 .DS_Store 时把 icvp 的 backgroundColor 硬编码为纯白 (1.0,1.0,1.0)，
# 会覆盖背景图亮度对 Finder 标签文字颜色的判定，导致文件名渲染成黑色看不清。
# 这里用 ds_store 的 'r+' 模式改写（不能用 'w+'：会 truncate 清空整个 store）。
echo "  后处理：调整 Finder 背景色为深蓝（文件名转白色）..."
hdiutil convert "$DMG_FINAL" -format UDRW -o /tmp/codex_helper_fix_rw.dmg
hdiutil attach /tmp/codex_helper_fix_rw.dmg -nobrowse -mountpoint /tmp/codex_helper_fix_mnt
"$PY" - <<'PY'
from ds_store import DSStore
p = "/tmp/codex_helper_fix_mnt/.DS_Store"
d = DSStore.open(p, "r+")
icvp = d["."]["icvp"]
icvp["backgroundColorRed"] = 0.067
icvp["backgroundColorGreen"] = 0.078
icvp["backgroundColorBlue"] = 0.165
d["."]["icvp"] = icvp
d.close()
print("  icvp 背景色已改为 (0.067, 0.078, 0.165)")
PY
sync --file-system /tmp/codex_helper_fix_mnt
hdiutil detach /tmp/codex_helper_fix_mnt
rm -f "$DMG_FINAL"
hdiutil convert /tmp/codex_helper_fix_rw.dmg -format UDZO -o "$DMG_FINAL"
rm -f /tmp/codex_helper_fix_rw.dmg
echo "  后处理完成"

xattr -dr com.apple.quarantine "$DMG_FINAL" 2>/dev/null || true

echo ""
echo "═══════════════════════════════════════"
echo "  ✅ 打包完成！"
echo "  输出: ${DMG_FINAL}"
echo "  大小: $(ls -lh "$DMG_FINAL" | awk '{print $5}')"
echo "═══════════════════════════════════════"
