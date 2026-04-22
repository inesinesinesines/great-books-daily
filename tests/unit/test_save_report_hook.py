"""
Unit tests for save_report() integration with rebuild_books_index().
@requirement REQ-007 (save_report must refresh books-index.json)
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import generate_daily_report as gdr  # noqa: E402


@pytest.fixture
def tmp_output(tmp_path, monkeypatch):
    """Redirect OUTPUT_DIR to a tmp path for the duration of the test."""
    monkeypatch.setattr(gdr, "OUTPUT_DIR", tmp_path)
    return tmp_path


def _make_report(date: str, book_id: int) -> dict:
    return {
        "date": date,
        "book_id": book_id,
        "author": "X",
        "title": "Y",
        "category": "c",
        "tradition": "t",
        "source_rank": 1,
        "source_basis": "b",
        "reading_mode": "ranked",
        "one_line": "o",
        "summary": ["s"],
        "keywords": ["k"],
        "why_now": "w",
        "discussion_question": "q",
        "perplexity_followup_prompt": "p",
        "next_recommendations": [],
        "source_note": "n",
    }


def test_save_report_writes_books_index(tmp_output):
    # @requirement REQ-007
    gdr.save_report(_make_report("2026-04-22", 5), update_today=False)
    idx_path = tmp_output / "books-index.json"
    assert idx_path.exists(), "books-index.json must be created by save_report"
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    assert "5" in idx["books"]
    assert idx["books"]["5"]["latest"] == "2026-04-22"


def test_save_report_updates_existing_index(tmp_output):
    # @requirement REQ-007
    gdr.save_report(_make_report("2026-04-20", 1), update_today=False)
    gdr.save_report(_make_report("2026-04-22", 5), update_today=False)
    idx = json.loads((tmp_output / "books-index.json").read_text(encoding="utf-8"))
    assert set(idx["books"].keys()) == {"1", "5"}
    assert idx["books"]["1"]["latest"] == "2026-04-20"
    assert idx["books"]["5"]["latest"] == "2026-04-22"


def test_save_report_preserves_today_json_behavior(tmp_output):
    # @requirement REQ-005 (no regression)
    gdr.save_report(_make_report("2026-04-22", 5), update_today=True)
    today = json.loads((tmp_output / "today.json").read_text(encoding="utf-8"))
    assert today["book_id"] == 5
    assert (tmp_output / "daily" / "2026-04-22.json").exists()
    # And index still built
    assert (tmp_output / "books-index.json").exists()
