#!/bin/bash
# 兼容旧的启动入口；唯一实现位于 telegram-bot.py，避免两套逻辑分叉。

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$ROOT_DIR/scripts/telegram-bot.py"
