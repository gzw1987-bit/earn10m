#!/bin/bash
# 从飞书同步公开数据。候选、验证、原子切换、恢复和可选构建共享同一把锁。

set -Eeuo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_PARENT="${FEISHU_DATA_PARENT:-$ROOT_DIR/src/data}"
DATA_DIR="${FEISHU_DATA_DIR:-$DATA_PARENT/feishu}"
LAST_GOOD_DIR="${FEISHU_LAST_GOOD_DIR:-$DATA_PARENT/.feishu-last-good}"
PRE_RESTORE_DIR="${FEISHU_PRE_RESTORE_DIR:-$DATA_PARENT/.feishu-pre-restore}"
LOCK_DIR="${EARN10M_LOCK_DIR:-$ROOT_DIR/var/locks/data-sync.lock}"
LARK_CLI_BIN="${LARK_CLI_BIN:-lark-cli}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
BASE_TOKEN="${FEISHU_BASE_TOKEN:-OdCpbN0EKaEQBCsfeNgcUoLKnJd}"
STAGING_DIR=""
PRESERVE_STAGING=false
LOCK_OWNED=false
MODE="sync"

usage() {
  echo "用法: $0 [--restore|--build]" >&2
}

if [ "${1:-}" = "--restore" ]; then
  MODE="restore"
elif [ "${1:-}" = "--build" ]; then
  MODE="build"
elif [ -n "${1:-}" ]; then
  usage
  exit 64
fi
if [ -n "${2:-}" ]; then
  usage
  exit 64
fi

acquire_lock() {
  local delegated_pid="${EARN10M_SYNC_LOCK_OWNER_PID:-}"
  local recorded_pid=""
  if [ -n "$delegated_pid" ]; then
    if [ -f "$LOCK_DIR/pid" ]; then
      recorded_pid="$(tr -cd '0-9' < "$LOCK_DIR/pid")"
    fi
    if [ "$delegated_pid" = "$PPID" ] \
      && [ "$recorded_pid" = "$delegated_pid" ] \
      && kill -0 "$delegated_pid" 2>/dev/null; then
      return 0
    fi
    echo "共享锁委托无效，拒绝绕过互斥" >&2
    return 1
  fi
  mkdir -p "$(dirname "$LOCK_DIR")"
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_DIR/pid"
    LOCK_OWNED=true
    return 0
  fi
  local owner_pid=""
  if [ -f "$LOCK_DIR/pid" ]; then
    owner_pid="$(tr -cd '0-9' < "$LOCK_DIR/pid")"
  fi
  if [ -z "$owner_pid" ]; then
    echo "数据锁存在但没有有效 PID；为避免并发，本次拒绝并保留锁" >&2
    return 1
  fi
  if kill -0 "$owner_pid" 2>/dev/null; then
    echo "已有数据任务运行（PID ${owner_pid}），本次拒绝并发" >&2
    return 1
  fi
  echo "发现死 PID 数据锁（PID ${owner_pid}）；拒绝自动清理，需人工复核" >&2
  return 1
}

cleanup() {
  if [ -n "$STAGING_DIR" ] && [ -d "$STAGING_DIR" ]; then
    if [ "$PRESERVE_STAGING" = true ]; then
      chmod -R go-rwx "$STAGING_DIR" 2>/dev/null || true
      echo "安装阶段失败；候选证据已保留在 ${STAGING_DIR}，人工复核后再删除" >&2
    else
      rm -rf "$STAGING_DIR"
    fi
  fi
  if [ "$LOCK_OWNED" = true ]; then
    local recorded_pid=""
    if [ -f "$LOCK_DIR/pid" ]; then
      recorded_pid="$(tr -cd '0-9' < "$LOCK_DIR/pid")"
    fi
    if [ "$recorded_pid" = "$$" ]; then
      rm -rf "$LOCK_DIR"
    else
      echo "锁所有者已变化，拒绝清理" >&2
    fi
  fi
}

handle_signal() {
  local exit_code="$1"
  trap - HUP INT TERM
  exit "$exit_code"
}

trap cleanup EXIT
trap 'handle_signal 129' HUP
trap 'handle_signal 130' INT
trap 'handle_signal 143' TERM

if ! acquire_lock; then
  exit 75
fi

if [ "$MODE" = "restore" ]; then
  "$PYTHON_BIN" "$ROOT_DIR/scripts/feishu_data_sync.py" restore \
    --live "$DATA_DIR" \
    --last-good "$LAST_GOOD_DIR" \
    --rescue "$PRE_RESTORE_DIR"
  echo "恢复完成；恢复前快照保存在 $PRE_RESTORE_DIR，可用于人工撤销"
  exit 0
fi

if ! command -v "$LARK_CLI_BIN" >/dev/null 2>&1 && [ ! -x "$LARK_CLI_BIN" ]; then
  echo "找不到 lark-cli: $LARK_CLI_BIN" >&2
  exit 127
fi

mkdir -p "$DATA_PARENT"
STAGING_DIR="$(mktemp -d "$DATA_PARENT/.feishu-candidate.XXXXXX")"

export_table() {
  local label="$1"
  local table_id="$2"
  local output_name="$3"
  echo "  -> 同步${label}..."
  "$LARK_CLI_BIN" base +record-list \
    --base-token "$BASE_TOKEN" \
    --table-id "$table_id" \
    --limit 200 \
    --format json > "$STAGING_DIR/$output_name"
}

echo "开始从飞书同步数据（候选目录隔离）..."
export_table "每日日志" "tblJS1rIjKsKjH3p" "logs.json"
export_table "财务月报" "tblM0py9ZcUjGld3" "finance.json"
export_table "业务线" "tblaEFebNACEMR71" "business.json"
export_table "内容发布" "tblEcP6FTPM4R9Jr" "content.json"

"$PYTHON_BIN" "$ROOT_DIR/scripts/feishu_data_sync.py" prepare \
  --source "$STAGING_DIR"
"$PYTHON_BIN" "$ROOT_DIR/scripts/feishu_data_sync.py" validate \
  --source "$STAGING_DIR"
PRESERVE_STAGING=true
"$PYTHON_BIN" "$ROOT_DIR/scripts/feishu_data_sync.py" install \
  --source "$STAGING_DIR" \
  --live "$DATA_DIR" \
  --last-good "$LAST_GOOD_DIR"
PRESERVE_STAGING=false

echo "同步完成：正式目录只包含完整验证后的公开 JSON 数据。"
echo "如需恢复上一份有效快照：npm run sync:restore"

if [ "$MODE" = "build" ]; then
  cd "$ROOT_DIR"
  npm run build
fi
