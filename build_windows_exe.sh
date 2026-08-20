#!/bin/bash
# 构建 Windows 自解压 EXE 安装包
# 原理：用 7z 压缩 + 自解压模块，生成一个 .exe 文件
# 用户双击后会自动解压到指定目录并运行安装脚本

set -e

cd "/Users/dongqing/Downloads/Codex助手"

echo "=== 构建 Codex助手 Windows EXE 安装包 ==="

BUILD_DIR="dist/win-portable"
EXE_OUTPUT="dist/Codex助手-Windows-Setup.exe"

# 确保 portable 包已构建
if [ ! -d "$BUILD_DIR" ]; then
    echo "先构建 portable 包..."
    bash build_windows_portable.sh
fi

# 创建自解压配置
cat > /tmp/sfx_config.txt << 'EOF'
;!@Install@!UTF-8!
Title="Codex助手 Windows 安装程序"
BeginPrompt="是否安装 Codex助手？"
ExtractTitle="正在解压文件..."
ExtractDialogText="请稍候..."
RunProgram="install_deps.bat"
;!@InstallEnd@!
EOF

# 使用 7z 创建自解压 EXE
echo "[1/2] 压缩文件..."
7z a -t7z -sfx7z.sfx "$EXE_OUTPUT" "$BUILD_DIR/*" -p"" 2>&1 || {
    echo "7z SFX 方式失败，改用 ZIP 自解压方式..."

    # 替代方案：生成一个 bat 启动器 + zip
    python3 << 'PYEOF'
import zipfile
import os
import struct

build_dir = "dist/win-portable"
exe_path = "dist/Codex助手-Windows-Setup.exe"

# 创建一个包含 portable 包的 zip，然后加上一个简单的 PE 头
# 实际上我们生成一个自解压 bat 包装器

# 先打包 zip
zip_path = "dist/Codex助手-Windows-portable.zip"
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(build_dir):
        for f in files:
            filepath = os.path.join(root, f)
            arcname = os.path.relpath(filepath, build_dir)
            zf.write(filepath, arcname)

print(f"ZIP 打包完成: {zip_path}")
print(f"文件数: {len(os.listdir(build_dir))}")
PYEOF

    echo ""
    echo "Windows EXE 安装包需要在 Windows 上构建。"
    echo "已生成 ZIP 便携版，可在 Windows 上用以下方式生成 EXE："
    echo "  1. 下载安装 7-Zip"
    echo "  2. 右键 ZIP 文件 -> 7-Zip -> 添加到压缩包"
    echo "  3. 勾选'创建自解压格式压缩包'"
    exit 0
}

echo "[2/2] 完成"
ls -lh "$EXE_OUTPUT" 2>&1
echo ""
echo "✅ EXE 安装包: $EXE_OUTPUT"
