import json
import os
from pathlib import Path
from dotenv import load_dotenv
from notion_client import Client

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


def main():
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        raise RuntimeError("NOTION_API_KEY or NOTION_DATABASE_ID is missing")
    notion = Client(auth=NOTION_API_KEY)
    report = load_today_report()
    response = notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties=build_properties(report),
        children=append_page_body(report)
    )
    print(json.dumps(response, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
