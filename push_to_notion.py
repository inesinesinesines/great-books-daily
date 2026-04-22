import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from notion_client import Client

from generate_daily_report import _parse_arg

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")
WEB_APP_URL = os.getenv("WEB_APP_URL", "")
JSON_BASE_URL = os.getenv("JSON_BASE_URL", "")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./data"))


def text_obj(value: str):
    return [{"type": "text", "text": {"content": value[:2000]}}]


def load_today_report():
    path = OUTPUT_DIR / "today.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_report_for_date(date_str: str):
    path = OUTPUT_DIR / "daily" / f"{date_str}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_report_from_arg(arg: str):
    target_date = _parse_arg(arg)
    return load_report_for_date(target_date.isoformat())


def build_properties(report: dict):
    date_str = report["date"]
    title_text = f"{date_str} · {report['author']} · {report['title']}"
    summary_text = " ".join(report.get("summary", []))[:2000]
    json_url = f"{JSON_BASE_URL.rstrip('/')}/daily/{date_str}.json" if JSON_BASE_URL else ""

    props = {
        "Name": {"title": text_obj(title_text)},
        "Date": {"date": {"start": date_str}},
        "Book ID": {"number": report.get("book_id")},
        "Author": {"rich_text": text_obj(report.get("author", ""))},
        "Title": {"rich_text": text_obj(report.get("title", ""))},
        "Category": {"select": {"name": report.get("category", "Uncategorized")}},
        "Tradition": {"select": {"name": report.get("tradition", "Unknown")}},
        "Source Rank": {"number": report.get("source_rank", 3)},
        "Source Basis": {"rich_text": text_obj(report.get("source_basis", ""))},
        "Reading Mode": {"select": {"name": report.get("reading_mode", "ranked")}},
        "One-line Summary": {"rich_text": text_obj(report.get("one_line", ""))},
        "Five-minute Summary": {"rich_text": text_obj(summary_text)},
        "Discussion Question": {"rich_text": text_obj(report.get("discussion_question", ""))},
        "Why Now": {"rich_text": text_obj(report.get("why_now", ""))},
        "JSON URL": {"url": json_url or None},
        "Web App URL": {"url": WEB_APP_URL or None}
    }

    keywords = report.get("keywords", [])
    if keywords:
        props["Keywords"] = {"multi_select": [{"name": k[:100]} for k in keywords[:10]]}
    return props


def append_page_body(report: dict):
    summary_lines = report.get("summary", [])
    next_recs = report.get("next_recommendations", [])
    children = [
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": text_obj("오늘의 고전 리포트")}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": text_obj(report.get("one_line", ""))}},
    ]
    for line in summary_lines[:5]:
        children.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": text_obj(line)}})
    children.extend([
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": text_obj("핵심 키워드: " + ", ".join(report.get("keywords", []))) }},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": text_obj("토론 질문: " + report.get("discussion_question", ""))}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": text_obj("출처 기준: " + report.get("source_basis", ""))}},
        {"object": "block", "type": "heading_3", "heading_3": {"rich_text": text_obj("다음에 읽을 책 추천")}}
    ])
    for rec in next_recs[:3]:
        txt = f"{rec.get('author','')} · {rec.get('title','')} — {rec.get('reason','')}"
        children.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": text_obj(txt)}})
    children.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": text_obj("Perplexity 후속 질문: " + report.get("perplexity_followup_prompt", ""))}})
    return children


def _resolve_data_source_id(notion, database_id: str) -> str | None:
    """Fetch the first data_source id for a database. Returns None if the
    database shape doesn't expose data_sources (pre-2025-09 API versions)."""
    retrieve = getattr(getattr(notion, "databases", None), "retrieve", None)
    if callable(retrieve):
        try:
            info = retrieve(database_id=database_id)
        except Exception as exc:  # notion-client may raise on schema gaps
            print(f"[WARN] databases.retrieve failed: {exc}", flush=True)
            info = {}
    else:
        try:
            info = notion.request(path=f"databases/{database_id}", method="GET")
        except Exception as exc:
            print(f"[WARN] raw databases GET failed: {exc}", flush=True)
            return None
    sources = (info or {}).get("data_sources") or []
    if not sources:
        return None
    return sources[0].get("id")


def _query_database(notion, database_id: str, filter_expr: dict, page_size: int = 1):
    """Query a Notion database in a version-portable way.

    Notion API 2025-09 removed the POST /v1/databases/{id}/query endpoint;
    queries now target POST /v1/data_sources/{id}/query. notion-client 2.5+
    exposes a matching `data_sources` endpoint. Older setups still support
    `databases.query`. We try the legacy path first (cheaper, no extra
    round-trip), then resolve the first data_source and query that.
    """
    # 1. Legacy path: notion-client <2.5 and older Notion-Version headers.
    db_query = getattr(getattr(notion, "databases", None), "query", None)
    if callable(db_query):
        try:
            return db_query(database_id=database_id, filter=filter_expr, page_size=page_size)
        except Exception as exc:
            print(f"[INFO] legacy databases.query failed, falling back to data_sources: {exc}", flush=True)

    # 2. Modern path: data_sources/{id}/query
    ds_id = _resolve_data_source_id(notion, database_id)
    if ds_id:
        ds_query = getattr(getattr(notion, "data_sources", None), "query", None)
        if callable(ds_query):
            return ds_query(data_source_id=ds_id, filter=filter_expr, page_size=page_size)
        return notion.request(
            path=f"data_sources/{ds_id}/query",
            method="POST",
            body={"filter": filter_expr, "page_size": page_size},
        )

    # 3. Last resort: hit the legacy REST path. Will 400 on 2025-09 API.
    return notion.request(
        path=f"databases/{database_id}/query",
        method="POST",
        body={"filter": filter_expr, "page_size": page_size},
    )


def find_existing_page(notion, database_id: str, book_id, date_str: str):
    """Return the first Notion page whose (Book ID, Date) match, else None."""
    if book_id is None:
        return None
    filter_expr = {
        "and": [
            {"property": "Book ID", "number": {"equals": int(book_id)}},
            {"property": "Date", "date": {"equals": date_str}},
        ]
    }
    res = _query_database(notion, database_id, filter_expr, page_size=1)
    results = res.get("results", [])
    return results[0]["id"] if results else None


def clear_page_children(notion, page_id: str):
    """Delete all direct child blocks of a page so we can replace the body."""
    cursor = None
    while True:
        kwargs = {"block_id": page_id}
        if cursor:
            kwargs["start_cursor"] = cursor
        res = notion.blocks.children.list(**kwargs)
        for block in res.get("results", []):
            try:
                notion.blocks.delete(block_id=block["id"])
            except Exception as exc:
                print(f"[WARN] failed to delete block {block['id']}: {exc}", flush=True)
        if not res.get("has_more"):
            return
        cursor = res.get("next_cursor")


def upsert_report(notion, database_id: str, report: dict):
    """Create or update the Notion page for this (book_id, date). Returns {action, id}."""
    book_id = report.get("book_id")
    date_str = report["date"]
    props = build_properties(report)
    children = append_page_body(report)

    page_id = find_existing_page(notion, database_id, book_id, date_str)
    if page_id:
        notion.pages.update(page_id=page_id, properties=props)
        clear_page_children(notion, page_id)
        notion.blocks.children.append(block_id=page_id, children=children)
        return {"action": "update", "id": page_id, "book_id": book_id, "date": date_str}

    created = notion.pages.create(
        parent={"database_id": database_id},
        properties=props,
        children=children,
    )
    return {"action": "create", "id": created["id"], "book_id": book_id, "date": date_str}


def main():
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        raise RuntimeError("NOTION_API_KEY or NOTION_DATABASE_ID is missing")
    notion = Client(auth=NOTION_API_KEY)

    if len(sys.argv) > 1:
        report = load_report_from_arg(sys.argv[1])
    else:
        report = load_today_report()

    result = upsert_report(notion, NOTION_DATABASE_ID, report)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
