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
VERSION="1.0.0"
DIST_DIR="dist"
APP_DIR="${DIST_DIR}/CodexHelper.app"
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
  --name "CodexHelper" \
  --icon "assets/icon.icns" \
  --add-data "web:web" \
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

# ─── 创建 DMG ───
echo ""
echo "创建 DMG..."
STAGING="$SCRIPT_DIR/.dmg_staging"
rm -rf "$STAGING"
mkdir -p "$STAGING"
cp -R "$APP_DIR" "$STAGING/"
ln -sf /Applications "$STAGING/Applications"

rm -f "$DMG_FINAL"
hdiutil create -srcfolder "$STAGING" -volname "$APP_NAME" -fs HFS+ -format UDZO -o "$DMG_FINAL" 2>/dev/null
rm -rf "$STAGING"
xattr -dr com.apple.quarantine "$DMG_FINAL" 2>/dev/null || true

echo ""
echo "═══════════════════════════════════════"
echo "  ✅ 打包完成！"
echo "  输出: ${DMG_FINAL}"
echo "  大小: $(ls -lh "$DMG_FINAL" | awk '{print $5}')"
echo "═══════════════════════════════════════"
