from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

import scripts.feishu_data_sync as sync_module
from scripts.feishu_data_sync import (
    REQUIRED_EXPORTS,
    ValidationError,
    install_exports,
    quarantine_incomplete_logs,
    restore_last_good,
    validate_export_directory,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "feishu-sync"
VALID = FIXTURES / "valid"
INVALID = FIXTURES / "invalid"


def tree_hash(directory: Path) -> str:
    digest = hashlib.sha256()
    for filename in REQUIRED_EXPORTS:
        digest.update(filename.encode())
        digest.update((directory / filename).read_bytes())
    return digest.hexdigest()


def copy_valid(destination: Path) -> None:
    shutil.copytree(VALID, destination)


def set_finance_income(directory: Path, income: int) -> None:
    path = directory / "finance.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    fields = payload["data"]["fields"]
    payload["data"]["data"][0][fields.index("收入")] = income
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_incomplete_log(directory: Path) -> None:
    path = directory / "logs.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    fields = payload["data"]["fields"]
    row = [None] * len(fields)
    row[fields.index("日期")] = "2026-07-12 00:00:00"
    payload["data"]["data"].append(row)
    payload["data"]["record_id_list"].append("rec-draft")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class FeishuDataSyncTests(unittest.TestCase):
    def test_valid_fixture_passes_schema_and_business_invariants(self) -> None:
        summary = validate_export_directory(VALID)
        self.assertEqual(set(summary.file_hashes), set(REQUIRED_EXPORTS))
        self.assertEqual(summary.total_records, 3)

    def test_invalid_fixtures_never_change_live_or_last_good(self) -> None:
        for fixture_name in ("markdown.json", "empty.json", "truncated.json", "wrong-root.json"):
            with self.subTest(fixture=fixture_name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                live = root / "feishu"
                last_good = root / ".feishu-last-good"
                candidate = root / ".feishu-candidate.test"
                copy_valid(live)
                copy_valid(last_good)
                copy_valid(candidate)
                shutil.copyfile(INVALID / fixture_name, candidate / "finance.json")
                live_before = tree_hash(live)
                snapshot_before = tree_hash(last_good)

                with self.assertRaises(ValidationError):
                    install_exports(candidate, live, last_good)

                self.assertEqual(tree_hash(live), live_before)
                self.assertEqual(tree_hash(last_good), snapshot_before)

    def test_incomplete_log_is_rejected_or_quarantined_before_install(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            candidate = Path(temporary) / "candidate"
            copy_valid(candidate)
            add_incomplete_log(candidate)

            with self.assertRaises(ValidationError):
                validate_export_directory(candidate)
            self.assertEqual(quarantine_incomplete_logs(candidate), 1)
            summary = validate_export_directory(candidate)

            self.assertEqual(summary.record_counts["logs.json"], 1)

    def test_schema_pagination_and_identifier_failures_are_rejected(self) -> None:
        mutations = {
            "has_more": lambda payload: payload["data"].__setitem__("has_more", True),
            "duplicate_id": lambda payload: payload["data"]["record_id_list"].__setitem__(
                0, payload["data"]["record_id_list"][-1]
            ),
            "extra_field": lambda payload: (
                payload["data"]["fields"].append("客户手机号"),
                payload["data"]["field_id_list"].append("fld-private"),
                [row.append("not-public") for row in payload["data"]["data"]],
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                candidate = Path(temporary) / "candidate"
                copy_valid(candidate)
                path = candidate / "business.json"
                payload = json.loads(path.read_text(encoding="utf-8"))
                if name == "duplicate_id":
                    payload["data"]["data"].append(payload["data"]["data"][0])
                    payload["data"]["record_id_list"].append(
                        payload["data"]["record_id_list"][0]
                    )
                mutate(payload)
                path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

                with self.assertRaises(ValidationError):
                    validate_export_directory(candidate)

    def test_success_uses_atomic_switch_and_preserves_previous_live(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            live = root / "feishu"
            last_good = root / ".feishu-last-good"
            candidate = root / ".feishu-candidate.test"
            copy_valid(live)
            set_finance_income(live, 999)
            previous_hash = tree_hash(live)
            copy_valid(candidate)
            incoming_hash = tree_hash(candidate)

            summary = install_exports(candidate, live, last_good)

            self.assertEqual(tree_hash(live), incoming_hash)
            self.assertEqual(tree_hash(last_good), previous_hash)
            self.assertFalse(candidate.exists())
            self.assertEqual(summary.total_records, 3)

    def test_post_switch_verification_failure_rolls_back_live(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            live = root / "feishu"
            last_good = root / ".feishu-last-good"
            candidate = root / ".feishu-candidate.test"
            copy_valid(live)
            set_finance_income(live, 999)
            copy_valid(last_good)
            copy_valid(candidate)
            live_before = tree_hash(live)
            snapshot_before = tree_hash(last_good)
            incoming_hash = tree_hash(candidate)
            original_validate = sync_module.validate_export_directory

            def injected_failure(path):
                result = original_validate(path)
                path = Path(path).absolute()
                if path == live.absolute() and tree_hash(path) == incoming_hash:
                    raise RuntimeError("injected post-switch failure")
                return result

            sync_module.validate_export_directory = injected_failure
            try:
                with self.assertRaises(RuntimeError):
                    install_exports(candidate, live, last_good)
            finally:
                sync_module.validate_export_directory = original_validate

            self.assertEqual(tree_hash(live), live_before)
            self.assertEqual(tree_hash(last_good), snapshot_before)
            self.assertTrue(candidate.exists())
            self.assertEqual(tree_hash(candidate), incoming_hash)

    def test_restore_reinstalls_last_good_without_mutating_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            live = root / "feishu"
            last_good = root / ".feishu-last-good"
            rescue = root / ".feishu-pre-restore"
            copy_valid(live)
            copy_valid(last_good)
            set_finance_income(live, 111)
            set_finance_income(last_good, 222)
            snapshot_hash = tree_hash(last_good)

            live_before = tree_hash(live)
            restore_last_good(live, last_good, rescue)

            self.assertEqual(tree_hash(live), snapshot_hash)
            self.assertEqual(tree_hash(last_good), snapshot_hash)
            self.assertEqual(tree_hash(rescue), live_before)

    def test_shell_sync_uses_explicit_json_output_with_offline_fake_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data_parent = root / "data"
            live = data_parent / "feishu"
            last_good = data_parent / ".feishu-last-good"
            fake_cli = root / "fake-lark-cli.py"
            arg_log = root / "arguments.log"
            copy_valid(live)
            set_finance_income(live, 777)
            previous_hash = tree_hash(live)

            fake_cli.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import os
                    from pathlib import Path
                    import sys

                    args = sys.argv[1:]
                    with Path(os.environ["ARG_LOG"]).open("a", encoding="utf-8") as log:
                        log.write(" ".join(args) + "\\n")
                    table_id = args[args.index("--table-id") + 1]
                    names = {
                        "tblJS1rIjKsKjH3p": "logs.json",
                        "tblM0py9ZcUjGld3": "finance.json",
                        "tblaEFebNACEMR71": "business.json",
                        "tblEcP6FTPM4R9Jr": "content.json",
                    }
                    sys.stdout.write((Path(os.environ["FIXTURE_DIR"]) / names[table_id]).read_text(encoding="utf-8"))
                    """
                ),
                encoding="utf-8",
            )
            fake_cli.chmod(0o755)
            environment = os.environ.copy()
            environment.update(
                {
                    "LARK_CLI_BIN": str(fake_cli),
                    "FEISHU_DATA_PARENT": str(data_parent),
                    "FEISHU_DATA_DIR": str(live),
                    "FEISHU_LAST_GOOD_DIR": str(last_good),
                    "FIXTURE_DIR": str(VALID),
                    "ARG_LOG": str(arg_log),
                    "EARN10M_LOCK_DIR": str(root / "sync.lock"),
                }
            )

            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "sync-feishu.sh")],
                cwd=ROOT,
                env=environment,
                text=True,
                errors="replace",
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            calls = arg_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(calls), 4)
            self.assertTrue(all("--format json" in call for call in calls))
            self.assertEqual(tree_hash(live), tree_hash(VALID))
            self.assertEqual(tree_hash(last_good), previous_hash)

    def test_shell_invalid_export_cannot_touch_live_or_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data_parent = root / "data"
            live = data_parent / "feishu"
            last_good = data_parent / ".feishu-last-good"
            fake_cli = root / "fake-lark-cli.py"
            copy_valid(live)
            copy_valid(last_good)
            live_before = tree_hash(live)
            snapshot_before = tree_hash(last_good)

            fake_cli.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import os
                    from pathlib import Path
                    import sys

                    args = sys.argv[1:]
                    table_id = args[args.index("--table-id") + 1]
                    names = {
                        "tblJS1rIjKsKjH3p": "logs.json",
                        "tblM0py9ZcUjGld3": "finance.json",
                        "tblaEFebNACEMR71": "business.json",
                        "tblEcP6FTPM4R9Jr": "content.json",
                    }
                    if table_id == "tblM0py9ZcUjGld3":
                        source = Path(os.environ["INVALID_FIXTURE"])
                    else:
                        source = Path(os.environ["FIXTURE_DIR"]) / names[table_id]
                    sys.stdout.write(source.read_text(encoding="utf-8"))
                    """
                ),
                encoding="utf-8",
            )
            fake_cli.chmod(0o755)
            environment = os.environ.copy()
            environment.update(
                {
                    "LARK_CLI_BIN": str(fake_cli),
                    "FEISHU_DATA_PARENT": str(data_parent),
                    "FEISHU_DATA_DIR": str(live),
                    "FEISHU_LAST_GOOD_DIR": str(last_good),
                    "FIXTURE_DIR": str(VALID),
                    "INVALID_FIXTURE": str(INVALID / "markdown.json"),
                    "EARN10M_LOCK_DIR": str(root / "sync.lock"),
                }
            )

            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "sync-feishu.sh")],
                cwd=ROOT,
                env=environment,
                text=True,
                errors="replace",
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("飞书数据门禁失败", result.stderr)
            self.assertEqual(tree_hash(live), live_before)
            self.assertEqual(tree_hash(last_good), snapshot_before)
            self.assertEqual(list(data_parent.glob(".feishu-candidate.*")), [])

    def test_shell_preserves_candidate_when_install_stage_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data_parent = root / "data"
            live = data_parent / "feishu"
            last_good = data_parent / ".feishu-last-good"
            fake_cli = root / "fake-lark-cli.py"
            python_wrapper = root / "python-wrapper.py"
            copy_valid(live)
            copy_valid(last_good)
            live_before = tree_hash(live)
            snapshot_before = tree_hash(last_good)

            fake_cli.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import os
                    from pathlib import Path
                    import sys

                    args = sys.argv[1:]
                    table_id = args[args.index("--table-id") + 1]
                    names = {
                        "tblJS1rIjKsKjH3p": "logs.json",
                        "tblM0py9ZcUjGld3": "finance.json",
                        "tblaEFebNACEMR71": "business.json",
                        "tblEcP6FTPM4R9Jr": "content.json",
                    }
                    sys.stdout.write((Path(os.environ["FIXTURE_DIR"]) / names[table_id]).read_text(encoding="utf-8"))
                    """
                ),
                encoding="utf-8",
            )
            fake_cli.chmod(0o755)
            python_wrapper.write_text(
                textwrap.dedent(
                    f"""\
                    #!{sys.executable}
                    import os
                    import sys

                    if len(sys.argv) > 2 and sys.argv[2] == "install":
                        raise SystemExit(91)
                    os.execv({sys.executable!r}, [{sys.executable!r}, *sys.argv[1:]])
                    """
                ),
                encoding="utf-8",
            )
            python_wrapper.chmod(0o755)
            environment = os.environ.copy()
            environment.update(
                {
                    "LARK_CLI_BIN": str(fake_cli),
                    "PYTHON_BIN": str(python_wrapper),
                    "FEISHU_DATA_PARENT": str(data_parent),
                    "FEISHU_DATA_DIR": str(live),
                    "FEISHU_LAST_GOOD_DIR": str(last_good),
                    "FIXTURE_DIR": str(VALID),
                    "EARN10M_LOCK_DIR": str(root / "sync.lock"),
                }
            )

            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "sync-feishu.sh")],
                cwd=ROOT,
                env=environment,
                text=True,
                errors="replace",
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 91, result.stderr)
            self.assertIn("候选证据已保留", result.stderr)
            candidates = list(data_parent.glob(".feishu-candidate.*"))
            self.assertEqual(len(candidates), 1)
            self.assertEqual(tree_hash(candidates[0]), tree_hash(VALID))
            self.assertEqual(tree_hash(live), live_before)
            self.assertEqual(tree_hash(last_good), snapshot_before)
            self.assertFalse((root / "sync.lock").exists())

    def test_term_stops_delegated_sync_and_releases_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data_parent = root / "data"
            live = data_parent / "feishu"
            last_good = data_parent / ".feishu-last-good"
            fake_cli = root / "slow-lark-cli.py"
            marker = root / "cli-started"
            copy_valid(live)
            copy_valid(last_good)

            fake_cli.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import os
                    from pathlib import Path
                    import time

                    Path(os.environ["START_MARKER"]).write_text("started", encoding="utf-8")
                    time.sleep(30)
                    """
                ),
                encoding="utf-8",
            )
            fake_cli.chmod(0o755)
            lock = root / "sync.lock"
            environment = os.environ.copy()
            environment.update(
                {
                    "LARK_CLI_BIN": str(fake_cli),
                    "FEISHU_DATA_PARENT": str(data_parent),
                    "FEISHU_DATA_DIR": str(live),
                    "FEISHU_LAST_GOOD_DIR": str(last_good),
                    "START_MARKER": str(marker),
                    "EARN10M_LOCK_DIR": str(lock),
                }
            )
            process = subprocess.Popen(
                ["bash", str(ROOT / "scripts" / "auto-deploy.sh")],
                cwd=ROOT,
                env=environment,
                text=True,
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            try:
                for _ in range(200):
                    if marker.exists():
                        break
                    if process.poll() is not None:
                        break
                    time.sleep(0.01)
                self.assertTrue(marker.exists(), "fake CLI did not start")
                os.killpg(process.pid, signal.SIGTERM)
                stdout, stderr = process.communicate(timeout=5)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate(timeout=5)

            self.assertEqual(process.returncode, 143, stderr)
            self.assertNotIn("同步完成", stdout)
            self.assertFalse(lock.exists())
            self.assertEqual(list(data_parent.glob(".feishu-candidate.*")), [])

    def test_shell_refuses_a_live_shared_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = root / "sync.lock"
            lock.mkdir()
            (lock / "pid").write_text(str(os.getpid()), encoding="utf-8")
            environment = os.environ.copy()
            environment["EARN10M_LOCK_DIR"] = str(lock)

            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "sync-feishu.sh")],
                cwd=ROOT,
                env=environment,
                text=True,
                errors="replace",
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 75)
            self.assertIn("拒绝并发", result.stderr)

    def test_shell_preserves_pidless_and_dead_pid_locks(self) -> None:
        for label, pid_value in (("pidless", None), ("dead", "99999999")):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                lock = root / "sync.lock"
                lock.mkdir()
                if pid_value is not None:
                    (lock / "pid").write_text(pid_value, encoding="utf-8")
                environment = os.environ.copy()
                environment["EARN10M_LOCK_DIR"] = str(lock)

                result = subprocess.run(
                    ["bash", str(ROOT / "scripts" / "sync-feishu.sh")],
                    cwd=ROOT,
                    env=environment,
                    text=True,
                    errors="replace",
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 75)
                self.assertTrue(lock.exists())


if __name__ == "__main__":
    unittest.main()
