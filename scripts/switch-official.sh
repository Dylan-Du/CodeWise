#!/bin/bash
# ============================================================
# 一键切回 OpenAI 官方模式
# 用法: ./switch-official.sh
# 功能:
#   1. 清理监听 18667 的残留适配器进程（防止历史对话串误连报错）
#   2. 还原 config.toml：删除 Codex助手 写入的顶层字段
#   3. 保留 [model_providers.codex_helper_adapter] 段（历史对话串恢复所需）
# 切回后: 新对话走 OpenAI 官方模型
# ============================================================
set -u
SRC_DIR="$(cd "$(dirname "$0")/../src" && pwd)"

echo "== 1/3 清理残留适配器进程（18667） =="
PIDS=$(lsof -tiTCP:18667 -sTCP:LISTEN 2>/dev/null || true)
if [ -n "${PIDS:-}" ]; then
  echo "发现残留进程: ${PIDS}，正在终止..."
  kill $PIDS 2>/dev/null
  sleep 1
fi
if lsof -tiTCP:18667 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "警告: 18667 仍在监听，请手动检查"
else
  echo "18667 已释放 ✓"
fi

echo "== 2/3 还原 config.toml =="
cd "$SRC_DIR"
python3 -c "from core import restore_openai_config; print(restore_openai_config())"

echo "== 3/3 验证 =="
python3 - <<'EOF'
import tomlkit
from pathlib import Path
p = Path.home() / ".codex" / "config.toml"
doc = tomlkit.parse(p.read_text(encoding="utf-8"))
top_keys = ["model", "model_provider", "model_catalog_json",
            "forced_login_method", "preferred_auth_method",
            "disable_response_storage"]
left = [k for k in top_keys if k in doc]
providers = doc.get("model_providers") or {}
adapter_block = providers.get("codex_helper_adapter")
print("顶层残留字段:", left if left else "无 ✓")
print("provider 段保留:", "是 ✓" if adapter_block is not None else "否(异常)")
EOF

echo "== 完成：新对话将走 OpenAI 官方 =="
