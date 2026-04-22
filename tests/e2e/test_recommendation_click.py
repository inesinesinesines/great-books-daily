"""
E2E tests for Book Recommendation click-to-view feature.

Real http.server + real Playwright chromium + real data/daily/*.json.
No mocks, no stubs.

@requirement REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006
@requirement NFR-001, NFR-002, NFR-003, NFR-004
@requirement EDGE-001, EDGE-003, EDGE-005, EDGE-006
"""
import json
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _goto(page, base_url: str):
    page.goto(f"{base_url}/index.html", wait_until="networkidle")
    # Wait for today's title to be replaced with real content
    page.wait_for_function(
        "document.getElementById('titleText').textContent !== '오늘의 책을 불러오는 중'",
        timeout=10_000,
    )


def test_e2e_01_rec_items_are_clickable_ui(page, http_server):
    # @requirement REQ-001 @requirement NFR-004
    _goto(page, http_server)
    page.wait_for_selector("#recommendations .rec-item", state="visible", timeout=5000)
    items = page.locator("#recommendations .rec-item")
    assert items.count() >= 1
    first = items.first
    assert first.get_attribute("role") == "button"
    assert first.get_attribute("tabindex") == "0"
    assert first.get_attribute("data-book-id") is not None


def test_e2e_02_click_existing_report_renders_it(page, http_server):
    # @requirement REQ-002 @requirement REQ-003
    _goto(page, http_server)
    # Today's report (2026-04-22) recommends books including 7, 8, 12.
    # Book 1 (Homer/Iliad) has an actual report at 2026-04-20 — use that.
    # We'll locate an item whose book_id matches an indexed book. Use 2026-04-19 -> book 100.
    # Easier: navigate to 2026-04-19 first so the rec-items include books that ARE indexed.
    page.evaluate("loadDate('2026-04-19').then(render)")
    page.wait_for_function(
        "document.getElementById('dateText').textContent.startsWith('2026-04-19')",
        timeout=5000,
    )
    # The 2026-04-19 report recommends book_ids: 1, 2, 5 — all indexed.
    target = page.locator("#recommendations .rec-item[data-book-id='1']")
    assert target.count() == 1, "expected a recommendation for book 1 on 2026-04-19"
    target.click()
    # Wait for title to update to Iliad and date to be 2026-04-20
    page.wait_for_function(
        "document.getElementById('titleText').textContent.includes('Iliad')",
        timeout=5000,
    )
    date_text = page.text_content("#dateText")
    assert "2026-04-20" in date_text
    # Preview chip must be hidden for a real report
    assert page.locator("#previewChip").get_attribute("hidden") is not None


def test_e2e_03_click_missing_report_shows_preview(page, http_server):
    # @requirement REQ-004 @requirement EDGE-001
    _goto(page, http_server)
    # From today's report (book 5), recommendations include book 7, 8, 12 — none indexed.
    target = page.locator("#recommendations .rec-item[data-book-id='7']")
    assert target.count() == 1
    target.click()
    page.wait_for_selector("#previewChip:not([hidden])", timeout=5000)
    title = page.text_content("#titleText")
    assert title and title.strip() != "Histories"
    # Preview block must be visible and link to the generate workflow
    page.wait_for_selector("#previewBlock:not([hidden])", timeout=5000)
    notice = page.text_content("#previewNoticeText")
    assert "GitHub Actions" in notice
    href = page.get_attribute("#generateBtn", "href")
    assert href and "generate-book.yml" in href


def test_e2e_04_recommendations_remain_clickable_after_render(page, http_server):
    # @requirement REQ-006
    _goto(page, http_server)
    # First click: book 7 (preview)
    page.locator("#recommendations .rec-item[data-book-id='7']").click()
    page.wait_for_selector("#previewChip:not([hidden])", timeout=5000)
    # After preview render, rec list may be empty (preview has no next_recs) OR repopulated.
    # Navigate back to today to guarantee rec items present, then click another.
    page.click("#todayBtn")
    page.wait_for_function(
        "document.getElementById('titleText').textContent.includes('Histories')",
        timeout=5000,
    )
    # Click another recommendation (book 8)
    page.locator("#recommendations .rec-item[data-book-id='8']").click()
    page.wait_for_selector("#previewChip:not([hidden])", timeout=5000)


def test_e2e_05_keyboard_enter_activates_rec(page, http_server):
    # @requirement NFR-004
    _goto(page, http_server)
    item = page.locator("#recommendations .rec-item[data-book-id='7']")
    item.focus()
    page.keyboard.press("Enter")
    page.wait_for_selector("#previewChip:not([hidden])", timeout=5000)


def test_e2e_06_today_button_restores_today_report(page, http_server):
    # @requirement EDGE-006 @requirement REQ-005
    _goto(page, http_server)
    original_title = page.text_content("#titleText")
    page.locator("#recommendations .rec-item[data-book-id='7']").click()
    page.wait_for_selector("#previewChip:not([hidden])", timeout=5000)
    page.click("#todayBtn")
    page.wait_for_function(
        f"document.getElementById('titleText').textContent === {json.dumps(original_title)}",
        timeout=5000,
    )
    assert page.locator("#previewChip").get_attribute("hidden") is not None


def test_e2e_07_no_api_key_exposed(page, http_server):
    # @requirement NFR-003
    _goto(page, http_server)
    # Read the rendered HTML source from the server — must not contain any ANTHROPIC_API_KEY literal.
    import urllib.request
    body = urllib.request.urlopen(f"{http_server}/index.html").read().decode("utf-8")
    assert "ANTHROPIC_API_KEY" not in body
    assert "sk-ant" not in body


def test_e2e_08_rapid_clicks_render_only_last(page, http_server):
    # @requirement EDGE-003
    _goto(page, http_server)
    # Fire both loadBookReport calls within the same microtask so the in-flight
    # guard has to arbitrate — last token wins. We cannot click twice via UI
    # because the first click rerenders recommendations, detaching the second
    # target from the DOM; the race we care about is the clickToken mechanism,
    # so we exercise it at the JS layer directly.
    page.evaluate("loadBookReport(7); loadBookReport(12);")
    page.wait_for_selector("#previewChip:not([hidden])", timeout=5000)
    # Wait for the title to settle on book 12 (Plato / Apology)
    page.wait_for_function(
        "document.getElementById('titleText').textContent.includes('Apology')",
        timeout=5000,
    )
    title = page.text_content("#titleText")
    assert "Apology" in title
