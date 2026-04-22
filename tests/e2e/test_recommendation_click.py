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


def _goto(page, base_url: str, disable_worker: bool = False):
    page.goto(f"{base_url}/index.html", wait_until="networkidle")
    # Wait for today's title to be replaced with real content
    page.wait_for_function(
        "document.getElementById('titleText').textContent !== '오늘의 책을 불러오는 중'",
        timeout=10_000,
    )
    if disable_worker:
        # Exercise the preview fallback branch by disabling the Worker URL.
        # This is not a mock — it's the real code path for a missing Worker.
        page.evaluate("WORKER_URL = '';")


def _pick_unindexed_rec_ids(page, count: int = 1):
    """Return book_ids from the current recommendations that are NOT in
    books-index.json. Tests use these to exercise the "missing report" path
    without depending on a static data snapshot (the index grows over time)."""
    ids = page.evaluate(
        """(async () => {
          const idx = await getBooksIndex();
          const indexed = new Set(idx && idx.books ? Object.keys(idx.books).map(k => parseInt(k)) : []);
          return Array.from(document.querySelectorAll('#recommendations .rec-item'))
            .map(el => parseInt(el.getAttribute('data-book-id')))
            .filter(id => Number.isFinite(id) && !indexed.has(id));
        })()"""
    )
    if len(ids) < count:
        pytest.skip(
            f"E2E requires {count} unindexed recommendation(s); current page has {len(ids)}"
        )
    return ids[:count]


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
    # Disables Worker to exercise preview fallback branch (real code, not a mock).
    _goto(page, http_server, disable_worker=True)
    bid = _pick_unindexed_rec_ids(page, 1)[0]
    target = page.locator(f"#recommendations .rec-item[data-book-id='{bid}']")
    assert target.count() == 1
    target.click()
    page.wait_for_selector("#previewChip:not([hidden])", timeout=5000)
    title = page.text_content("#titleText")
    assert title and title.strip() != ""
    # Preview block must be visible and link to the generate workflow
    page.wait_for_selector("#previewBlock:not([hidden])", timeout=5000)
    notice = page.text_content("#previewNoticeText")
    assert "GitHub Actions" in notice
    href = page.get_attribute("#generateBtn", "href")
    assert href and "generate-book.yml" in href


def test_e2e_03b_click_missing_report_with_worker_shows_generating_state(page, http_server):
    # @requirement REQ-004 (new Worker-driven flow)
    # Dispatch to loopback:1 fails in <50ms, so the generating DOM state is
    # too transient for a post-hoc selector check. Instead we instrument the
    # real render() function to capture DOM state at every invocation —
    # this is observation, not mocking (render still runs normally).
    _goto(page, http_server)
    page.evaluate("WORKER_URL = 'http://127.0.0.1:1';")
    bid = _pick_unindexed_rec_ids(page, 1)[0]
    calls = page.evaluate(
        f"""(async () => {{
          window.__calls = [];
          const orig = window.render;
          window.render = function(d){{
            const r = orig(d);
            window.__calls.push({{
              generating: !!d.generating,
              previewFlag: !!d.generated_client_side,
              title: d.title,
              chipVisible: !document.getElementById('generatingChip').hidden,
              blockVisible: !document.getElementById('generatingBlock').hidden,
              summaryAllHidden: Array.from(document.querySelectorAll('#summaryArea .summary-block')).every(el => el.hidden)
            }});
            return r;
          }};
          loadBookReport({bid});
          await new Promise(r => setTimeout(r, 400));
          return window.__calls;
        }})()"""
    )
    # Expect exactly: first a generating render, then a fallback preview render
    generating = [c for c in calls if c["generating"]]
    preview = [c for c in calls if c["previewFlag"] and not c["generating"]]
    assert len(generating) >= 1, f"no generating render observed. calls={calls}"
    assert generating[0]["chipVisible"] is True
    assert generating[0]["blockVisible"] is True
    assert generating[0]["summaryAllHidden"] is True
    assert len(preview) >= 1, f"no fallback preview render observed. calls={calls}"
    # And the final DOM settles on preview visible
    page.wait_for_selector("#previewBlock:not([hidden])", timeout=5000)


def test_e2e_04_recommendations_remain_clickable_after_render(page, http_server):
    # @requirement REQ-006
    _goto(page, http_server, disable_worker=True)
    bids = _pick_unindexed_rec_ids(page, 2)
    page.locator(f"#recommendations .rec-item[data-book-id='{bids[0]}']").click()
    page.wait_for_selector("#previewChip:not([hidden])", timeout=5000)
    # Navigate back to today to guarantee rec items present, then click another.
    page.click("#todayBtn")
    page.wait_for_function(
        "document.getElementById('titleText').textContent.includes('Histories')",
        timeout=5000,
    )
    page.locator(f"#recommendations .rec-item[data-book-id='{bids[1]}']").click()
    page.wait_for_selector("#previewChip:not([hidden])", timeout=5000)


def test_e2e_05_keyboard_enter_activates_rec(page, http_server):
    # @requirement NFR-004
    _goto(page, http_server, disable_worker=True)
    bid = _pick_unindexed_rec_ids(page, 1)[0]
    item = page.locator(f"#recommendations .rec-item[data-book-id='{bid}']")
    item.focus()
    page.keyboard.press("Enter")
    page.wait_for_selector("#previewChip:not([hidden])", timeout=5000)


def test_e2e_06_today_button_restores_today_report(page, http_server):
    # @requirement EDGE-006 @requirement REQ-005
    _goto(page, http_server, disable_worker=True)
    original_title = page.text_content("#titleText")
    bid = _pick_unindexed_rec_ids(page, 1)[0]
    page.locator(f"#recommendations .rec-item[data-book-id='{bid}']").click()
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


def test_e2e_09a_external_rec_without_worker_falls_back_to_perplexity(page, http_server):
    # @requirement fallback when Worker is unavailable
    _goto(page, http_server, disable_worker=True)
    page.evaluate(
        """renderRecommendations([
          {title: 'Prometheus Bound', author: 'Aeschylus', reason: '비극 확장', external: true}
        ]);"""
    )
    bid_attr = page.get_attribute("#recommendations .rec-item", "data-book-id")
    assert bid_attr is None
    html = page.inner_html("#recommendations .rec-item")
    assert "Perplexity에서 열기" in html
    with page.context.expect_page(timeout=5000) as new_page_info:
        page.locator("#recommendations .rec-item").click()
    new_page = new_page_info.value
    new_page.wait_for_load_state("domcontentloaded", timeout=8000)
    assert "perplexity.ai" in new_page.url


def test_e2e_09b_external_rec_with_worker_enters_generating_state(page, http_server):
    # @requirement external rec clicks trigger Worker dispatch + generating UI
    _goto(page, http_server)
    # Point WORKER_URL at unroutable loopback — dispatch will fail fast, but
    # we only need to observe the SYNCHRONOUS generating state that render()
    # draws before the dispatch await resolves.
    page.evaluate("WORKER_URL = 'http://127.0.0.1:1';")
    page.evaluate(
        """renderRecommendations([
          {title: 'Prometheus Bound', author: 'Aeschylus', reason: '비극 확장', external: true}
        ]);"""
    )
    # Badge now reads '리포트 생성' when a Worker is configured
    html = page.inner_html("#recommendations .rec-item")
    assert "리포트 생성" in html
    # Capture render state via instrumentation (same pattern as e2e_03b)
    calls = page.evaluate(
        """(async () => {
          window.__calls = [];
          const orig = window.render;
          window.render = function(d){
            const r = orig(d);
            window.__calls.push({
              generating: !!d.generating,
              title: d.title,
              author: d.author,
              chipVisible: !document.getElementById('generatingChip').hidden,
              blockVisible: !document.getElementById('generatingBlock').hidden,
            });
            return r;
          };
          document.querySelector('#recommendations .rec-item').click();
          await new Promise(r => setTimeout(r, 400));
          return window.__calls;
        })()"""
    )
    generating = [c for c in calls if c["generating"]]
    assert len(generating) >= 1, f"no generating render observed. calls={calls}"
    assert generating[0]["title"] == "Prometheus Bound"
    assert generating[0]["author"] == "Aeschylus"
    assert generating[0]["chipVisible"] is True
    assert generating[0]["blockVisible"] is True


def test_e2e_08_rapid_clicks_render_only_last(page, http_server):
    # @requirement EDGE-003
    _goto(page, http_server, disable_worker=True)
    # Fire both loadBookReport calls within the same microtask so the in-flight
    # guard has to arbitrate — last token wins. We cannot click twice via UI
    # because the first click rerenders recommendations, detaching the second
    # target from the DOM; the race we care about is the clickToken mechanism,
    # so we exercise it at the JS layer directly.
    bids = _pick_unindexed_rec_ids(page, 2)
    # Look up the expected title for the second (last-wins) book from books.json
    expected_title = page.evaluate(
        f"(async () => (await getBooksCatalog()).find(b => b.id === {bids[1]}).title)()"
    )
    page.evaluate(f"loadBookReport({bids[0]}); loadBookReport({bids[1]});")
    page.wait_for_selector("#previewChip:not([hidden])", timeout=5000)
    page.wait_for_function(
        f"document.getElementById('titleText').textContent.includes({json.dumps(expected_title)})",
        timeout=5000,
    )
    title = page.text_content("#titleText")
    assert expected_title in title
