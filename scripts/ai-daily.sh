#!/bin/bash
# AI日报 — 每天早上7点自动执行
# 搜索全球AI新闻+赚钱情报 → 发送到飞书+Telegram

FEISHU_CHAT_ID="oc_86a0033ce2a2c0820a2137217aee9416"
TELEGRAM_CHAT_ID="8296218023"
TELEGRAM_BOT_TOKEN="8795715897:AAHO_wJq_EuFHIDerWml8MV05duQn7e0rB0"
REPORT_DIR="/Users/gzw/earn10m/daily-reports"
TODAY=$(date +%Y-%m-%d)
REPORT_FILE="$REPORT_DIR/$TODAY.md"

mkdir -p "$REPORT_DIR"

log() { echo "[$(date '+%H:%M:%S')] $1"; }

log "AI日报开始生成..."

# Step 1: 生成日报
PROMPT=$(cat <<EOF
你是AI行业分析师，为AI创业者写每日情报。今天是 $TODAY。

请执行以下搜索（至少6个查询）：
- "AI news $TODAY"
- "AI company revenue profit 2026"
- "AI startup raised funding April 2026"
- "AI SaaS indie hacker revenue 2026"
- "AI赚钱 案例 2026年4月"
- "AI创业 OPC 一人公司 营收 2026"

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

要求：说人话，不用"赋能""生态"等废话。每条必须有具体数字。宁可少写高质量的不要凑数。只写入文件。
EOF
)

echo "$PROMPT" | /Users/gzw/.local/bin/claude -p --allowedTools "WebSearch,Write" > /dev/null 2>&1

# 检查是否生成成功
if [ ! -f "$REPORT_FILE" ]; then
  log "ERROR: 日报文件未生成"
  exit 1
fi

log "日报已生成: $REPORT_FILE"
REPORT_CONTENT=$(cat "$REPORT_FILE")

# Step 2: 发送到飞书
log "发送到飞书..."
lark-cli im +messages-send \
  --chat-id "$FEISHU_CHAT_ID" \
  --markdown "$REPORT_CONTENT" > /dev/null 2>&1

if [ $? -eq 0 ]; then
  log "飞书发送成功"
else
  log "飞书发送失败"
fi

# Step 3: 发送到 Telegram（直接调用 Bot API，不依赖 MCP）
log "发送到 Telegram..."

# Telegram 单条消息限制4096字符，超长需要分段发送
CONTENT_LENGTH=${#REPORT_CONTENT}
if [ "$CONTENT_LENGTH" -le 4000 ]; then
  curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="$TELEGRAM_CHAT_ID" \
    -d text="$REPORT_CONTENT" \
    -d parse_mode="" > /dev/null 2>&1
else
  # 分段发送：按 ## 标题拆分
  PART1=$(echo "$REPORT_CONTENT" | sed -n '1,/^## 今日AI赚钱情报/p' | head -n -1)
  PART2=$(echo "$REPORT_CONTENT" | sed -n '/^## 今日AI赚钱情报/,/^## 值得关注的信号/p' | head -n -1)
  PART3=$(echo "$REPORT_CONTENT" | sed -n '/^## 值得关注的信号/,$p')

  curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="$TELEGRAM_CHAT_ID" \
    -d text="$PART1" > /dev/null 2>&1

  curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="$TELEGRAM_CHAT_ID" \
    -d text="$PART2" > /dev/null 2>&1

  curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="$TELEGRAM_CHAT_ID" \
    -d text="$PART3" > /dev/null 2>&1
fi

if [ $? -eq 0 ]; then
  log "Telegram发送成功"
else
  log "Telegram发送失败"
fi

# Step 4: 生成社交媒体分享长图
log "生成分享长图..."
SHARE_HTML="$REPORT_DIR/$TODAY-share.html"
SHARE_PNG="$REPORT_DIR/$TODAY-share.png"

python3 /Users/gzw/earn10m/scripts/daily-to-image.py "$REPORT_FILE" "$SHARE_HTML" > /dev/null 2>&1

if [ -f "$SHARE_HTML" ]; then
  playwright screenshot --viewport-size="1080,1920" --full-page \
    "file://$SHARE_HTML" "$SHARE_PNG" > /dev/null 2>&1

  if [ -f "$SHARE_PNG" ]; then
    # 同时复制一份到桌面，方便随时发朋友圈
    cp "$SHARE_PNG" "/Users/gzw/Desktop/AI日报-$TODAY.png"
    log "分享长图已生成: 桌面/AI日报-$TODAY.png"

    # 把图片也发到 Telegram
    curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendPhoto" \
      -F chat_id="$TELEGRAM_CHAT_ID" \
      -F photo=@"$SHARE_PNG" \
      -F caption="AI日报 $TODAY · 长图版 · 可直接转发朋友圈" > /dev/null 2>&1
    log "分享长图已发送到 Telegram"

    # 把图片也发到飞书
    lark-cli im +messages-send \
      --chat-id "$FEISHU_CHAT_ID" \
      --image "$SHARE_PNG" > /dev/null 2>&1
    log "分享长图已发送到飞书"
  else
    log "WARNING: 长图截图失败"
  fi
else
  log "WARNING: 长图HTML生成失败"
fi

log "AI日报全部完成!"
