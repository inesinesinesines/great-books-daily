"""
Unit tests for the skip-if-exists policy in generate_for_date.

Verifies option C behavior: existing daily files are reused (no Claude call)
unless --force is set. today.json and the books index stay consistent.

@requirement dedup — avoid duplicate Claude calls when a date's report exists
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
    monkeypatch.setattr(gdr, "OUTPUT_DIR", tmp_path)
    return tmp_path


def _fake_report(date_str: str, book_id: int, author="A") -> dict:
    return {
        "date": date_str,
        "book_id": book_id,
        "author": author,
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


def _install_existing(tmp_output, date_str, payload):
    daily = tmp_output / "daily"
    daily.mkdir(parents=True, exist_ok=True)
    (daily / f"{date_str}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def test_skip_reuses_existing_report_without_claude(tmp_output, monkeypatch):
    original = _fake_report("2026-04-22", 5, author="Herodotus-original")
    _install_existing(tmp_output, "2026-04-22", original)

    calls = {"claude": 0}

    def explode(*_a, **_kw):
        calls["claude"] += 1
        raise AssertionError("Claude must not be called when report exists and force is False")

    monkeypatch.setattr(gdr, "call_claude", explode)

    from datetime import date as date_cls
    result = gdr.generate_for_date(date_cls(2026, 4, 22), update_today=False, force=False)

    assert calls["claude"] == 0
    assert result["author"] == "Herodotus-original"
    # File is untouched
    stored = json.loads((tmp_output / "daily" / "2026-04-22.json").read_text(encoding="utf-8"))
    assert stored["author"] == "Herodotus-original"


def test_skip_still_refreshes_today_and_index(tmp_output, monkeypatch):
    original = _fake_report("2026-04-22", 5)
    _install_existing(tmp_output, "2026-04-22", original)

    monkeypatch.setattr(gdr, "call_claude", lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("Claude should not be called")))

    from datetime import date as date_cls
    gdr.generate_for_date(date_cls(2026, 4, 22), update_today=True, force=False)

    # today.json updated
    today = json.loads((tmp_output / "today.json").read_text(encoding="utf-8"))
    assert today["date"] == "2026-04-22"
    # Index built
    idx = json.loads((tmp_output / "books-index.json").read_text(encoding="utf-8"))
    assert "5" in idx["books"]


def test_force_overwrites_existing_with_new_claude_call(tmp_output, monkeypatch):
    existing = _fake_report("2026-04-22", 5, author="old-author")
    _install_existing(tmp_output, "2026-04-22", existing)

    new_report = _fake_report("2026-04-22", 5, author="new-author-from-claude")
    claude_calls = []

    def fake_claude(prompt):
        claude_calls.append(prompt[:40])
        return new_report

    monkeypatch.setattr(gdr, "call_claude", fake_claude)

    from datetime import date as date_cls
    result = gdr.generate_for_date(date_cls(2026, 4, 22), update_today=False, force=True)

    assert len(claude_calls) == 1
    assert result["author"] == "new-author-from-claude"
    stored = json.loads((tmp_output / "daily" / "2026-04-22.json").read_text(encoding="utf-8"))
    assert stored["author"] == "new-author-from-claude"


def test_missing_file_still_calls_claude(tmp_output, monkeypatch):
    # No pre-existing file → Claude must run
    new_report = _fake_report("2026-04-22", 5, author="claude-authored")
    claude_calls = []

    def fake_claude(prompt):
        claude_calls.append(1)
        return new_report

    monkeypatch.setattr(gdr, "call_claude", fake_claude)

    from datetime import date as date_cls
    gdr.generate_for_date(date_cls(2026, 4, 22), update_today=False, force=False)

    assert len(claude_calls) == 1
    stored = json.loads((tmp_output / "daily" / "2026-04-22.json").read_text(encoding="utf-8"))
    assert stored["author"] == "claude-authored"


def test_main_accepts_force_flag(tmp_output, monkeypatch):
    existing = _fake_report("2026-04-22", 5, author="prev")
    _install_existing(tmp_output, "2026-04-22", existing)

    call_log = []
    monkeypatch.setattr(gdr, "call_claude", lambda p: (call_log.append(1), _fake_report("2026-04-22", 5, author="new"))[1])
    monkeypatch.setattr(sys, "argv", ["generate_daily_report.py", "2026-04-22", "--force"])

    gdr.main()
    assert len(call_log) == 1


def test_main_without_force_reuses(tmp_output, monkeypatch):
    existing = _fake_report("2026-04-22", 5, author="prev")
    _install_existing(tmp_output, "2026-04-22", existing)

    def fail(*a, **kw):
        raise AssertionError("Claude must not run when file exists and --force absent")

    monkeypatch.setattr(gdr, "call_claude", fail)
    monkeypatch.setattr(sys, "argv", ["generate_daily_report.py", "2026-04-22"])

    gdr.main()  # Should not raise
