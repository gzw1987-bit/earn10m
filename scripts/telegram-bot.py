#!/usr/bin/env python3
"""Telegram Bot — 发消息自动记录到飞书+同步网站"""

import json
import subprocess
import time
import urllib.request
import urllib.parse
import sys
import os
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_DIR = os.path.join(PROJECT_ROOT, "var")
OFFSET_PATH = os.path.join(STATE_DIR, "telegram-update-offset")


def load_env_file(path):
    """加载简单 KEY=VALUE 文件，不执行 shell 表达式。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key.isidentifier() or key in os.environ:
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            os.environ[key] = value


load_env_file(os.path.join(PROJECT_ROOT, ".env"))

BOT_TOKEN = os.environ.get("TELEGRAM_LOG_BOT_TOKEN", "")
ALLOWED_CHAT_ID = os.environ.get("TELEGRAM_ALLOWED_CHAT_ID", "")
BASE_TOKEN = "OdCpbN0EKaEQBCsfeNgcUoLKnJd"
LOG_TABLE = "tblJS1rIjKsKjH3p"
BIZ_TABLE = "tblaEFebNACEMR71"
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
START_DATE = datetime(2026, 4, 13)
AUTO_PUBLISH_ENABLED = os.environ.get("AUTO_PUBLISH_ENABLED", "").lower() in {
    "1", "true", "yes"
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def validate_config():
    missing = []
    if not BOT_TOKEN:
        missing.append("TELEGRAM_LOG_BOT_TOKEN")
    if not ALLOWED_CHAT_ID:
        missing.append("TELEGRAM_ALLOWED_CHAT_ID")
    if missing:
        raise RuntimeError(f"缺少必要配置: {', '.join(missing)}")


def load_offset():
    try:
        with open(OFFSET_PATH, encoding="utf-8") as offset_file:
            return int(offset_file.read().strip())
    except (FileNotFoundError, ValueError, OSError):
        return None


def save_offset(offset):
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    tmp_path = f"{OFFSET_PATH}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as offset_file:
        offset_file.write(str(offset))
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, OFFSET_PATH)

def tg_request(method, params=None):
    url = f"{API_BASE}/{method}"
    if params:
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data)
    else:
        req = urllib.request.Request(url)
    try:
        # 使用 Python 默认 CA 与主机名校验；代理证书问题必须修代理信任链。
        with urllib.request.urlopen(req, timeout=35) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"API错误: {e}")
        return None

def send_msg(chat_id, text):
    tg_request("sendMessage", {"chat_id": chat_id, "text": text})

def run_claude(prompt):
    """用 Claude CLI 处理文本"""
    try:
        result = subprocess.run(
            ["/Users/gzw/.local/bin/claude", "-p", "--allowedTools", ""],
            input=prompt, capture_output=True, text=True, timeout=120
        )
        return result.stdout.strip()
    except Exception as e:
        log(f"Claude错误: {e}")
        return None

def write_to_feishu_log(title, summary, content, mood, tags):
    """写入飞书日志表"""
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = f"{today} 00:00:00"

    json_payload = json.dumps({
        "fields": ["日期", "标题", "摘要", "正文", "心情", "标签"],
        "rows": [[timestamp, title, summary, content, mood, tags]]
    }, ensure_ascii=False)

    try:
        result = subprocess.run(
            ["lark-cli", "base", "+record-batch-create",
             "--base-token", BASE_TOKEN,
             "--table-id", LOG_TABLE,
             "--json", json_payload],
            capture_output=True, text=True, timeout=30
        )
        return lark_command_succeeded(result)
    except Exception as e:
        log(f"飞书写入错误: {e}")
        return False


def lark_command_succeeded(result):
    if result.returncode != 0:
        return False
    output = result.stdout.strip()
    if not output:
        return True
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return '"ok": true' in output or '"code": 0' in output
    if not isinstance(payload, dict):
        return True
    return payload.get("ok", True) is not False and payload.get("code", 0) == 0

def write_to_feishu_biz(name, desc, status):
    """写入飞书业务线表"""
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = f"{today} 00:00:00"

    json_payload = json.dumps({
        "fields": ["名称", "描述", "状态", "启动日期", "累计收入", "标签"],
        "rows": [[name, desc, status, timestamp, 0, ""]]
    }, ensure_ascii=False)

    try:
        result = subprocess.run(
            ["lark-cli", "base", "+record-batch-create",
             "--base-token", BASE_TOKEN,
             "--table-id", BIZ_TABLE,
             "--json", json_payload],
            capture_output=True, text=True, timeout=30
        )
        return lark_command_succeeded(result)
    except Exception as e:
        log(f"业务线写入错误: {e}")
        return False

def trigger_deploy():
    """串行同步网站数据；自动发布必须显式启用。"""
    try:
        command = ["bash", os.path.join(PROJECT_ROOT, "scripts", "auto-deploy.sh")]
        if AUTO_PUBLISH_ENABLED:
            command.append("--publish")
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=300,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"网站同步错误: {exc}")
        return False

def process_message(text):
    """用 Claude 把用户消息整理成结构化日志"""
    day_num = (datetime.now() - START_DATE).days + 1
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""你是日志整理助手。用户发来了今天做的事情，请整理成JSON。

用户输入：
{text}

今天是 {today}，这是项目第 {day_num} 天。

请输出严格JSON（不要markdown代码块，不要任何其他文字）：
{{"title": "Day {day_num}: 简短标题", "summary": "一句话摘要50字以内", "content": "# Day {day_num}: 标题\\n\\n## 今天做了什么\\n\\n1. **事项1** — 描述\\n\\n## 当前状态\\n\\n- 负债：360万\\n- 业务线：进展", "mood": "不错", "tags": "标签1,标签2", "new_business": []}}

规则：
- mood 从 极佳/不错/平稳/有点难/很艰难 里选
- 如果提到新业务线，new_business 格式 [{{"name":"名称","desc":"描述","status":"建设中"}}]
- content 用 markdown 格式
- 只输出JSON"""

    raw = run_claude(prompt)
    if not raw:
        return None

    # 尝试解析 JSON
    import re
    try:
        return json.loads(raw)
    except:
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            try:
                return json.loads(m.group())
            except:
                pass
    return None

def main():
    validate_config()
    log("Telegram Bot 启动，等待消息...")
    offset = load_offset()

    if offset is None:
        # 首次升级沿用旧行为，只建立初始游标；之后每次重启从持久游标恢复。
        offset = 0
        resp = tg_request("getUpdates", {"offset": -1, "limit": 1})
        if resp and resp.get("result"):
            offset = resp["result"][-1]["update_id"] + 1
        save_offset(offset)
        log(f"已建立初始 update 游标: {offset}")
    else:
        log(f"从持久 update 游标恢复: {offset}")

    while True:
        try:
            resp = tg_request("getUpdates", {"offset": offset, "timeout": 30})
            if not resp or not resp.get("ok"):
                time.sleep(5)
                continue

            for update in resp.get("result", []):
                next_offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "")

                if not chat_id or not text:
                    offset = next_offset
                    save_offset(offset)
                    continue

                if chat_id != ALLOWED_CHAT_ID:
                    log(f"忽略未授权用户: {chat_id}")
                    offset = next_offset
                    save_offset(offset)
                    continue

                log(f"收到 update={update['update_id']}，文本长度={len(text)}")

                # 特殊命令
                if text == "/status":
                    send_msg(chat_id, "Bot 运行中。直接发消息告诉我今天做了什么，自动记录到飞书和网站。")
                    offset = next_offset
                    save_offset(offset)
                    continue

                if text == "/help":
                    send_msg(chat_id, "使用方法：\n\n直接发今天做的事，比如：\n「今天做了小红书Agent，写了3篇文章」\n\n我会自动：\n1. 整理成日志\n2. 写入飞书\n3. 同步到网站\n\n命令：\n/status - 检查bot状态\n/help - 帮助")
                    offset = next_offset
                    save_offset(offset)
                    continue

                send_msg(chat_id, "收到，正在整理...")

                # 处理消息
                data = process_message(text)
                if not data:
                    send_msg(chat_id, "抱歉，处理失败了。请重新描述试试。")
                    offset = next_offset
                    save_offset(offset)
                    continue

                title = data.get("title", "")
                summary = data.get("summary", "")
                content = data.get("content", "")
                mood = data.get("mood", "不错")
                tags = data.get("tags", "")

                # 写入飞书日志
                ok = write_to_feishu_log(title, summary, content, mood, tags)

                # 写入新业务线
                biz_lines = data.get("new_business", [])
                biz_ok = True
                biz_msg = ""
                for biz in biz_lines:
                    current_biz_ok = write_to_feishu_biz(
                        biz["name"], biz["desc"], biz.get("status", "建设中")
                    )
                    biz_ok = biz_ok and current_biz_ok
                    if current_biz_ok:
                        biz_msg += f"\n+ 新业务线: {biz['name']}"

                # 只有飞书全部写入成功才同步公开网站数据。
                sync_ok = ok and biz_ok and trigger_deploy()

                # 回复
                if ok and biz_ok and sync_ok:
                    sync_status = "网站发布已触发" if AUTO_PUBLISH_ENABLED else "网站数据已同步，等待审查发布"
                    reply = f"已记录!\n\n{title}\n{summary}\n心情: {mood}\n标签: {tags}{biz_msg}\n\n{sync_status}。"
                elif ok and biz_ok:
                    reply = f"日志已写入飞书，但网站数据同步失败，请检查。\n\n{title}\n{summary}"
                else:
                    reply = f"日志内容已整理但飞书写入失败，未触发网站同步。\n\n{title}\n{summary}"

                send_msg(chat_id, reply)
                log(f"处理完成: {title}")
                offset = next_offset
                save_offset(offset)

        except KeyboardInterrupt:
            log("Bot 停止")
            break
        except Exception as e:
            log(f"循环错误: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
