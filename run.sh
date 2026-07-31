#!/usr/bin/env bash
# 一键启动 Codex助手 (pywebview + HTML UI)
# 用法: ./run.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 清除可能导致 Python 沙箱化的环境变量
unset PYTHONHOME PYTHONPATH 2>/dev/null || true

PY=""
# 尝试找到可用的 Python（优先使用系统 Python）
for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    PY="$c"
    break
  fi
done

if [ -z "$PY" ]; then
  echo "错误: 找不到 Python3" >&2
  exit 1
fi

echo "使用 Python: $($PY --version)"

# 检查依赖
need_install=0
for mod in webview tomlkit; do
  "$PY" -c "import $mod" >/dev/null 2>&1 || need_install=1
done

if [ "$need_install" = "1" ]; then
  echo "安装依赖..."
  "$PY" -m pip install --user --break-system-packages pywebview tomlkit 2>/dev/null \
    || "$PY" -m pip install --user pywebview tomlkit
fi

# 启动
cd "$SCRIPT_DIR/src"
exec "$PY" web_launcher.py
