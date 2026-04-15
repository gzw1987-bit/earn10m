#!/bin/bash
# Telegram Bot 自动日志记录
# 监听 Telegram 消息 → AI整理 → 写入飞书 → 回复确认
# 作为后台服务运行

# 加载 .env
ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env"
if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

BOT_TOKEN="${TELEGRAM_DAILY_BOT_TOKEN}"
ALLOWED_CHAT_ID="8296218023"
BASE_TOKEN="OdCpbN0EKaEQBCsfeNgcUoLKnJd"
LOG_TABLE="tblJS1rIjKsKjH3p"
BIZ_TABLE="tblaEFebNACEMR71"
OFFSET=0

log() { echo "[$(date '+%H:%M:%S')] $1"; }

send_msg() {
  curl -s "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    -d chat_id="$1" -d text="$2" > /dev/null 2>&1
}

log "Telegram Bot 启动，等待消息..."

while true; do
  # 获取新消息
  RESPONSE=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getUpdates?offset=${OFFSET}&timeout=30" 2>/dev/null)

  # 解析消息
  MESSAGES=$(echo "$RESPONSE" | python3 -c "
import json,sys
try:
    data = json.load(sys.stdin)
    if not data.get('ok'): sys.exit(0)
    for r in data.get('result', []):
        uid = r['update_id']
        msg = r.get('message', {})
        chat_id = str(msg.get('chat', {}).get('id', ''))
        text = msg.get('text', '')
        if chat_id and text:
            print(f'{uid}|||{chat_id}|||{text}')
except: pass
" 2>/dev/null)

  # 处理每条消息
  while IFS= read -r line; do
    [ -z "$line" ] && continue

    UPDATE_ID=$(echo "$line" | awk -F'\\|\\|\\|' '{print $1}')
    CHAT_ID=$(echo "$line" | awk -F'\\|\\|\\|' '{print $2}')
    TEXT=$(echo "$line" | awk -F'\\|\\|\\|' '{print $3}')
    OFFSET=$((UPDATE_ID + 1))

    # 只处理允许的用户
    if [ "$CHAT_ID" != "$ALLOWED_CHAT_ID" ]; then
      log "忽略未授权用户: $CHAT_ID"
      continue
    fi

    log "收到消息: ${TEXT:0:50}..."

    # 特殊命令
    if [ "$TEXT" = "/status" ]; then
      send_msg "$CHAT_ID" "Bot 运行中。输入今天做的事，我帮你记录到飞书和网站。"
      continue
    fi

    send_msg "$CHAT_ID" "收到，正在处理..."

    TODAY=$(date +%Y-%m-%d)
    TIMESTAMP="${TODAY} 00:00:00"

    # 用 Claude 整理成结构化日志
    STRUCTURED=$(echo "你是日志整理助手。用户发来了今天做的事情，请整理成JSON格式。

用户输入：
$TEXT

请输出严格的JSON（不要markdown代码块），格式：
{
  \"title\": \"Day X: 简短标题\",
  \"summary\": \"一句话摘要，50字以内\",
  \"content\": \"完整的markdown正文，包含## 今天做了什么（列表形式）和## 当前状态\",
  \"mood\": \"不错\",
  \"tags\": \"标签1,标签2,标签3\",
  \"new_business\": []
}

规则：
- 根据内容判断 Day 数字（从2026-04-13算第1天）
- mood 从这几个里选：极佳/不错/平稳/有点难/很艰难
- 如果提到新业务线，在 new_business 里列出，格式 [{\"name\":\"名称\",\"desc\":\"描述\",\"status\":\"建设中\"}]
- 如果没有新业务线，new_business 为空数组
- content 里要有 ## 今天做了什么（把用户说的内容整理成编号列表）
- 只输出JSON，不要其他文字" | /Users/gzw/.local/bin/claude -p --allowedTools "" 2>/dev/null)

    # 提取JSON
    JSON_DATA=$(echo "$STRUCTURED" | python3 -c "
import json,sys,re
text = sys.stdin.read()
# 尝试直接解析
try:
    d = json.loads(text)
    print(json.dumps(d, ensure_ascii=False))
    sys.exit(0)
except: pass
# 尝试从markdown代码块提取
m = re.search(r'\{[\s\S]*\}', text)
if m:
    try:
        d = json.loads(m.group())
        print(json.dumps(d, ensure_ascii=False))
        sys.exit(0)
    except: pass
print('ERROR')
" 2>/dev/null)

    if [ "$JSON_DATA" = "ERROR" ] || [ -z "$JSON_DATA" ]; then
      send_msg "$CHAT_ID" "解析失败，请重新描述今天做了什么。"
      log "JSON解析失败"
      continue
    fi

    # 提取字段
    TITLE=$(echo "$JSON_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin)['title'])" 2>/dev/null)
    SUMMARY=$(echo "$JSON_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin)['summary'])" 2>/dev/null)
    CONTENT=$(echo "$JSON_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin)['content'])" 2>/dev/null)
    MOOD=$(echo "$JSON_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin)['mood'])" 2>/dev/null)
    TAGS=$(echo "$JSON_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin)['tags'])" 2>/dev/null)

    # 写入飞书日志
    log "写入飞书日志..."
    ESCAPED_CONTENT=$(echo "$CONTENT" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read())[1:-1])" 2>/dev/null)

    lark-cli base +record-batch-create \
      --base-token "$BASE_TOKEN" \
      --table-id "$LOG_TABLE" \
      --json "{\"fields\":[\"日期\",\"标题\",\"摘要\",\"正文\",\"心情\",\"标签\"],\"rows\":[[\"$TIMESTAMP\",\"$TITLE\",\"$SUMMARY\",\"$ESCAPED_CONTENT\",\"$MOOD\",\"$TAGS\"]]}" > /dev/null 2>&1

    # 检查是否有新业务线
    NEW_BIZ=$(echo "$JSON_DATA" | python3 -c "
import json,sys
d = json.load(sys.stdin)
biz = d.get('new_business', [])
if biz:
    for b in biz:
        print(f'{b[\"name\"]}|||{b[\"desc\"]}|||{b.get(\"status\",\"建设中\")}')
" 2>/dev/null)

    BIZ_MSG=""
    while IFS= read -r bline; do
      [ -z "$bline" ] && continue
      BIZ_NAME=$(echo "$bline" | cut -d'|||' -f1)
      BIZ_DESC=$(echo "$bline" | cut -d'|||' -f2)
      BIZ_STATUS=$(echo "$bline" | cut -d'|||' -f3)

      lark-cli base +record-batch-create \
        --base-token "$BASE_TOKEN" \
        --table-id "$BIZ_TABLE" \
        --json "{\"fields\":[\"名称\",\"描述\",\"状态\",\"启动日期\",\"累计收入\",\"标签\"],\"rows\":[[\"$BIZ_NAME\",\"$BIZ_DESC\",\"$BIZ_STATUS\",\"$TIMESTAMP\",0,\"\"]]}" > /dev/null 2>&1

      BIZ_MSG="$BIZ_MSG\n+ 新业务线: $BIZ_NAME"
      log "新增业务线: $BIZ_NAME"
    done <<< "$NEW_BIZ"

    # 触发网站同步
    log "触发网站同步..."
    bash /Users/gzw/earn10m/scripts/auto-deploy.sh > /dev/null 2>&1 &

    # 回复确认
    REPLY="已记录到飞书和网站!

日志: $TITLE
摘要: $SUMMARY
心情: $MOOD
标签: $TAGS${BIZ_MSG}

网站正在同步更新中..."

    send_msg "$CHAT_ID" "$REPLY"
    log "处理完成: $TITLE"

  done <<< "$MESSAGES"
done
