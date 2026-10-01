#!/bin/bash
# AI日报 — 每天早上7点自动执行
# 搜索全球AI新闻+赚钱情报 → 发送到飞书+Telegram

set -Eeuo pipefail
umask 077
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
# Parse a small config whitelist as literal values; preserve the process environment.
if [ -f "$ENV_FILE" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    case "$key" in
      TELEGRAM_DAILY_BOT_TOKEN|TELEGRAM_DAILY_CHAT_ID|FEISHU_DAILY_CHAT_ID|CLAUDE_CLI_BIN|LARK_CLI_BIN|PYTHON_BIN|DAILY_REPORT_DIR|DAILY_DESKTOP_DIR)
        if [[ "$value" == \"*\" || "$value" == \'*\' ]]; then value="${value:1:${#value}-2}"; fi
        if [ -z "${!key+x}" ]; then export "$key=$value"; fi
        ;;
    esac
  done < "$ENV_FILE"
fi

FEISHU_CHAT_ID="${FEISHU_DAILY_CHAT_ID:-oc_86a0033ce2a2c0820a2137217aee9416}"
TELEGRAM_CHAT_ID="${TELEGRAM_DAILY_CHAT_ID:-8296218023}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_DAILY_BOT_TOKEN:?缺少 TELEGRAM_DAILY_BOT_TOKEN}"
CLAUDE_CLI_BIN="${CLAUDE_CLI_BIN:-claude}"
LARK_CLI_BIN="${LARK_CLI_BIN:-lark-cli}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REPORT_DIR="${DAILY_REPORT_DIR:-$ROOT_DIR/daily-reports}"
TODAY=$(date +%Y-%m-%d)
CURRENT_YEAR=$(date +%Y)
CURRENT_MONTH=$(date +%Y年%m月)
CURRENT_YEAR_MONTH=$(date +%Y-%m)
mkdir -p "$REPORT_DIR"
FINAL_REPORT_FILE="$REPORT_DIR/$TODAY.md"
REPORT_FILE=$(mktemp "$REPORT_DIR/.$TODAY-candidate.XXXXXX")
PARTS_DIR=$(mktemp -d "$REPORT_DIR/.telegram-parts.XXXXXX")
trap 'rm -f "$REPORT_FILE"; rm -rf "$PARTS_DIR"' EXIT

log() { echo "[$(date '+%H:%M:%S')] $1"; }

check_api_response() {
  "$PYTHON_BIN" -c 'import json,sys
result=json.load(sys.stdin)
success=isinstance(result,dict) and (result.get("ok") is True or (type(result.get("code")) is int and result["code"] == 0))
if isinstance(result,dict):
    success=success and ("ok" not in result or result["ok"] is True) and ("code" not in result or (type(result["code"]) is int and result["code"] == 0))
sys.exit(0 if success else 1)'
}

log "AI日报开始生成..."

# Step 1: 生成日报
PROMPT=$(cat <<EOF
你是AI行业分析师，为AI创业者写每日情报。今天是 $TODAY。

请执行以下搜索（至少6个查询）：
- "AI news $TODAY"
- "AI company revenue profit ${CURRENT_YEAR}"
- "AI startup raised funding ${CURRENT_YEAR_MONTH}"
- "AI SaaS indie hacker revenue ${CURRENT_YEAR}"
- "AI赚钱 案例 ${CURRENT_MONTH}"
- "AI创业 OPC 一人公司 营收 ${CURRENT_YEAR}"

然后将结果写入 $REPORT_FILE，格式如下：

# AI日报 · $TODAY

## 今日最重要的事
（3-5条。每条要有具体公司名、人名、数字，说清楚发生了什么、为什么重要。不要空洞概括。）

## 今日AI赚钱情报
（这是最重要的板块。搜索谁在用AI赚钱、赚多少、怎么赚的。至少3条。每条说清楚：什么人/公司，用什么AI做什么业务，赚了多少。数字越具体越好。搜不到今天的可以放近一周的。）

## 值得关注的信号
（2-3条不算大新闻但值得留意的小趋势、工具更新、政策动向）

## 一句话总结
（一句话概括今天AI世界最值得记住的事）

---
*AI日报 · @年赚千万真实记录 · $TODAY*

要求：说人话，不用"赋能""生态"等废话。每条必须有具体数字。宁可少写高质量的不要凑数。每条附可核验来源链接与报道日期。只写入文件。
EOF
)

printf '%s\n' "$PROMPT" | "$CLAUDE_CLI_BIN" -p --allowedTools "WebSearch,Write" > /dev/null 2>&1

# 检查是否生成成功
if [ ! -s "$REPORT_FILE" ]; then
  log "ERROR: 日报文件未生成"
  exit 1
fi

mv "$REPORT_FILE" "$FINAL_REPORT_FILE"
REPORT_FILE="$FINAL_REPORT_FILE"
# Keep the published report when the temporary cleanup runs.
trap 'rm -rf "$PARTS_DIR"' EXIT
log "日报已生成: $REPORT_FILE"
REPORT_CONTENT=$(cat "$REPORT_FILE")

# Step 2: 发送到飞书
log "发送到飞书..."
if "$LARK_CLI_BIN" im +messages-send \
  --chat-id "$FEISHU_CHAT_ID" \
  --markdown "$REPORT_CONTENT" --format json 2>/dev/null | check_api_response; then
  log "飞书发送成功"
else
  log "飞书发送失败"
  exit 1
fi

# Step 3: 发送到 Telegram（直接调用 Bot API，不依赖 MCP）
log "发送到 Telegram..."

# Split by actual message size; headings alone cannot bound long sections.
"$PYTHON_BIN" - "$REPORT_FILE" "$PARTS_DIR" <<'PYTHON'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8")
chunk, units, index = [], 0, 0
for character in text:
    count = len(character.encode("utf-16-le")) // 2
    if units + count > 4000:
        Path(sys.argv[2], f"{index:05d}.txt").write_text("".join(chunk), encoding="utf-8")
        chunk, units, index = [], 0, index + 1
    chunk.append(character)
    units += count
if chunk:
    Path(sys.argv[2], f"{index:05d}.txt").write_text("".join(chunk), encoding="utf-8")
PYTHON

for part in "$PARTS_DIR"/*.txt; do
  if curl --fail --silent --show-error --max-time 35 \
      "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" \
      --data-urlencode "text@$part" 2>/dev/null | check_api_response; then
    log "Telegram分段发送成功"
  else
    log "Telegram发送失败"
    exit 1
  fi
done

# Step 4: 生成社交媒体分享长图
log "生成分享长图..."
SHARE_HTML="$REPORT_DIR/$TODAY-share.html"
SHARE_PNG="$REPORT_DIR/$TODAY-share.png"

"$PYTHON_BIN" "$ROOT_DIR/scripts/daily-to-image.py" "$REPORT_FILE" "$SHARE_HTML" > /dev/null 2>&1

if [ -f "$SHARE_HTML" ]; then
  if playwright screenshot --viewport-size="1080,1920" --full-page \
    "file://$SHARE_HTML" "$SHARE_PNG" > /dev/null 2>&1 && [ -s "$SHARE_PNG" ]; then
    # 同时复制一份到桌面，方便随时发朋友圈
    if [ -n "${DAILY_DESKTOP_DIR:-}" ]; then
      mkdir -p "$DAILY_DESKTOP_DIR"
      cp "$SHARE_PNG" "$DAILY_DESKTOP_DIR/AI日报-$TODAY.png"
    fi
    log "分享长图已生成: $SHARE_PNG"

    # 把图片也发到 Telegram
    curl --fail --silent --show-error --max-time 35 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendPhoto" \
      -F chat_id="$TELEGRAM_CHAT_ID" \
      -F photo=@"$SHARE_PNG" \
      -F caption="AI日报 $TODAY · 长图版 · 可直接转发朋友圈" 2>/dev/null | check_api_response
    log "分享长图已发送到 Telegram"

    # 把图片也发到飞书
    "$LARK_CLI_BIN" im +messages-send \
      --chat-id "$FEISHU_CHAT_ID" \
      --image "$SHARE_PNG" --format json 2>/dev/null | check_api_response
    log "分享长图已发送到飞书"
  else
    log "WARNING: 长图截图失败"
  fi
else
  log "WARNING: 长图HTML生成失败"
fi

log "AI日报全部完成!"
