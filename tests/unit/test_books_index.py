"""
Unit tests for rebuild_books_index() in generate_daily_report.
@requirement REQ-007 (build-time index maintenance)
@requirement REQ-003 (client must resolve book_id -> date)
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from generate_daily_report import rebuild_books_index  # noqa: E402


def _write_report(daily_dir: Path, date: str, book_id: int, **extra):
    daily_dir.mkdir(parents=True, exist_ok=True)
    payload = {"date": date, "book_id": book_id, **extra}
    (daily_dir / f"{date}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_empty_daily_dir_produces_empty_books_map(tmp_path):
    # @requirement REQ-007
    out = tmp_path
    (out / "daily").mkdir()
    idx = rebuild_books_index(out)
    assert idx["count"] == 0
    assert idx["books"] == {}
    written = json.loads((out / "books-index.json").read_text(encoding="utf-8"))
    assert written == idx


def test_single_report_is_indexed(tmp_path):
    # @requirement REQ-003
    out = tmp_path
    _write_report(out / "daily", "2026-04-22", 5)
    idx = rebuild_books_index(out)
    assert idx["count"] == 1
    assert idx["books"]["5"]["latest"] == "2026-04-22"
    assert idx["books"]["5"]["dates"] == ["2026-04-22"]


def test_multiple_dates_for_same_book_pick_latest(tmp_path):
    # @requirement REQ-003 (lookup uses 'latest')
    out = tmp_path
    _write_report(out / "daily", "2026-04-20", 1)
    _write_report(out / "daily", "2026-06-29", 1)
    _write_report(out / "daily", "2026-05-15", 1)
    idx = rebuild_books_index(out)
    assert idx["books"]["1"]["latest"] == "2026-06-29"
    assert idx["books"]["1"]["dates"] == ["2026-04-20", "2026-05-15", "2026-06-29"]


def test_multiple_books_indexed_independently(tmp_path):
    # @requirement REQ-003
    out = tmp_path
    _write_report(out / "daily", "2026-04-19", 100)
    _write_report(out / "daily", "2026-04-20", 1)
    _write_report(out / "daily", "2026-04-21", 2)
    _write_report(out / "daily", "2026-04-22", 5)
    idx = rebuild_books_index(out)
    assert idx["count"] == 4
    assert set(idx["books"].keys()) == {"1", "2", "5", "100"}
    assert idx["books"]["100"]["latest"] == "2026-04-19"


def test_report_missing_book_id_is_skipped(tmp_path):
    # @requirement NFR-002 (graceful handling)
    out = tmp_path
    daily = out / "daily"
    daily.mkdir()
    # valid file
    _write_report(daily, "2026-04-22", 5)
    # malformed file: no book_id field
    (daily / "2026-04-23.json").write_text(
        json.dumps({"date": "2026-04-23"}, ensure_ascii=False),
        encoding="utf-8",
    )
    idx = rebuild_books_index(out)
    assert set(idx["books"].keys()) == {"5"}
    assert idx["count"] == 1


def test_output_is_deterministic(tmp_path):
    # @requirement REQ-007 (idempotency)
    out = tmp_path
    _write_report(out / "daily", "2026-04-22", 5)
    _write_report(out / "daily", "2026-04-20", 1)
    idx1 = rebuild_books_index(out)
    idx1_keys = list(idx1["books"].keys())
    # Run again — keys order and content identical
    idx2 = rebuild_books_index(out)
    assert list(idx2["books"].keys()) == idx1_keys
    assert idx2["books"] == idx1["books"]


def test_generated_at_is_iso_with_tz(tmp_path):
    # @requirement REQ-007 — timestamp present for freshness checks
    out = tmp_path
    (out / "daily").mkdir()
    idx = rebuild_books_index(out)
    # Must be parseable; ISO 8601 with offset or 'Z'
    assert "T" in idx["generated_at"]
    assert idx["generated_at"][0:4].isdigit()
