#!/bin/bash
# 从飞书多维表格同步数据到网站
# 用法: npm run sync

set -e

BASE_TOKEN="OdCpbN0EKaEQBCsfeNgcUoLKnJd"
DATA_DIR="src/data/feishu"

echo "开始从飞书同步数据..."

mkdir -p "$DATA_DIR"

# 同步每日日志
echo "  -> 同步每日日志..."
lark-cli base +record-list \
  --base-token "$BASE_TOKEN" \
  --table-id tblJS1rIjKsKjH3p \
  --limit 200 > "$DATA_DIR/logs.json"

# 同步财务月报
echo "  -> 同步财务月报..."
lark-cli base +record-list \
  --base-token "$BASE_TOKEN" \
  --table-id tblM0py9ZcUjGld3 \
  --limit 200 > "$DATA_DIR/finance.json"

# 同步业务线
echo "  -> 同步业务线..."
lark-cli base +record-list \
  --base-token "$BASE_TOKEN" \
  --table-id tblaEFebNACEMR71 \
  --limit 200 > "$DATA_DIR/business.json"

# 同步内容发布
echo "  -> 同步内容发布..."
lark-cli base +record-list \
  --base-token "$BASE_TOKEN" \
  --table-id tblEcP6FTPM4R9Jr \
  --limit 200 > "$DATA_DIR/content.json"

echo "同步完成! 数据已保存到 $DATA_DIR/"
echo "运行 npm run dev 查看更新后的网站"
