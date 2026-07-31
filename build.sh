#!/usr/bin/env bash
# 一键打包成 macOS .app
# 用法: ./build.sh
# 产物: dist/Codex助手.app

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PY=""
# 优先尝试 python.org 的绝对路径,不依赖 PATH
for c in /usr/local/bin/python3.13 \
         /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
         python3.13 python3.12 python3.11 python3; do
  if [ -x "$c" ] 2>/dev/null || command -v "$c" >/dev/null 2>&1; then
    if "$c" -c "import tkinter" >/dev/null 2>&1; then
      PY="$c"; break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "错误:找不到带 tkinter 的 Python。请先运行 brew install python-tk@3.13" >&2
  exit 1
fi

echo "[1/4] 使用 Python: $($PY --version) ($(command -v $PY))"

echo "[2/4] 安装打包依赖 (pyinstaller / tomlkit / pywebview)"
"$PY" -m pip install --upgrade --quiet --user --break-system-packages \
  pyinstaller tomlkit pywebview

echo "[3/4] 清理旧 build/dist"
rm -rf build dist

echo "[4/4] 运行 PyInstaller"
"$PY" -m PyInstaller --clean --noconfirm CodexSwitch.spec

APP="dist/Codex助手.app"
if [ -d "$APP" ]; then
  xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
  echo ""
  echo "✅ 打包完成: $APP"
  echo "把它拖到 /Applications,或直接双击运行。"
else
  echo "❌ 打包失败,没看到 $APP"
  exit 1
fi
