#!/usr/bin/env python3
"""Validate and atomically install the public Feishu export set.

The module intentionally uses only the Python standard library so the safety
gate can run before npm dependencies are installed.  It never contacts Feishu;
network export remains the responsibility of ``sync-feishu.sh``.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Iterable


REQUIRED_EXPORTS = ("logs.json", "finance.json", "business.json", "content.json")
EXPECTED_FIELDS = {
    "logs.json": {"日期", "正文", "心情", "摘要", "标签", "标题"},
    "finance.json": {"月份", "净资产", "支出", "收入", "负债"},
    "business.json": {"名称", "状态", "累计收入", "标签", "启动日期", "描述"},
    "content.json": {"日期", "标题", "点赞数", "阅读量", "平台", "链接"},
}
MAX_EXPORT_BYTES = 16 * 1024 * 1024
DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}(?:\s|T|$)")
MONTH = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])$")


class ValidationError(ValueError):
    """An export cannot be trusted as the public data snapshot."""


@dataclass(frozen=True)
class ExportSummary:
    file_hashes: dict[str, str]
    record_counts: dict[str, int]

    @property
    def total_records(self) -> int:
        return sum(self.record_counts.values())


def _fail(path: pathlib.Path, message: str) -> None:
    raise ValidationError(f"{path.name}: {message}")


def _reject_nonstandard_number(value: str) -> None:
    raise ValueError(f"non-standard JSON number: {value}")


def _load_json(path: pathlib.Path) -> Any:
    try:
        size = path.stat().st_size
    except FileNotFoundError as exc:
        raise ValidationError(f"缺少必需导出文件: {path.name}") from exc
    if size == 0:
        _fail(path, "文件为空")
    if size > MAX_EXPORT_BYTES:
        _fail(path, f"文件超过 {MAX_EXPORT_BYTES} 字节安全上限")
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle, parse_constant=_reject_nonstandard_number)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        _fail(path, f"不是严格 JSON（{exc}）")


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _require_text(path: pathlib.Path, field: str, value: object, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        _fail(path, f"字段“{field}”必须是字符串")
    if not allow_empty and not value.strip():
        _fail(path, f"字段“{field}”不能为空")
    return value


def _row_objects(path: pathlib.Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, dict):
        _fail(path, "data 必须是对象")

    fields = data.get("fields")
    rows = data.get("data")
    record_ids = data.get("record_id_list")
    field_ids = data.get("field_id_list")

    if not isinstance(fields, list) or not fields or not all(isinstance(item, str) and item for item in fields):
        _fail(path, "data.fields 必须是非空字符串数组")
    if len(fields) != len(set(fields)):
        _fail(path, "data.fields 含重复字段")
    if set(fields) != EXPECTED_FIELDS[path.name]:
        missing = sorted(EXPECTED_FIELDS[path.name] - set(fields))
        extra = sorted(set(fields) - EXPECTED_FIELDS[path.name])
        _fail(path, f"公开字段白名单不匹配，缺少={missing}，多出={extra}")
    if not isinstance(field_ids, list) or len(field_ids) != len(fields):
        _fail(path, "data.field_id_list 必须与 fields 等长")
    if not all(isinstance(item, str) and item for item in field_ids):
        _fail(path, "data.field_id_list 必须只含非空字符串")
    if not isinstance(rows, list):
        _fail(path, "data.data 必须是记录数组")
    if len(rows) > 200:
        _fail(path, "单次导出记录数超过脚本上限 200")
    if not isinstance(record_ids, list) or len(record_ids) != len(rows):
        _fail(path, "data.record_id_list 必须与记录数一致")
    if not all(isinstance(item, str) and item for item in record_ids):
        _fail(path, "record_id 必须是非空字符串")
    if len(record_ids) != len(set(record_ids)):
        _fail(path, "record_id 不能重复")
    if data.get("has_more") is not False:
        _fail(path, "has_more 必须为 false；拒绝安装不完整分页")

    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != len(fields):
            _fail(path, f"第 {index + 1} 行必须是与 fields 等长的数组")
        result.append(dict(zip(fields, row)))
    return result


def _validate_logs(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    seen_dates: set[str] = set()
    for row in rows:
        date = _require_text(path, "日期", row["日期"])
        if not DATE_PREFIX.match(date):
            _fail(path, f"日期格式无效: {date!r}")
        day = date[:10]
        if day in seen_dates:
            _fail(path, f"日期重复会造成日志 slug 冲突: {day}")
        seen_dates.add(day)
        _require_text(path, "标题", row["标题"])
        _require_text(path, "正文", row["正文"])
        for field in ("摘要", "标签"):
            if row[field] is not None and not isinstance(row[field], str):
                _fail(path, f"字段“{field}”只能是字符串或 null")
        mood = row["心情"]
        if not (
            isinstance(mood, str)
            or (isinstance(mood, list) and all(isinstance(item, str) for item in mood))
            or mood is None
        ):
            _fail(path, "字段“心情”必须是字符串、字符串数组或 null")


def _validate_finance(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        _fail(path, "财务导出至少需要一条记录")
    seen_months: set[str] = set()
    for row in rows:
        month = _require_text(path, "月份", row["月份"])
        if not MONTH.match(month):
            _fail(path, f"月份格式无效: {month!r}")
        if month in seen_months:
            _fail(path, f"月份重复: {month}")
        seen_months.add(month)
        for field in ("净资产", "支出", "收入", "负债"):
            if not _is_number(row[field]):
                _fail(path, f"字段“{field}”必须是有限数值")


def _validate_business(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    seen_names: set[str] = set()
    for row in rows:
        name = _require_text(path, "名称", row["名称"])
        if name in seen_names:
            _fail(path, f"业务线名称重复: {name}")
        seen_names.add(name)
        if not _is_number(row["累计收入"]):
            _fail(path, "字段“累计收入”必须是有限数值")
        start_date = _require_text(path, "启动日期", row["启动日期"])
        if not DATE_PREFIX.match(start_date):
            _fail(path, f"启动日期格式无效: {start_date!r}")
        status = row["状态"]
        if not (
            isinstance(status, str) and status.strip()
            or isinstance(status, list) and status and all(isinstance(item, str) and item.strip() for item in status)
        ):
            _fail(path, "字段“状态”必须是非空字符串或非空字符串数组")
        for field in ("标签", "描述"):
            if row[field] is not None and not isinstance(row[field], str):
                _fail(path, f"字段“{field}”只能是字符串或 null")


def _validate_content(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        date = _require_text(path, "日期", row["日期"])
        if not DATE_PREFIX.match(date):
            _fail(path, f"日期格式无效: {date!r}")
        _require_text(path, "标题", row["标题"])
        _require_text(path, "平台", row["平台"])
        _require_text(path, "链接", row["链接"])
        for field in ("点赞数", "阅读量"):
            if not _is_number(row[field]) or row[field] < 0:
                _fail(path, f"字段“{field}”必须是非负有限数值")


VALIDATORS = {
    "logs.json": _validate_logs,
    "finance.json": _validate_finance,
    "business.json": _validate_business,
    "content.json": _validate_content,
}


def quarantine_incomplete_logs(directory: os.PathLike[str] | str) -> int:
    """Remove incomplete log drafts from a staging export before validation."""

    root = pathlib.Path(directory)
    path = root / "logs.json"
    payload = _load_json(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        _fail(path, "data 必须是对象")
    data = payload["data"]
    fields = data.get("fields")
    rows = data.get("data")
    record_ids = data.get("record_id_list")
    if not isinstance(fields, list) or not isinstance(rows, list):
        _fail(path, "无法识别日志候选结构")
    if not isinstance(record_ids, list) or len(record_ids) != len(rows):
        _fail(path, "日志记录 ID 与行数不一致")
    try:
        title_index = fields.index("标题")
        content_index = fields.index("正文")
    except ValueError:
        _fail(path, "日志缺少标题或正文字段")

    kept_rows: list[Any] = []
    kept_ids: list[Any] = []
    for row, record_id in zip(rows, record_ids):
        if not isinstance(row, list) or len(row) != len(fields):
            _fail(path, "日志行列数不一致")
        title = row[title_index]
        content = row[content_index]
        publishable = (
            isinstance(title, str)
            and bool(title.strip())
            and isinstance(content, str)
            and bool(content.strip())
        )
        if publishable:
            kept_rows.append(row)
            kept_ids.append(record_id)

    removed = len(rows) - len(kept_rows)
    if not removed:
        return 0
    data["data"] = kept_rows
    data["record_id_list"] = kept_ids
    query_context = data.get("query_context")
    if isinstance(query_context, dict) and isinstance(query_context.get("count"), int):
        query_context["count"] = len(kept_rows)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _fsync_path(temporary)
        os.replace(temporary, path)
        _fsync_path(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()
    return removed


def validate_export_directory(directory: os.PathLike[str] | str) -> ExportSummary:
    root = pathlib.Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ValidationError(f"导出路径不是普通目录: {root}")

    present_json = {path.name for path in root.glob("*.json")}
    required = set(REQUIRED_EXPORTS)
    if present_json != required:
        raise ValidationError(
            f"导出文件集合不匹配，缺少={sorted(required - present_json)}，多出={sorted(present_json - required)}"
        )

    hashes: dict[str, str] = {}
    counts: dict[str, int] = {}
    for filename in REQUIRED_EXPORTS:
        path = root / filename
        payload = _load_json(path)
        if not isinstance(payload, dict):
            _fail(path, "JSON 顶层必须是对象")
        if payload.get("ok") is not True:
            _fail(path, "ok 必须严格为 true")
        if payload.get("identity") not in {"user", "bot"}:
            _fail(path, "identity 必须是 user 或 bot")
        rows = _row_objects(path, payload)
        VALIDATORS[filename](path, rows)
        hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        counts[filename] = len(rows)
    return ExportSummary(hashes, counts)


def _fsync_path(path: pathlib.Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY") and path.is_dir():
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if exc.errno in {errno.EINVAL, errno.ENOTSUP}:
            return
        raise
    try:
        os.fsync(descriptor)
    except OSError as exc:
        if exc.errno not in {errno.EINVAL, errno.ENOTSUP}:
            raise
    finally:
        os.close(descriptor)


def _fsync_tree(directory: pathlib.Path) -> None:
    for filename in REQUIRED_EXPORTS:
        _fsync_path(directory / filename)
    _fsync_path(directory)


def _same_filesystem(paths: Iterable[pathlib.Path]) -> None:
    devices = {path.stat().st_dev for path in paths}
    if len(devices) != 1:
        raise RuntimeError("候选、正式目录与快照目录必须位于同一文件系统")


def _platform_exchange(left: pathlib.Path, right: pathlib.Path) -> None:
    if left.is_symlink() or right.is_symlink() or not left.is_dir() or not right.is_dir():
        raise RuntimeError("原子交换只接受两个普通目录")
    _same_filesystem((left, right))
    libc = ctypes.CDLL(None, use_errno=True)
    left_bytes = os.fsencode(left)
    right_bytes = os.fsencode(right)

    if sys.platform == "darwin":
        function = getattr(libc, "renameatx_np", None)
        at_fdcwd = -2
    elif sys.platform.startswith("linux"):
        function = getattr(libc, "renameat2", None)
        at_fdcwd = -100
    else:
        function = None
        at_fdcwd = 0

    if function is None:
        raise RuntimeError(f"当前平台 {sys.platform!r} 不支持安全的目录原子交换")
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    if function(at_fdcwd, left_bytes, at_fdcwd, right_bytes, 0x00000002) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), f"{left} <-> {right}")


def atomic_exchange_directories(left: pathlib.Path, right: pathlib.Path) -> None:
    """Atomically exchange two directories and roll back fsync failures."""

    _platform_exchange(left, right)
    try:
        _fsync_path(left.parent)
        if right.parent != left.parent:
            _fsync_path(right.parent)
    except OSError as exc:
        try:
            _platform_exchange(left, right)
        except Exception as rollback_exc:
            raise RuntimeError(
                "目录已交换但持久化失败，自动回滚也失败；需要人工恢复"
            ) from rollback_exc
        raise RuntimeError("目录交换持久化失败，已自动回滚") from exc


def _copy_export_set(source: pathlib.Path, parent: pathlib.Path, prefix: str) -> pathlib.Path:
    parent.mkdir(parents=True, exist_ok=True)
    candidate = pathlib.Path(tempfile.mkdtemp(prefix=prefix, dir=parent))
    candidate.chmod(0o700)
    try:
        for filename in REQUIRED_EXPORTS:
            destination = candidate / filename
            shutil.copy2(source / filename, destination)
            destination.chmod(0o600)
        validate_export_directory(candidate)
        _fsync_tree(candidate)
        return candidate
    except Exception:
        shutil.rmtree(candidate, ignore_errors=True)
        raise


def _replace_snapshot(source: pathlib.Path, snapshot: pathlib.Path) -> None:
    candidate = _copy_export_set(source, snapshot.parent, ".feishu-snapshot-candidate.")
    try:
        if snapshot.exists():
            atomic_exchange_directories(candidate, snapshot)
            shutil.rmtree(candidate, ignore_errors=True)
        else:
            os.replace(candidate, snapshot)
            try:
                _fsync_path(snapshot.parent)
            except OSError:
                os.replace(snapshot, candidate)
                raise
    except Exception:
        if candidate.exists():
            shutil.rmtree(candidate, ignore_errors=True)
        raise


def _directory_is_valid(directory: pathlib.Path) -> bool:
    try:
        validate_export_directory(directory)
        return True
    except (OSError, ValidationError):
        return False


def install_exports(
    source: os.PathLike[str] | str,
    live: os.PathLike[str] | str,
    last_good: os.PathLike[str] | str,
) -> ExportSummary:
    source_path = pathlib.Path(source).absolute()
    live_path = pathlib.Path(live).absolute()
    snapshot_path = pathlib.Path(last_good).absolute()
    summary = validate_export_directory(source_path)

    live_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    filesystem_anchors = [source_path, live_path.parent, snapshot_path.parent]
    if live_path.exists():
        filesystem_anchors.append(live_path)
    _same_filesystem(filesystem_anchors)
    _fsync_tree(source_path)

    live_existed = live_path.exists()
    live_was_valid = live_existed and _directory_is_valid(live_path)
    snapshot_is_valid = snapshot_path.exists() and _directory_is_valid(snapshot_path)

    exchanged = False
    if live_existed:
        if live_path.is_symlink() or not live_path.is_dir():
            raise RuntimeError(f"正式数据路径不是普通目录: {live_path}")
        atomic_exchange_directories(source_path, live_path)
        exchanged = True
    else:
        os.replace(source_path, live_path)
        try:
            _fsync_path(live_path.parent)
        except OSError:
            os.replace(live_path, source_path)
            raise

    try:
        # Verify the bytes readers will consume after the switch before the old
        # live directory or candidate evidence is removed.
        installed = validate_export_directory(live_path)
        if installed.file_hashes != summary.file_hashes:
            raise RuntimeError("原子切换后的正式数据 hash 与候选不一致")

        # Commit the recovery point only after post-switch verification.  If
        # this step fails, the live exchange is rolled back below.
        if live_was_valid:
            _replace_snapshot(source_path, snapshot_path)
        elif not snapshot_is_valid:
            _replace_snapshot(live_path, snapshot_path)
    except Exception:
        try:
            if exchanged:
                atomic_exchange_directories(source_path, live_path)
            elif live_path.exists() and not source_path.exists():
                os.replace(live_path, source_path)
                _fsync_path(source_path.parent)
        except Exception as rollback_exc:
            raise RuntimeError(
                "安装失败且 live 自动回滚失败；候选与恢复快照已保留"
            ) from rollback_exc
        raise

    # Cleanup is not part of the commit decision. A cleanup failure must not
    # turn a verified, recoverable installation into an ambiguous failure.
    if source_path.exists():
        shutil.rmtree(source_path, ignore_errors=True)
    return installed


def restore_last_good(
    live: os.PathLike[str] | str,
    last_good: os.PathLike[str] | str,
    rescue: os.PathLike[str] | str | None = None,
) -> ExportSummary:
    live_path = pathlib.Path(live).absolute()
    snapshot_path = pathlib.Path(last_good).absolute()
    summary = validate_export_directory(snapshot_path)
    candidate = _copy_export_set(snapshot_path, live_path.parent, ".feishu-restore-candidate.")
    rescue_path = pathlib.Path(rescue).absolute() if rescue is not None else None
    live_was_valid = live_path.exists() and _directory_is_valid(live_path)
    exchanged = False
    try:
        if live_path.exists():
            if live_path.is_symlink() or not live_path.is_dir():
                raise RuntimeError(f"正式数据路径不是普通目录: {live_path}")
            atomic_exchange_directories(candidate, live_path)
            exchanged = True
        else:
            os.replace(candidate, live_path)
            try:
                _fsync_path(live_path.parent)
            except OSError:
                os.replace(live_path, candidate)
                raise
        restored = validate_export_directory(live_path)
        if restored.file_hashes != summary.file_hashes:
            raise RuntimeError("恢复后的正式数据 hash 与 last-good 不一致")
        if rescue_path is not None and live_was_valid and candidate.exists():
            rescue_path.parent.mkdir(parents=True, exist_ok=True)
            _replace_snapshot(candidate, rescue_path)
    except Exception:
        try:
            if exchanged:
                atomic_exchange_directories(candidate, live_path)
            elif live_path.exists() and not candidate.exists():
                os.replace(live_path, candidate)
                _fsync_path(candidate.parent)
        except Exception as rollback_exc:
            raise RuntimeError("恢复失败且 live 自动回滚失败") from rollback_exc
        raise
    if candidate.exists():
        shutil.rmtree(candidate, ignore_errors=True)
    return restored


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="校验一个完整导出目录")
    validate_parser.add_argument("--source", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare", help="从候选目录隔离不完整日志草稿"
    )
    prepare_parser.add_argument("--source", required=True)

    install_parser = subparsers.add_parser("install", help="校验并原子安装候选导出")
    install_parser.add_argument("--source", required=True)
    install_parser.add_argument("--live", required=True)
    install_parser.add_argument("--last-good", required=True)

    restore_parser = subparsers.add_parser("restore", help="从 last-good 恢复正式数据")
    restore_parser.add_argument("--live", required=True)
    restore_parser.add_argument("--last-good", required=True)
    restore_parser.add_argument("--rescue")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            summary = validate_export_directory(args.source)
            action = "已验证"
        elif args.command == "prepare":
            removed = quarantine_incomplete_logs(args.source)
            print(f"已隔离 {removed} 条不完整日志草稿")
            return 0
        elif args.command == "install":
            summary = install_exports(args.source, args.live, args.last_good)
            action = "已原子安装"
        else:
            summary = restore_last_good(args.live, args.last_good, args.rescue)
            action = "已恢复"
    except (OSError, RuntimeError, ValidationError) as exc:
        print(f"飞书数据门禁失败: {exc}", file=sys.stderr)
        return 1
    print(f"{action} {len(summary.file_hashes)} 个文件，共 {summary.total_records} 条记录")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
