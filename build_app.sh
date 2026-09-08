#!/bin/bash
# Codex助手 — 使用 PyInstaller 打包成 macOS .app
# 用法: bash build_app.sh
# 产物: dist/Codex助手.app

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ─── 查找合适的 Python ───
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    if "$c" -c "import webview" >/dev/null 2>&1; then
      PY="$c"; break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "未找到带 pywebview 的 Python，请运行: pip install pywebview"
  exit 1
fi

echo "[1/3] 使用 Python: $("$PY" --version 2>&1) ($(command -v $PY))"

# ─── 安装依赖 ───
echo "[2/3] 安装依赖..."
"$PY" -m pip install --upgrade --quiet --user --break-system-packages \
  pyinstaller tomlkit pywebview 2>/dev/null || \
"$PY" -m pip install --upgrade --quiet \
  pyinstaller tomlkit pywebview 2>/dev/null || true

# ─── 清理并打包 ───
echo "[3/3] 运行 PyInstaller..."
rm -rf build dist *.spec

# 生成图标（从 logo.svg）
ICONSET="build/icon.iconset"
rm -rf "$ICONSET"
mkdir -p "$ICONSET"

LOGO_SVG="assets/logo.svg"
RSVG_CONVERT="rsvg-convert"
if ! command -v rsvg-convert &>/dev/null; then
  TRAE_RSVG="$HOME/Library/Application Support/TRAE SOLO CN/ModularData/ai-agent/vm/tools/bin/rsvg-convert"
  [ -f "$TRAE_RSVG" ] && RSVG_CONVERT="$TRAE_RSVG"
fi

if [ -f "$LOGO_SVG" ] && [ -n "$RSVG_CONVERT" ]; then
  echo "从 logo.svg 生成图标..."
  for SIZE in 16 32 128 256 512; do
    $RSVG_CONVERT -w $SIZE -h $SIZE "$LOGO_SVG" > "$ICONSET/icon_${SIZE}x${SIZE}.png" 2>/dev/null || true
    if [ $SIZE -lt 512 ]; then
      $RSVG_CONVERT -w $((SIZE*2)) -h $((SIZE*2)) "$LOGO_SVG" > "$ICONSET/icon_${SIZE}x${SIZE}@2x.png" 2>/dev/null || true
    fi
  done
  $RSVG_CONVERT -w 1024 -h 1024 "$LOGO_SVG" > "$ICONSET/icon_512x512@2x.png" 2>/dev/null || true
  iconutil -c icns "$ICONSET" -o "assets/icon.icns" 2>/dev/null || true
  rm -rf "$ICONSET"
  echo "图标生成完成"
fi

# 运行 PyInstaller（使用本地缓存目录避免权限问题）
export PYINSTALLER_CONFIG_DIR="$SCRIPT_DIR/.pyinstaller_cache"
mkdir -p "$PYINSTALLER_CONFIG_DIR"

"$PY" -m PyInstaller \
  --clean \
  --noconfirm \
  --windowed \
  --name "Codex助手" \
  --icon "assets/icon.icns" \
  --add-data "web:web" \
  --add-data "assets/mascot-3d.png:assets" \
  --add-data "assets/brand-text.png:assets" \
  --add-data "assets/brand-text-dark.png:assets" \
  --add-data "assets/icon-1024.png:assets" \
  --hidden-import "webview" \
  --hidden-import "webview.platforms.cocoa" \
  --hidden-import "werkzeug" \
  --hidden-import "werkzeug.serving" \
  --hidden-import "tomlkit" \
  --hidden-import "tomlkit.api" \
  --hidden-import "tomlkit.container" \
  --hidden-import "tomlkit.items" \
  --hidden-import "tomlkit.parser" \
  --hidden-import "tomlkit.toml_document" \
  --hidden-import "tomlkit.toml_file" \
  --hidden-import "jinja2" \
  --hidden-import "markupsafe" \
  --hidden-import "itsdangerous" \
  --hidden-import "click" \
  --osx-bundle-identifier "com.codexhelper.app" \
  --exclude-module tkinter \
  --exclude-module matplotlib \
  --exclude-module numpy \
  --exclude-module pandas \
  --exclude-module PIL \
  --exclude-module scipy \
  --exclude-module wx \
  --exclude-module PyQt5 \
  --exclude-module PyQt6 \
  --exclude-module PySide2 \
  --exclude-module PySide6 \
  "src/web_launcher.py"

# 清理
rm -rf "$PYINSTALLER_CONFIG_DIR"
rm -f *.spec

APP="dist/Codex助手.app"
if [ -d "$APP" ]; then
  xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
  echo ""
  echo "✅ 打包完成: $APP"
  echo "双击运行，或拖到 /Applications"
else
  echo "❌ 打包失败"
  exit 1
fi
