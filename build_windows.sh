#!/bin/bash
# Codex助手 - Windows EXE 打包脚本
# 在 Windows 机器上运行此脚本生成 exe 安装包
# 用法: 在 Windows 上安装 Python 3.11+ 后运行 build_windows.bat
#
# 前置条件:
#   1. Windows 10/11
#   2. Python 3.11+ (从 https://python.org 下载)
#   3. NSIS (从 https://nsis.sourceforge.io 下载，用于生成安装包)
#
# 或者直接运行: build_windows.bat

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Codex助手 Windows 打包 ==="

# 安装依赖
echo "[1/4] 安装 Python 依赖..."
pip install --upgrade pip
pip install pyinstaller pywebview tomlkit certifi werkzeug jinja2 markupsafe itsdangerous click
pip install pythonnet  # Windows 上 pywebview 需要

# 生成 ICO 图标（从 SVG）
echo "[2/4] 准备图标..."
# 如果没有 ico 文件，用 PNG 转换
if [ ! -f "assets/icon.ico" ]; then
  if command -v convert >/dev/null 2>&1; then
    convert -resize 256x256 assets/logo.svg assets/icon.ico 2>/dev/null || true
  fi
fi

# PyInstaller 打包
echo "[3/4] 运行 PyInstaller..."
rm -rf build dist/Codex助手

python -m PyInstaller \
  --clean \
  --noconfirm \
  --windowed \
  --name "Codex助手" \
  --icon "assets/icon.ico" \
  --add-data "web;web" \
  --add-data "assets/mascot-3d.png;assets" \
  --add-data "assets/brand-text.png;assets" \
  --add-data "assets/brand-text-dark.png;assets" \
  --add-data "assets/icon-1024.png;assets" \
  --add-data "assets/codex-model-template.json;assets" \
  --add-data "assets/dream-skin;assets/dream-skin" \
  --collect-all tomlkit \
  --collect-all werkzeug \
  --collect-all jinja2 \
  --collect-all certifi \
  --hidden-import "certifi" \
  --hidden-import "webview" \
  --hidden-import "webview.platforms.winforms" \
  --hidden-import "clr_loader" \
  --hidden-import "werkzeug" \
  --hidden-import "werkzeug.serving" \
  --hidden-import "jinja2" \
  --hidden-import "markupsafe" \
  --hidden-import "itsdangerous" \
  --hidden-import "click" \
  --exclude-module tkinter \
  --exclude-module matplotlib \
  --exclude-module numpy \
  --exclude-module pandas \
  --exclude-module PIL \
  --exclude-module scipy \
  "src/web_launcher.py"

# 生成 NSIS 安装脚本
echo "[4/4] 生成 NSIS 安装脚本..."
cat > dist/installer.nsi << 'NSISEOF'
!define APP_NAME "Codex助手"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "CodexHelper"
!define APP_EXE "Codex助手.exe"
!define APP_REGKEY "Software\CodexHelper\Codex助手"

Name "${APP_NAME}"
OutFile "Codex助手-Setup.exe"
InstallDir "$LOCALAPPDATA\${APP_NAME}"
RequestExecutionLevel user
Unicode true

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  
  ; 复制所有文件
  File /r "Codex助手\*.*"
  
  ; 创建快捷方式
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  
  ; 写入注册表（卸载信息）
  WriteRegStr HKCU "${APP_REGKEY}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher" "${APP_PUBLISHER}"
  
  ; 创建卸载程序
  WriteUninstaller "$INSTDIR\uninstall.exe"
  
  SectionEnd
  
Section "Uninstall"
  ; 删除文件
  RMDir /r "$INSTDIR"
  RMDir /r "$SMPROGRAMS\${APP_NAME}"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  
  ; 清除注册表
  DeleteRegKey HKCU "${APP_REGKEY}"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
SectionEnd
NSISEOF

echo ""
echo "✅ PyInstaller 打包完成: dist/Codex助手/"
echo ""
echo "要生成安装包，请安装 NSIS 后运行:"
echo "  cd dist && makensis installer.nsi"
echo "  产物: dist/Codex助手-Setup.exe"
