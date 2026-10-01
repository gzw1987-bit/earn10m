from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bot = load_script("telegram_bot", "telegram-bot.py")
renderer = load_script("daily_to_image", "daily-to-image.py")
VALID_LOG = {"title": "Day 1", "summary": "summary", "content": "# Day 1", "mood": "不错", "tags": "AI", "new_business": []}


class TelegramSafetyTests(unittest.TestCase):
    def test_malformed_model_output_never_writes_or_syncs(self):
        cases = [[], {}, {**VALID_LOG, "title": ""}, {**VALID_LOG, "content": None},
                 {**VALID_LOG, "tags": []}, {**VALID_LOG, "mood": "unknown"},
                 {**VALID_LOG, "new_business": [{}]},
                 {**VALID_LOG, "new_business": [{"name": "new", "desc": None}]}]
        for data in cases:
            with self.subTest(data=data):
                update = {"update_id": 1, "message": {"chat": {"id": "123"}, "text": "today"}}
                with patch.object(bot, "validate_config"), patch.object(bot, "ALLOWED_CHAT_ID", "123"), \
                     patch.object(bot, "load_offset", return_value=0), patch.object(bot, "save_offset") as offset, \
                     patch.object(bot, "tg_request", side_effect=[{"ok": True, "result": [update]}, KeyboardInterrupt]), \
                     patch.object(bot, "run_claude", return_value=json.dumps(data)), \
                     patch.object(bot, "send_msg"), patch.object(bot, "log"), \
                     patch.object(bot, "write_to_feishu_log") as write_log, \
                     patch.object(bot, "write_to_feishu_biz") as write_biz, \
                     patch.object(bot, "trigger_deploy") as sync:
                    bot.main()
                    write_log.assert_not_called()
                    write_biz.assert_not_called()
                    sync.assert_not_called()
                    offset.assert_called_once_with(2)

    def test_valid_fenced_json_still_processes(self):
        for raw in (json.dumps(VALID_LOG), "```json\n" + json.dumps(VALID_LOG) + "\n```"):
            with patch.object(bot, "run_claude", return_value=raw):
                self.assertEqual(bot.process_message("today"), VALID_LOG)

    def test_lark_result_requires_explicit_success(self):
        failures = ["", "[]", "{}", "null", "true", '{"code": false}',
                    '{"ok": true, "code": 3}', '{"ok": false, "code": 0}',
                    'warning: {"ok": true}', '{"error": "denied"}']
        for output in failures:
            with self.subTest(output=output):
                self.assertFalse(bot.lark_command_succeeded(SimpleNamespace(returncode=0, stdout=output)))
        for output in ('{"ok": true}', '{"code": 0}', '{"ok": true, "code": 0}'):
            self.assertTrue(bot.lark_command_succeeded(SimpleNamespace(returncode=0, stdout=output)))
            self.assertFalse(bot.lark_command_succeeded(SimpleNamespace(returncode=1, stdout=output)))

    def test_feishu_writes_request_explicit_json_output(self):
        for writer, args in ((bot.write_to_feishu_log, ("title", "summary", "content", "不错", "AI")),
                             (bot.write_to_feishu_biz, ("name", "desc", "建设中"))):
            with patch.object(bot.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout='{"ok": true}')) as run:
                self.assertTrue(writer(*args))
                command = run.call_args.args[0]
                self.assertEqual(command[0], bot.LARK_CLI_BIN)
                self.assertEqual(command[command.index("--format") + 1], "json")
                json.loads(command[command.index("--json") + 1])

    def test_failed_claude_command_cannot_return_partial_output(self):
        with patch.object(bot.subprocess, "run", return_value=SimpleNamespace(returncode=2, stdout=json.dumps(VALID_LOG))), patch.object(bot, "log"):
            self.assertIsNone(bot.run_claude("today"))

    def test_api_token_is_redacted_from_logs(self):
        output = io.StringIO()
        with patch.object(bot, "BOT_TOKEN", "test-token"), contextlib.redirect_stdout(output):
            bot.log("failed https://api.telegram.org/bottest-token/sendMessage")
        self.assertNotIn("test-token", output.getvalue())
        self.assertIn("<redacted>", output.getvalue())


class DailyReportScriptTests(unittest.TestCase):
    def make_project(self, temporary, *, curl_ok=True, generation_ok=True):
        root = Path(temporary) / "project with spaces"
        scripts, bins = root / "scripts", root / "fake binaries"
        scripts.mkdir(parents=True)
        bins.mkdir()
        for filename in ("ai-daily.sh", "daily-to-image.py"):
            shutil.copyfile(ROOT / "scripts" / filename, scripts / filename)
        report_content = "# Daily 2026-10-01\n\n## Main\n\n" + "😀" * 2600 + " & body=" * 350
        (root / "report-input.md").write_text(report_content, encoding="utf-8")
        fake_scripts = {
            "claude": """#!/usr/bin/env python3
import os, re, sys
from pathlib import Path
prompt = sys.stdin.read()
if os.environ['GENERATION_OK'] == 'true':
    path = re.search(r'然后将结果写入 (.+)，格式如下', prompt).group(1)
    Path(path).write_text(Path(os.environ['REPORT_INPUT']).read_text(encoding='utf-8'), encoding='utf-8')
""",
            "lark": """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
assert '--format' in sys.argv and sys.argv[sys.argv.index('--format') + 1] == 'json'
Path(os.environ['LARK_MARKER']).write_text('called')
print(json.dumps({'ok': True}))
""",
            "curl": r"""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
assert '--data-urlencode' in args
assert 'bottest token & $(touch injected)' in ''.join(args)
text_arg = next(arg for arg in args if arg.startswith('text@'))
text = Path(text_arg[5:]).read_text(encoding='utf-8')
assert len(text.encode('utf-16-le')) // 2 <= 4000
with Path(os.environ['MESSAGE_LOG']).open('a',encoding='utf-8') as handle:
    handle.write(json.dumps(text,ensure_ascii=False) + '\n')
print(json.dumps({'ok': os.environ['CURL_OK'] == 'true'}))
""",
            "playwright": "#!/bin/sh\nexit 1\n",
        }
        for name, code in fake_scripts.items():
            path = bins / name
            path.write_text(code, encoding="utf-8")
            path.chmod(0o755)
        # Literal config must preserve shell syntax and whitespace without execution.
        (root / ".env").write_text('TELEGRAM_DAILY_BOT_TOKEN="test token & $(touch injected)"\n', encoding="utf-8")
        environment = os.environ.copy()
        environment.pop("TELEGRAM_DAILY_BOT_TOKEN", None)
        environment.update({"PATH": str(bins) + os.pathsep + os.environ.get("PATH", ""),
                            "CLAUDE_CLI_BIN": str(bins / "claude"), "LARK_CLI_BIN": str(bins / "lark"),
                            "DAILY_REPORT_DIR": str(root / "reports"), "GENERATION_OK": str(generation_ok).lower(),
                            "CURL_OK": str(curl_ok).lower(), "REPORT_INPUT": str(root / "report-input.md"),
                            "LARK_MARKER": str(root / "lark-called"), "MESSAGE_LOG": str(root / "messages.jsonl")})
        return root, environment, report_content

    def test_long_unicode_report_is_encoded_and_bounded_without_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, environment, content = self.make_project(temporary)
            result = subprocess.run(["bash", str(root / "scripts/ai-daily.sh")], cwd=root, env=environment, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            messages = [json.loads(line) for line in (root / "messages.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertGreater(len(messages), 1)
            self.assertEqual("".join(messages), content)
            self.assertFalse((root / "injected").exists())
            self.assertEqual(list((root / "reports").glob(".telegram-parts.*")), [])

    def test_telegram_api_failure_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, environment, _ = self.make_project(temporary, curl_ok=False)
            result = subprocess.run(["bash", str(root / "scripts/ai-daily.sh")], cwd=root, env=environment, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Telegram发送失败", result.stdout)
            self.assertNotIn("AI日报全部完成", result.stdout)

    def test_empty_generation_does_not_send_or_overwrite_existing_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, environment, _ = self.make_project(temporary, generation_ok=False)
            reports = root / "reports"
            reports.mkdir()
            day = subprocess.check_output(["date", "+%Y-%m-%d"], text=True).strip()
            existing = reports / (day + ".md")
            existing.write_text("existing report")
            result = subprocess.run(["bash", str(root / "scripts/ai-daily.sh")], cwd=root, env=environment, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(existing.read_text(), "existing report")
            self.assertFalse((root / "lark-called").exists())
            self.assertFalse((root / "messages.jsonl").exists())
            self.assertEqual(list(reports.glob(".*candidate.*")), [])


class ShareHtmlSafetyTests(unittest.TestCase):
    def test_model_html_is_escaped_in_titles_body_and_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, target = Path(temporary) / "daily.md", Path(temporary) / "daily.html"
            source.write_text('# Daily 2026-10-01\n\n## <script>alert(1)</script>\n\n1. **bold** <img src=x onerror=alert(2)> & hello\n\n## 一句话总结\n\n<script>alert(3)</script> **summary**', encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                renderer.md_to_share_html(source, target)
            html = target.read_text(encoding="utf-8")
            self.assertNotIn("<script>", html)
            self.assertNotIn("<img src=x", html)
            self.assertIn("&lt;script&gt;", html)
            self.assertIn("&amp; hello", html)
            self.assertIn('<strong style="color:#fafafa;">bold</strong>', html)


if __name__ == "__main__":
    unittest.main()
