#!/bin/bash
# ============================================================
# 一键启用 Codex 助手（适配器模式）
# 用法: ./switch-adapter.sh [模型名]
#   默认模型: LongCat-2.0（取 codex-helper-config.json 中的 model）
# 功能:
#   1. 检查上游配置（upstream / api_key 是否已填）
#   2. 写入 config.toml：顶层 model + [model_providers.codex_helper_adapter]
#   3. 启动适配器（监听 18667，已运行则跳过）
#   4. 实测请求验证（HTTP 200 才算成功）
# ============================================================
set -u
DATA_DIR="$HOME/.codex-helper/data"
CONFIG_JSON="$DATA_DIR/codex-helper-config.json"
SRC_DIR="$(cd "$(dirname "$0")/../src" && pwd)"

echo "== 1/4 检查上游配置 =="
if [ ! -f "$CONFIG_JSON" ]; then
  echo "错误: 未找到 $CONFIG_JSON"
  echo "请先用 Codex助手 GUI 配置模型与 API Key，再运行本脚本"
  exit 1
fi
MODEL=$(python3 -c "
import json
c = json.load(open('$CONFIG_JSON'))
assert c.get('upstream'), 'upstream 为空'
assert c.get('api_key'), 'api_key 为空'
print(c.get('model') or 'LongCat-2.0')
" || true)
[ -n "$MODEL" ] || { echo "错误: 无法读取模型配置"; exit 1; }
echo "上游: $(python3 -c "import json; print(json.load(open('$CONFIG_JSON'))['upstream'])" 2>/dev/null || echo '(读取失败)')"
echo "模型: $MODEL"
echo "Key:  已配置 ✓"

echo "== 2/4 写入 config.toml =="
cd "$SRC_DIR"
python3 -c "from core import apply_codex_config; apply_codex_config('$MODEL'); print('config.toml 已指向 Codex助手 Adapter ✓')"

echo "== 3/4 启动适配器 =="
if lsof -tiTCP:18667 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "18667 已有适配器在运行，跳过启动"
else
  mkdir -p "$DATA_DIR"
  cd "$SRC_DIR"
  nohup python3 adapter.py >> "$DATA_DIR/adapter.log" 2>&1 &
  echo "适配器进程已启动 (PID $!)，日志: $DATA_DIR/adapter.log"
  sleep 2
fi
if curl -s --noproxy '*' -m 3 http://127.0.0.1:18667/health >/dev/null 2>&1; then
  echo "适配器健康 ✓"
else
  echo "警告: 适配器未就绪，请稍后检查 $DATA_DIR/adapter.log"
fi

echo "== 4/4 实测请求 =="
CODE=$(curl -s --noproxy '*' -m 60 -o /tmp/switch-adapter-test.txt -w "%{http_code}" \
  -X POST http://127.0.0.1:18667/v1/responses \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODEL\",\"input\":\"hi\",\"max_output_tokens\":5}" 2>/dev/null)
if [ "$CODE" = "200" ]; then
  echo "实测请求 HTTP 200 ✓，Codex 助手可正常使用"
else
  echo "实测请求 HTTP $CODE（可能上游暂时故障，可重试）"
  head -c 300 /tmp/switch-adapter-test.txt
  echo
fi
