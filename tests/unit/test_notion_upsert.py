"""
Unit tests for push_to_notion upsert logic.

Uses a hand-rolled fake Notion client so we can run without real credentials
and without network. The fake mirrors only the methods the upsert path uses.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import push_to_notion as ptn  # noqa: E402


class _Namespace:
    """Lightweight object for attribute access (mimics notion-client namespaces)."""


class FakeNotion:
    """Minimal Notion client stub exercising the create-or-update contract.

    Can simulate three eras:
      * legacy (<2.5 + old Notion-Version): databases.query available
      * modern (2.5+ + 2025-09 API): data_sources endpoint required
      * pure-raw: neither typed endpoint is available, only request()
    """

    def __init__(
        self,
        existing_pages=None,
        expose_databases_query=True,
        legacy_query_works=True,
        expose_data_sources=True,
    ):
        self.existing_pages = list(existing_pages or [])
        self.calls = []
        self.legacy_query_works = legacy_query_works
        self.data_source_id = "ds-fake-1"

        self.databases = _Namespace()
        self.databases.retrieve = self._db_retrieve
        if expose_databases_query:
            self.databases.query = self._db_query_maybe_fail

        self.pages = _Namespace()
        self.pages.create = self._pages_create
        self.pages.update = self._pages_update

        self.blocks = _Namespace()
        self.blocks.delete = self._blocks_delete
        children = _Namespace()
        children.list = self._blocks_children_list
        children.append = self._blocks_children_append
        self.blocks.children = children

        if expose_data_sources:
            self.data_sources = _Namespace()
            self.data_sources.query = self._data_sources_query

    def _db_query_maybe_fail(self, database_id, filter, page_size=10, **_):
        self.calls.append(("databases.query", {"database_id": database_id, "filter": filter}))
        if not self.legacy_query_works:
            # Simulate the 400 returned by 2025-09 API on the legacy path
            raise RuntimeError("Invalid request URL (simulated 400)")
        return self._match(filter, page_size)

    def _db_retrieve(self, database_id, **_):
        self.calls.append(("databases.retrieve", {"database_id": database_id}))
        return {"id": database_id, "data_sources": [{"id": self.data_source_id}]}

    def _data_sources_query(self, data_source_id, filter, page_size=10, **_):
        self.calls.append(("data_sources.query", {"data_source_id": data_source_id, "filter": filter}))
        return self._match(filter, page_size)

    def _match(self, filter_expr, page_size):
        filters = filter_expr.get("and", [])
        want_book = next(f for f in filters if "Book ID" in f["property"])["number"]["equals"]
        want_date = next(f for f in filters if "Date" in f["property"])["date"]["equals"]
        matches = [
            {"id": p["id"]}
            for p in self.existing_pages
            if p["book_id"] == want_book and p["date"] == want_date
        ]
        return {"results": matches[:page_size]}

    def request(self, path, method, query=None, body=None, auth=None):
        """Raw-request shim. Used only when neither typed endpoint is mounted."""
        self.calls.append(("request", {"path": path, "method": method}))
        body = body or {}
        if method == "GET" and path.startswith("databases/") and "/" not in path[len("databases/"):]:
            return self._db_retrieve(database_id=path.split("/")[1])
        if method == "POST" and path.startswith("data_sources/") and path.endswith("/query"):
            return self._match(body.get("filter", {}), body.get("page_size", 10))
        if method == "POST" and path.startswith("databases/") and path.endswith("/query"):
            return self._match(body.get("filter", {}), body.get("page_size", 10))
        raise NotImplementedError(f"FakeNotion.request unsupported: {method} {path}")


    def _pages_create(self, parent, properties, children):
        self.calls.append(("pages.create", {"parent": parent}))
        new = {
            "id": f"page-new-{len(self.existing_pages)+1}",
            "book_id": properties["Book ID"]["number"],
            "date": properties["Date"]["date"]["start"],
            "children": list(children),
            "properties": properties,
        }
        self.existing_pages.append(new)
        return {"id": new["id"]}

    def _pages_update(self, page_id, properties):
        self.calls.append(("pages.update", {"page_id": page_id}))
        for p in self.existing_pages:
            if p["id"] == page_id:
                p["properties"] = properties
                return {"id": page_id}
        raise KeyError(page_id)

    def _blocks_children_list(self, block_id, start_cursor=None, **_):
        self.calls.append(("blocks.children.list", {"block_id": block_id}))
        for p in self.existing_pages:
            if p["id"] == block_id:
                return {
                    "results": [{"id": f"blk-{i}"} for i in range(len(p.get("children", [])))],
                    "has_more": False,
                }
        return {"results": [], "has_more": False}

    def _blocks_delete(self, block_id):
        self.calls.append(("blocks.delete", {"block_id": block_id}))
        # Stubbed — child tracking is simulated in append

    def _blocks_children_append(self, block_id, children):
        self.calls.append(("blocks.children.append", {"block_id": block_id, "count": len(children)}))
        for p in self.existing_pages:
            if p["id"] == block_id:
                p["children"] = list(children)
                return {"results": []}
        raise KeyError(block_id)


@pytest.fixture
def sample_report():
    return {
        "date": "2026-04-22",
        "book_id": 5,
        "author": "Herodotus",
        "title": "Histories",
        "category": "History",
        "tradition": "Greek",
        "source_rank": 1,
        "source_basis": "basis",
        "reading_mode": "ranked",
        "one_line": "one",
        "summary": ["s1", "s2"],
        "keywords": ["k1"],
        "why_now": "w",
        "discussion_question": "q",
        "perplexity_followup_prompt": "p",
        "next_recommendations": [{"author": "X", "title": "Y", "reason": "r"}],
    }


def test_upsert_creates_when_no_match(sample_report):
    # @requirement on-demand Notion push — create path
    notion = FakeNotion(existing_pages=[])
    result = ptn.upsert_report(notion, "db-id", sample_report)
    assert result["action"] == "create"
    methods = [c[0] for c in notion.calls]
    assert methods[0] == "databases.query"
    assert "pages.create" in methods
    assert "pages.update" not in methods


def test_upsert_updates_when_same_book_and_date_exists(sample_report):
    # @requirement dedup — update existing rather than create duplicate
    notion = FakeNotion(existing_pages=[{
        "id": "page-exist-1", "book_id": 5, "date": "2026-04-22", "children": []
    }])
    result = ptn.upsert_report(notion, "db-id", sample_report)
    assert result["action"] == "update"
    assert result["id"] == "page-exist-1"
    methods = [c[0] for c in notion.calls]
    # Must: query -> update -> list children -> append children (no create)
    assert "pages.create" not in methods
    assert "pages.update" in methods
    assert "blocks.children.append" in methods


def test_upsert_two_invocations_yield_single_page(sample_report):
    # @requirement dedup — idempotent upsert
    notion = FakeNotion(existing_pages=[])
    ptn.upsert_report(notion, "db-id", sample_report)
    assert len(notion.existing_pages) == 1
    # Second call with same (book_id, date) must not create a second page
    ptn.upsert_report(notion, "db-id", sample_report)
    assert len(notion.existing_pages) == 1
    create_calls = [c for c in notion.calls if c[0] == "pages.create"]
    update_calls = [c for c in notion.calls if c[0] == "pages.update"]
    assert len(create_calls) == 1
    assert len(update_calls) == 1


def test_upsert_different_book_same_date_creates_new(sample_report):
    notion = FakeNotion(existing_pages=[{
        "id": "page-1", "book_id": 5, "date": "2026-04-22", "children": []
    }])
    other = dict(sample_report)
    other["book_id"] = 7
    other["title"] = "Oresteia"
    result = ptn.upsert_report(notion, "db-id", other)
    assert result["action"] == "create"
    assert len(notion.existing_pages) == 2


def test_upsert_falls_back_to_data_sources_when_databases_query_missing(sample_report):
    # @requirement compat with notion-client 2.5+ (databases.query removed)
    notion = FakeNotion(existing_pages=[], expose_databases_query=False)
    assert not hasattr(notion.databases, "query"), "fake must not expose databases.query"
    result = ptn.upsert_report(notion, "db-id", sample_report)
    assert result["action"] == "create"
    methods = [c[0] for c in notion.calls]
    # Must resolve the data source and query it — not the legacy path
    assert "databases.retrieve" in methods
    assert "data_sources.query" in methods


def test_upsert_falls_back_from_legacy_400_to_data_sources(sample_report):
    # @requirement compat with Notion API 2025-09 (databases/*/query returns 400)
    notion = FakeNotion(existing_pages=[], legacy_query_works=False)
    result = ptn.upsert_report(notion, "db-id", sample_report)
    assert result["action"] == "create"
    methods = [c[0] for c in notion.calls]
    # Legacy path attempted, failed, then data_sources path used
    assert methods[0] == "databases.query"
    assert "data_sources.query" in methods


def test_upsert_different_date_same_book_creates_new(sample_report):
    notion = FakeNotion(existing_pages=[{
        "id": "page-1", "book_id": 5, "date": "2026-04-22", "children": []
    }])
    other = dict(sample_report)
    other["date"] = "2026-05-01"
    result = ptn.upsert_report(notion, "db-id", other)
    assert result["action"] == "create"
    assert len(notion.existing_pages) == 2


def test_upsert_clears_children_before_reappending(sample_report):
    # @requirement page body must reflect the latest report (no stale blocks)
    notion = FakeNotion(existing_pages=[{
        "id": "page-exist-1", "book_id": 5, "date": "2026-04-22",
        "children": [{"type": "paragraph"} for _ in range(3)]
    }])
    ptn.upsert_report(notion, "db-id", sample_report)
    methods = [c[0] for c in notion.calls]
    # 3 existing blocks listed, then 3 deletes, then 1 append
    assert methods.count("blocks.delete") == 3
    assert methods.count("blocks.children.append") == 1


def test_load_report_from_arg_accepts_book_id(tmp_path, monkeypatch, sample_report):
    # @requirement push_to_notion should accept book_id like generate_daily_report
    monkeypatch.setattr(ptn, "OUTPUT_DIR", tmp_path)
    daily = tmp_path / "daily"
    daily.mkdir()
    (daily / "2026-04-22.json").write_text(
        json.dumps(sample_report, ensure_ascii=False), encoding="utf-8"
    )
    # Env expected by _parse_arg (imported transitively)
    monkeypatch.setenv("START_DATE", "2026-04-20")
    monkeypatch.setenv("TIMEZONE", "Asia/Seoul")
    monkeypatch.setenv("READING_MODE", "ranked")
    # book_id=5 maps to 2026-04-22 in ranked mode
    loaded = ptn.load_report_from_arg("5")
    assert loaded["book_id"] == 5
    assert loaded["date"] == "2026-04-22"


def test_load_report_from_arg_accepts_date(tmp_path, monkeypatch, sample_report):
    monkeypatch.setattr(ptn, "OUTPUT_DIR", tmp_path)
    daily = tmp_path / "daily"
    daily.mkdir()
    (daily / "2026-04-22.json").write_text(
        json.dumps(sample_report, ensure_ascii=False), encoding="utf-8"
    )
    loaded = ptn.load_report_from_arg("2026-04-22")
    assert loaded["date"] == "2026-04-22"
