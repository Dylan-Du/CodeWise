@echo off
chcp 65001 >nul 2>&1
title Codex助手 - Windows 打包脚本

echo ========================================
echo   Codex助手 Windows EXE 打包脚本
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请从 https://python.org 下载安装
    pause
    exit /b 1
)

echo [1/4] 安装 Python 依赖...
pip install --upgrade pip pyinstaller pywebview tomlkit werkzeug jinja2 markupsafe itsdangerous click pythonnet
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

echo [2/4] 清理旧文件...
if exist build rmdir /s /q build
if exist dist\Codex助手 rmdir /s /q dist\Codex助手

echo [3/4] 运行 PyInstaller 打包...
python -m PyInstaller ^
  --clean --noconfirm --windowed ^
  --name "Codex助手" ^
  --icon "assets\icon.ico" ^
  --add-data "web;web" ^
  --add-data "assets\apinest-logo.png;assets" ^
  --add-data "assets\mascot-3d.png;assets" ^
  --add-data "assets\brand-text.png;assets" ^
  --add-data "assets\brand-text-dark.png;assets" ^
  --hidden-import "webview" ^
  --hidden-import "webview.platforms.winforms" ^
  --hidden-import "clr_loader" ^
  --hidden-import "werkzeug" ^
  --hidden-import "werkzeug.serving" ^
  --hidden-import "tomlkit" ^
  --hidden-import "tomlkit.api" ^
  --hidden-import "tomlkit.container" ^
  --hidden-import "tomlkit.items" ^
  --hidden-import "tomlkit.parser" ^
  --hidden-import "tomlkit.toml_document" ^
  --hidden-import "tomlkit.toml_file" ^
  --hidden-import "jinja2" ^
  --hidden-import "markupsafe" ^
  --hidden-import "itsdangerous" ^
  --hidden-import "click" ^
  --exclude-module tkinter ^
  --exclude-module matplotlib ^
  --exclude-module numpy ^
  --exclude-module pandas ^
  --exclude-module PIL ^
  --exclude-module scipy ^
  "src\web_launcher.py"

if errorlevel 1 (
    echo [错误] PyInstaller 打包失败
    pause
    exit /b 1
)

echo [4/4] 生成 NSIS 安装脚本...
(
echo !define APP_NAME "Codex助手"
echo !define APP_VERSION "1.0.0"
echo !define APP_PUBLISHER "CodexHelper"
echo !define APP_EXE "Codex助手.exe"
echo Name "${APP_NAME}"
echo OutFile "Codex助手-Setup.exe"
echo InstallDir "$LOCALAPPDATA\${APP_NAME}"
echo RequestExecutionLevel user
echo Unicode true
echo Page directory
echo Page instfiles
echo UninstPage uninstConfirm
echo UninstPage instfiles
echo Section "Install"
echo   SetOutPath "$INSTDIR"
echo   File /r "Codex助手\*.*"
echo   CreateDirectory "$SMPROGRAMS\${APP_NAME}"
echo   CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
echo   CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
echo   WriteRegStr HKCU "Software\CodexHelper\Codex助手" "InstallDir" "$INSTDIR"
echo   WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_NAME}"
echo   WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" '"$INSTDIR\uninstall.exe"'
echo   WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
echo   WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher" "${APP_PUBLISHER}"
echo   WriteUninstaller "$INSTDIR\uninstall.exe"
echo SectionEnd
echo Section "Uninstall"
echo   RMDir /r "$INSTDIR"
echo   RMDir /r "$SMPROGRAMS\${APP_NAME}"
echo   Delete "$DESKTOP\${APP_NAME}.lnk"
echo   DeleteRegKey HKCU "Software\CodexHelper\Codex助手"
echo   DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
echo SectionEnd
) > dist\installer.nsi

echo.
echo ========================================
echo   ✅ 打包完成！
echo ========================================
echo.
echo   产物目录: dist\Codex助手\
echo   主程序:   dist\Codex助手\Codex助手.exe
echo.
echo   要生成安装包（.exe installer），请：
echo   1. 安装 NSIS: https://nsis.sourceforge.io
echo   2. 运行: cd dist ^&^& makensis installer.nsi
echo   3. 产物: dist\Codex助手-Setup.exe
echo.
pause
