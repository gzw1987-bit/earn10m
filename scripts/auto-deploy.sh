#!/bin/bash
# 从飞书同步公开数据；只有显式传入 --publish 才提交并推送数据变更。

set -Eeuo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK_DIR="${EARN10M_LOCK_DIR:-$ROOT_DIR/var/locks/data-sync.lock}"
DEFAULT_DATA_DIR="$ROOT_DIR/src/data/feishu"
DATA_PARENT="${FEISHU_DATA_PARENT:-$ROOT_DIR/src/data}"
DATA_DIR="${FEISHU_DATA_DIR:-$DATA_PARENT/feishu}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PUBLISH=false
ACTIVE_CHILD_PID=""

if [ "${1:-}" = "--publish" ]; then
  PUBLISH=true
elif [ -n "${1:-}" ]; then
  echo "用法: $0 [--publish]" >&2
  exit 64
fi

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

acquire_lock() {
  mkdir -p "$(dirname "$LOCK_DIR")"
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_DIR/pid"
    return 0
  fi

  local owner_pid=""
  if [ -f "$LOCK_DIR/pid" ]; then
    owner_pid="$(tr -cd '0-9' < "$LOCK_DIR/pid")"
  fi

  if [ -z "$owner_pid" ]; then
    log "同步锁存在但没有有效 PID；为避免并发，本次拒绝并保留锁"
    return 1
  fi

  if kill -0 "$owner_pid" 2>/dev/null; then
    log "已有同步任务运行（PID ${owner_pid}），本次跳过"
    return 1
  fi

  log "发现死 PID 同步锁（PID ${owner_pid}）；为避免清锁竞态，本次拒绝，需人工复核后清理"
  return 1
}

release_lock() {
  local recorded_pid=""
  if [ -f "$LOCK_DIR/pid" ]; then
    recorded_pid="$(tr -cd '0-9' < "$LOCK_DIR/pid")"
  fi
  if [ "$recorded_pid" = "$$" ]; then
    rm -rf "$LOCK_DIR"
  else
    log "锁所有者已变化，拒绝清理"
  fi
}

handle_signal() {
  local exit_code="$1"
  trap - HUP INT TERM
  if [ -n "$ACTIVE_CHILD_PID" ] && kill -0 "$ACTIVE_CHILD_PID" 2>/dev/null; then
    kill -TERM "$ACTIVE_CHILD_PID" 2>/dev/null || true
    wait "$ACTIVE_CHILD_PID" 2>/dev/null || true
  fi
  exit "$exit_code"
}

validate_json_exports() {
  "$PYTHON_BIN" "$ROOT_DIR/scripts/feishu_data_sync.py" validate \
    --source "$DATA_DIR"
}

if ! acquire_lock; then
  exit 75
fi
trap release_lock EXIT
trap 'handle_signal 129' HUP
trap 'handle_signal 130' INT
trap 'handle_signal 143' TERM

cd "$ROOT_DIR"
log "开始同步飞书数据"

EARN10M_SYNC_LOCK_OWNER_PID="$$" bash scripts/sync-feishu.sh &
ACTIVE_CHILD_PID=$!
if wait "$ACTIVE_CHILD_PID"; then
  sync_status=0
else
  sync_status=$?
fi
ACTIVE_CHILD_PID=""
if [ "$sync_status" -ne 0 ]; then
  log "飞书同步失败，未触发发布"
  exit 1
fi

if ! validate_json_exports; then
  log "同步结果未通过 JSON Schema 或业务不变量，未触发发布"
  exit 1
fi

if [ "$DATA_DIR" != "$DEFAULT_DATA_DIR" ]; then
  if [ "$PUBLISH" = true ]; then
    log "自定义 FEISHU_DATA_DIR 只允许本地验证，拒绝提交或推送"
    exit 1
  fi
  log "自定义数据目录已更新并验证；未进入 Git 发布流程"
  exit 0
fi

if [ -z "$(git status --porcelain -- src/data/feishu/)" ]; then
  log "数据无变化"
  exit 0
fi

if [ "$PUBLISH" != true ]; then
  log "数据已更新但尚未发布；审查后运行 npm run publish:data"
  exit 0
fi

# 发布前要求除生成的数据外没有其它工作区改动，避免自动任务夹带代码或秘密。
UNRELATED_CHANGES="$(git status --porcelain --untracked-files=normal | awk 'substr($0,4) !~ /^src\/data\/feishu\// {print}')"
if [ -n "$UNRELATED_CHANGES" ]; then
  log "检测到飞书数据目录之外的工作区改动，拒绝自动提交和推送"
  exit 1
fi

git add -- src/data/feishu/
if git diff --cached --quiet -- src/data/feishu/; then
  log "暂存后没有数据变化"
  exit 0
fi

git commit -m "sync: $(date '+%Y-%m-%d %H:%M') 飞书数据更新"
git push
log "数据已推送；后续部署由仓库 CI/Vercel Git 集成负责"
