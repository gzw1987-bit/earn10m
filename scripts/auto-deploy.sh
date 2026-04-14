#!/bin/bash
# 自动同步飞书数据并部署到 Vercel
# 每小时自动执行一次

cd /Users/gzw/earn10m

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

log "开始自动同步..."

# 1. 从飞书拉数据
bash scripts/sync-feishu.sh > /dev/null 2>&1

if [ $? -ne 0 ]; then
  log "飞书同步失败"
  exit 1
fi

# 2. 检查是否有变化
CHANGES=$(git diff --stat src/data/feishu/)

if [ -z "$CHANGES" ]; then
  log "数据无变化，跳过部署"
  exit 0
fi

log "检测到数据更新，开始部署..."

# 3. 提交并部署
git add src/data/feishu/
git commit -m "sync: $(date '+%Y-%m-%d %H:%M') 飞书数据更新" > /dev/null 2>&1
git push > /dev/null 2>&1
# Token 从环境变量读取，不硬编码在脚本里
/opt/homebrew/bin/vercel --prod --yes --token "$VERCEL_TOKEN" > /dev/null 2>&1

if [ $? -eq 0 ]; then
  log "部署成功"
else
  log "部署失败"
fi
