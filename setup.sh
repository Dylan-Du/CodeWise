#!/bin/bash
# Codex助手 — macOS 权限配置脚本
# 运行此脚本完成一次性授权，之后不再需要重复操作
#
# 使用方法：bash setup.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}  Codex助手 — macOS 权限配置${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# 检查当前用户是否有权限写入 ~/.codex/
CODex_DIR="$HOME/.codex"
TEST_FILE="$CODex_DIR/.write_test_$$"

check_permission() {
    # 尝试创建测试文件
    if touch "$TEST_FILE" 2>/dev/null; then
        rm -f "$TEST_FILE"
        return 0
    fi
    return 1
}

if check_permission; then
    echo -e "${GREEN}✓ 权限检查通过，无需额外配置${NC}"
    echo ""
    read -p "是否仍要打开系统设置确认？[y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}配置完成！${NC}"
        exit 0
    fi
fi

echo -e "${YELLOW}⚠ 需要授予「完全磁盘访问权限」才能写入配置文件${NC}"
echo ""
echo "macOS 保护 ~/.codex/ 目录，需要您手动授权一次。"
echo "授权后永久有效，无需重复操作。"
echo ""

# 检测当前运行的终端程序
detect_terminal() {
    # 获取父进程名称
    local parent_pid=$PPID
    local terminal_name=""
    
    # 尝试检测终端类型
    if [[ -n "$TERM_PROGRAM" ]]; then
        terminal_name="$TERM_PROGRAM"
    elif [[ -n "$ITERM_SESSION_ID" ]]; then
        terminal_name="iTerm2"
    elif [[ -n "$TERMINAL_EMULATOR" ]]; then
        terminal_name="$TERMINAL_EMULATOR"
    else
        terminal_name="Terminal"
    fi
    
    echo "$terminal_name"
}

TERMINAL_APP=$(detect_terminal)
echo -e "检测到终端: ${BLUE}$TERMINAL_APP${NC}"
echo ""

echo -e "${YELLOW}即将打开系统设置，请按照以下步骤操作：${NC}"
echo ""
echo "1. 点击左下角 🔒 锁图标解锁"
echo "2. 点击 + 号添加应用"
echo "3. 找到并添加: $TERMINAL_APP"
echo "4. 确保开关已打开"
echo "5. 关闭系统设置窗口"
echo ""
echo -e "${BLUE}按回车键打开系统设置...${NC}"
read

# 打开系统设置的完全磁盘访问权限页面
open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"

echo -e "${YELLOW}请在系统设置中完成授权，然后返回此处${NC}"
echo ""
echo -e "授权完成后，按 ${GREEN}回车键${NC} 继续..."

MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    read -t 1 -n 1 -r 2>/dev/null || true
    
    if check_permission; then
        echo ""
        echo -e "${GREEN}================================${NC}"
        echo -e "${GREEN}  ✓ 权限配置成功！${NC}"
        echo -e "${GREEN}================================${NC}"
        echo ""
        echo "现在可以正常使用 Codex助手 了。"
        echo ""
        echo "启动命令："
        echo "  cd $(dirname "$0")/src && python3 web_launcher.py"
        echo ""
        
        # 询问是否立即启动
        read -p "是否立即启动 Codex助手？[Y/n] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            echo -e "${BLUE}正在启动...${NC}"
            cd "$(dirname "$0")/src" && python3 web_launcher.py
        fi
        exit 0
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
done

echo ""
echo -e "${RED}超时：未检测到权限变更${NC}"
echo ""
echo "请确认您已经："
echo "1. 解锁了系统设置（点击锁图标）"
echo "2. 添加了终端应用到允许列表"
echo "3. 打开了开关"
echo ""
echo "然后重新运行此脚本：bash setup.sh"
exit 1
