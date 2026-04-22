"""
Integration test: save_report -> filesystem -> rebuild_books_index -> books-index.json

Exercises the real filesystem with multiple save_report invocations and asserts
the on-disk books-index.json matches expectations. No mocks.

@requirement REQ-007, REQ-003
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import generate_daily_report as gdr  # noqa: E402


def _payload(date: str, book_id: int) -> dict:
    return {
        "date": date,
        "book_id": book_id,
        "author": "A",
        "title": "T",
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


def test_multiple_save_reports_yield_correct_index(tmp_path, monkeypatch):
    monkeypatch.setattr(gdr, "OUTPUT_DIR", tmp_path)

    gdr.save_report(_payload("2026-04-19", 100), update_today=False)
    gdr.save_report(_payload("2026-04-20", 1), update_today=False)
    gdr.save_report(_payload("2026-04-21", 2), update_today=False)
    gdr.save_report(_payload("2026-04-22", 5), update_today=True)

    # Daily files present
    for d in ("2026-04-19", "2026-04-20", "2026-04-21", "2026-04-22"):
        assert (tmp_path / "daily" / f"{d}.json").exists(), f"missing {d}"

    # today.json reflects last save
    today = json.loads((tmp_path / "today.json").read_text(encoding="utf-8"))
    assert today["book_id"] == 5

    # books-index.json is consistent
    idx = json.loads((tmp_path / "books-index.json").read_text(encoding="utf-8"))
    assert idx["count"] == 4
    assert idx["books"]["1"]["latest"] == "2026-04-20"
    assert idx["books"]["2"]["latest"] == "2026-04-21"
    assert idx["books"]["5"]["latest"] == "2026-04-22"
    assert idx["books"]["100"]["latest"] == "2026-04-19"

    # After a re-save for same book with a newer date, latest updates
    gdr.save_report(_payload("2026-06-15", 1), update_today=False)
    idx2 = json.loads((tmp_path / "books-index.json").read_text(encoding="utf-8"))
    assert idx2["books"]["1"]["latest"] == "2026-06-15"
    assert idx2["books"]["1"]["dates"] == ["2026-04-20", "2026-06-15"]
