"""
Unit tests for external-book registration and indexing.

@requirement external recommendation can become a real report
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import generate_daily_report as gdr  # noqa: E402


@pytest.fixture
def temp_books(tmp_path, monkeypatch):
    """Point BOOKS_PATH at a writable tmp copy of the real catalog seed."""
    seed = [
        {"id": 1, "author": "Homer", "title": "The Iliad", "category": "Ancient Epic", "tradition": "Greek", "source_rank": 1},
        {"id": 2, "author": "Homer", "title": "The Odyssey", "category": "Ancient Epic", "tradition": "Greek", "source_rank": 1},
        {"id": 5, "author": "Herodotus", "title": "Histories", "category": "History", "tradition": "Greek", "source_rank": 1},
    ]
    books_path = tmp_path / "books.json"
    books_path.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(gdr, "BOOKS_PATH", books_path)
    return books_path


def test_add_external_book_appends_new_entry(temp_books):
    entry = gdr.add_external_book("Prometheus Bound", "Aeschylus")
    assert entry["id"] == 6  # max(1,2,5) + 1
    assert entry["source_rank"] == 4
    assert entry["author"] == "Aeschylus"
    stored = json.loads(temp_books.read_text(encoding="utf-8"))
    assert any(b["title"] == "Prometheus Bound" for b in stored)


def test_add_external_book_dedupes_case_and_whitespace(temp_books):
    first = gdr.add_external_book("Prometheus Bound", "Aeschylus")
    same = gdr.add_external_book("  prometheus  bound ", "AESCHYLUS")
    assert same["id"] == first["id"]
    # Only one new entry in the file
    stored = json.loads(temp_books.read_text(encoding="utf-8"))
    assert len([b for b in stored if b["title"] == "Prometheus Bound"]) == 1


def test_add_external_book_dedupes_against_curated_list(temp_books):
    # Curated list has Homer / The Iliad — must not create a duplicate
    same = gdr.add_external_book("The Iliad", "Homer")
    assert same["id"] == 1
    stored = json.loads(temp_books.read_text(encoding="utf-8"))
    assert len(stored) == 3  # unchanged


def test_add_external_book_rejects_empty(temp_books):
    with pytest.raises(ValueError):
        gdr.add_external_book("", "Author")
    with pytest.raises(ValueError):
        gdr.add_external_book("Title", "")


def test_load_books_excludes_external_by_default(temp_books):
    gdr.add_external_book("Prometheus Bound", "Aeschylus")
    rotation = gdr.load_books()
    full = gdr.load_books(include_external=True)
    assert len(rotation) == 3
    assert len(full) == 4
    assert all(b.get("source_rank", 3) <= 3 for b in rotation)


def test_date_for_external_book_resolves(temp_books, monkeypatch):
    monkeypatch.setattr(gdr, "START_DATE", "2026-04-20")
    entry = gdr.add_external_book("Prometheus Bound", "Aeschylus")
    # entry appended at index 3 (after ids 1,2,5) in full list
    d = gdr.date_for_book_id(entry["id"])
    assert d.isoformat() == "2026-04-23"  # start + 3 days


def test_rebuild_books_index_annotates_external(tmp_path, monkeypatch, temp_books):
    monkeypatch.setattr(gdr, "OUTPUT_DIR", tmp_path)
    # Register an external book and write a daily file for it
    entry = gdr.add_external_book("Prometheus Bound", "Aeschylus")
    daily = tmp_path / "daily"
    daily.mkdir()
    (daily / "2026-04-23.json").write_text(
        json.dumps({
            "date": "2026-04-23",
            "book_id": entry["id"],
            "title": "Prometheus Bound",
            "author": "Aeschylus",
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    # Also a curated-book daily file to confirm it DOES NOT get external flag
    (daily / "2026-04-22.json").write_text(
        json.dumps({"date": "2026-04-22", "book_id": 5, "title": "Histories", "author": "Herodotus"},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    idx = gdr.rebuild_books_index(tmp_path)
    ext_entry = idx["books"][str(entry["id"])]
    assert ext_entry.get("external") is True
    assert ext_entry["title_norm"] == "prometheus bound"
    assert ext_entry["author_norm"] == "aeschylus"
    # Curated book has no external flag
    curated = idx["books"]["5"]
    assert curated.get("external") is None


def test_generate_for_external_uses_canonical_date(tmp_path, monkeypatch, temp_books):
    monkeypatch.setattr(gdr, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(gdr, "START_DATE", "2026-04-20")

    captured = {}

    def fake_claude(prompt):
        captured["prompt_len"] = len(prompt)
        return {
            "date": "2026-04-23",
            "book_id": 6,
            "author": "Aeschylus",
            "title": "Prometheus Bound",
            "category": "Classic",
            "tradition": "Unknown",
            "source_rank": 4,
            "source_basis": "User-requested external recommendation",
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

    monkeypatch.setattr(gdr, "call_claude", fake_claude)
    report = gdr.generate_for_external("Prometheus Bound", "Aeschylus")
    assert report["book_id"] == 6
    assert report["date"] == "2026-04-23"
    assert (tmp_path / "daily" / "2026-04-23.json").exists()
    idx = json.loads((tmp_path / "books-index.json").read_text(encoding="utf-8"))
    assert "6" in idx["books"]
    assert idx["books"]["6"].get("external") is True
