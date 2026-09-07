#!/bin/bash
# Codex助手 - Windows Portable 包构建脚本
# 使用 Python embeddable + pip 来创建 Windows 可运行的 portable 包
# 产物: dist/Codex助手-Windows-portable.zip

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== 构建 Codex助手 Windows Portable 包 ==="

# 1. 准备目录
BUILD_DIR="dist/win-portable"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/python"
mkdir -p "$BUILD_DIR/assets"
mkdir -p "$BUILD_DIR/web"

# 2. 下载并解压 Python embeddable
 echo "[1/5] 准备 Python embeddable..."
PYTHON_EMBED_VERSION="3.10.11"
PYTHON_EMBED_URL="https://www.python.org/ftp/python/${PYTHON_EMBED_VERSION}/python-${PYTHON_EMBED_VERSION}-embed-amd64.zip"
PYTHON_EMBED_ZIP="/tmp/python-${PYTHON_EMBED_VERSION}-embed-amd64.zip"
if [ ! -f "$PYTHON_EMBED_ZIP" ]; then
  echo "下载 Python ${PYTHON_EMBED_VERSION} Windows embeddable 包..."
  curl -fL --retry 2 -o "$PYTHON_EMBED_ZIP" "$PYTHON_EMBED_URL"
fi
unzip -q -o "$PYTHON_EMBED_ZIP" -d "$BUILD_DIR/python/"

# 3. 启用 pip (取消 site-packages 注释)
echo "[2/5] 配置 Python..."
# 修改 pth 文件启用 site-packages
PTH_FILE=$(find "$BUILD_DIR/python" -name "python*._pth" | head -1)
if [ -n "$PTH_FILE" ]; then
  # 取消 import site 注释
  sed -i '' 's/#import site/import site/' "$PTH_FILE" 2>/dev/null || \
  sed -i 's/#import site/import site/' "$PTH_FILE"
  echo "已启用 site-packages: $PTH_FILE"
fi

# 4. 下载 get-pip.py 并安装依赖
echo "[3/5] 下载 get-pip.py..."
curl -L -o "$BUILD_DIR/python/get-pip.py" "https://bootstrap.pypa.io/get-pip.py" 2>/dev/null

# 5. 复制应用代码
echo "[4/5] 复制应用代码..."
cp -R web/* "$BUILD_DIR/web/"
cp assets/apinest-logo.png "$BUILD_DIR/assets/" 2>/dev/null || true
cp assets/mascot-3d.png "$BUILD_DIR/assets/" 2>/dev/null || true
cp assets/brand-text.png "$BUILD_DIR/assets/" 2>/dev/null || true
cp assets/brand-text-dark.png "$BUILD_DIR/assets/" 2>/dev/null || true
cp -R src "$BUILD_DIR/src"

# 6. 创建启动脚本
echo "[5/5] 创建启动脚本..."

# install_deps.bat - 首次运行安装依赖
cat > "$BUILD_DIR/install_deps.bat" << 'BATEOF'
@echo off
chcp 65001 >nul 2>&1
echo 正在安装依赖包，请稍候...
cd /d "%~dp0\python"
python.exe get-pip.py --quiet 2>nul
python.exe -m pip install --quiet pywebview tomlkit certifi werkzeug jinja2 markupsafe itsdangerous click pythonnet 2>nul
if errorlevel 1 (
    echo 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)
echo 依赖安装完成！
echo.
echo 请双击 Codex助手.bat 启动应用
pause
BATEOF

# Codex助手.bat - 主启动脚本
cat > "$BUILD_DIR/Codex助手.bat" << 'BATEOF'
@echo off
chcp 65001 >nul 2>&1
title Codex助手

REM 检查是否已安装依赖
if not exist "%~dp0\python\Lib\site-packages\pywebview" (
    echo 首次运行，需要安装依赖...
    call "%~dp0\install_deps.bat"
)

REM 启动应用
cd /d "%~dp0"
"%~dp0\python\python.exe" "%~dp0\src\web_launcher.py"
if errorlevel 1 (
    echo.
    echo 应用启动失败，请确保已运行 install_deps.bat 安装依赖
    pause
)
BATEOF

# README.txt
cat > "$BUILD_DIR/README.txt" << 'READMEEOF'
Codex助手 Windows Portable 版
================================

首次使用：
1. 双击 install_deps.bat 安装依赖（需要联网，约1分钟）
2. 双击 Codex助手.bat 启动应用

后续使用：
直接双击 Codex助手.bat 即可

注意：需要 Windows 10 或以上版本
READMEEOF

# 7. 打包为 ZIP
echo "打包为 ZIP..."
cd dist
zip -r -q "Codex助手-Windows-portable.zip" "win-portable/"
cd ..

# 清理
rm -rf "$BUILD_DIR"

SIZE=$(du -h "dist/Codex助手-Windows-portable.zip" | cut -f1)
echo ""
echo "✅ Windows Portable 包构建完成: dist/Codex助手-Windows-portable.zip ($SIZE)"
echo ""
echo "使用说明："
echo "  1. 将 ZIP 文件复制到 Windows 电脑"
echo "  2. 解压到任意目录"
echo "  3. 双击 install_deps.bat 安装依赖（首次）"
echo "  4. 双击 Codex助手.bat 启动"
