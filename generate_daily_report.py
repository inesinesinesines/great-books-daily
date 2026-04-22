import json
import os
import re
import sys
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Defaults to Opus 4.7 (most capable current model). Override by setting the
# CLAUDE_MODEL env var / GitHub Actions secret (e.g., to claude-sonnet-4-6
# for faster/cheaper runs). An empty string still falls back to the default.
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL") or "claude-opus-4-7"
START_DATE = os.getenv("START_DATE", "2026-04-20")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Seoul")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./data"))
BOOKS_PATH = Path(__file__).parent / "books.json"
READING_MODE = os.getenv("READING_MODE", "ranked").strip().lower()


def load_books(include_external: bool = False):
    """Load the curated book catalog from books.json.

    include_external=False (default) excludes books with source_rank >= 4 so
    they don't pollute the daily rotation (pick_book). External books are
    entries added dynamically from user-triggered recommendations.
    """
    books = json.loads(BOOKS_PATH.read_text(encoding="utf-8"))
    if not include_external:
        books = [b for b in books if b.get("source_rank", 3) <= 3]
    if READING_MODE == "strict":
        return [b for b in books if b.get("source_rank", 3) <= 2]
    return books


def _normalize(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def add_external_book(title: str, author: str) -> dict:
    """Add or return a book entry for a user-requested external classic.

    Dedupes on (normalized author, normalized title). If an entry already
    exists (regardless of source_rank) it is returned unchanged. New entries
    are appended to books.json with source_rank=4 so pick_book's daily
    rotation is not affected.
    """
    title = (title or "").strip()
    author = (author or "").strip()
    if not title or not author:
        raise ValueError("title and author are required for external book")

    books = json.loads(BOOKS_PATH.read_text(encoding="utf-8"))
    key = (_normalize(author), _normalize(title))
    for b in books:
        if (_normalize(b.get("author", "")), _normalize(b.get("title", ""))) == key:
            return b

    new_id = max((b.get("id", 0) for b in books), default=0) + 1
    entry = {
        "id": new_id,
        "author": author,
        "title": title,
        "category": "Classic",
        "tradition": "Unknown",
        "source_rank": 4,
        "source_basis": "User-requested external recommendation",
    }
    books.append(entry)
    BOOKS_PATH.write_text(
        json.dumps(books, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return entry


def get_today_local():
    return datetime.now(ZoneInfo(TIMEZONE)).date()


def pick_book(target_date: date, books: list[dict]) -> tuple[dict, int]:
    start = datetime.strptime(START_DATE, "%Y-%m-%d").date()
    delta = (target_date - start).days
    idx = delta % len(books)
    return books[idx], idx


def next_books(current_index: int, books: list[dict], count: int = 3) -> list[dict]:
    return [books[(current_index + i) % len(books)] for i in range(1, count + 1)]


def recommendation_reason(book: dict) -> str:
    rank = book.get("source_rank", 3)
    if rank == 1:
        return "공개 Basic Program 자료에서 직접 확인되는 작품이어서 우선 추천됩니다."
    if rank == 2:
        return "대표 저자군 기반으로 흐름을 자연스럽게 이어 주는 작품입니다."
    return "확장 고전 단계에서 시야를 넓혀 주는 보강 텍스트입니다."


def build_prompt(book: dict, target_date: str, excluded_titles: list[str]) -> str:
    """
    excluded_titles: list of "Author / Title" strings (the app's curated 100).
    Claude must recommend 3 classics NOT in this list but in a similar author
    group, tradition, or theme.
    """
    excluded_block = "\n".join(f"- {t}" for t in excluded_titles)
    return f"""
당신은 고전 읽기 앱의 일일 리포트를 만드는 편집자입니다.
반드시 JSON만 반환하세요. 마크다운, 코드펜스, 설명 문장 없이 순수 JSON만 출력하세요.

날짜: {target_date}
읽기 모드: {READING_MODE}
오늘의 책:
- id: {book['id']}
- author: {book['author']}
- title: {book['title']}
- category: {book['category']}
- tradition: {book['tradition']}
- source_rank: {book.get('source_rank', 3)}
- source_basis: {book.get('source_basis', '')}

이 앱에 이미 등록된 100권(아래 목록) 안의 작품은 next_recommendations 후보에서
**반드시 제외**하세요. 추천은 아래 목록에 없는 고전이어야 합니다.

==== 제외 목록 (Author / Title) ====
{excluded_block}
==== 제외 목록 끝 ====

반환 JSON 스키마:
{{
  "date": "{target_date}",
  "book_id": {book['id']},
  "author": "{book['author']}",
  "title": "{book['title']}",
  "category": "{book['category']}",
  "tradition": "{book['tradition']}",
  "source_rank": {book.get('source_rank', 3)},
  "source_basis": "{book.get('source_basis', '')}",
  "reading_mode": "{READING_MODE}",
  "one_line": "한국어 한 문장 요약",
  "summary": ["문장1", "문장2", "문장3", "문장4", "문장5"],
  "keywords": ["키워드1", "키워드2", "키워드3", "키워드4"],
  "why_now": "한국어 2~3문장",
  "discussion_question": "한국어 질문 1개",
  "perplexity_followup_prompt": "사용자가 Perplexity에 이어서 물을 수 있는 한국어 질문",
  "next_recommendations": [
    {{"title": "...", "author": "...", "reason": "...", "external": true}},
    {{"title": "...", "author": "...", "reason": "...", "external": true}},
    {{"title": "...", "author": "...", "reason": "...", "external": true}}
  ],
  "source_note": "Basic Program 기반 Great Books 스타일 일일 리포트"
}}

요구사항:
- 자연스러운 한국어로 작성
- 짧지만 내용 있게 작성
- 가짜 인용문 금지
- 작품의 핵심 사상, 문제의식, 현재적 의미를 중심으로 쓸 것
- next_recommendations는 **위의 100권 목록에 없는 실존 고전** 중에서, 오늘의 책과 같은 저자의 다른 대표작,
  같은 전통/시대의 연계 작품, 또는 같은 주제의식을 확장하는 고전을 3권 추천하세요.
- 추천의 reason은 2~3문장으로, 오늘의 책과의 연결점을 명시할 것.
- book_id는 포함하지 마세요 (외부 고전이므로 id 없음). external=true 플래그만 유지.
- JSON 외의 어떤 텍스트도 출력하지 말 것
""".strip()


def extract_text(resp) -> str:
    parts = []
    for block in resp.content:
        text = getattr(block, 'text', None)
        if text:
            parts.append(text)
    return ''.join(parts).strip()


def strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.index("\n")
        text = text[first_nl + 1:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def call_claude(prompt: str) -> dict:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError('ANTHROPIC_API_KEY is missing')
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1800,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )
    content = extract_text(msg)
    content = strip_code_fences(content)
    return json.loads(content)


def fallback_report(book: dict, target_date: str, recommendations: list[dict]) -> dict:
    return {
        "date": target_date,
        "book_id": book["id"],
        "author": book["author"],
        "title": book["title"],
        "category": book["category"],
        "tradition": book["tradition"],
        "source_rank": book.get("source_rank", 3),
        "source_basis": book.get("source_basis", ""),
        "reading_mode": READING_MODE,
        "one_line": f"{book['author']}의 『{book['title']}』을(를) 오늘의 고전으로 읽는 일일 리포트입니다.",
        "summary": [
            f"이 작품은 {book['category']} 전통에서 중요한 위치를 차지합니다.",
            "핵심 개념과 논점, 텍스트의 구조를 빠르게 잡도록 구성했습니다.",
            "출처에 가까운 책부터 읽고 이후 확장 고전으로 넓혀 가는 흐름에 놓여 있습니다.",
            "줄거리보다 문제 제기와 사상적 긴장을 중심으로 읽는 것이 중요합니다.",
            "오늘의 리포트는 현재적 의미까지 짧게 연결해 줍니다."
        ],
        "keywords": [book["category"], book["tradition"], "핵심 개념", "현대적 의미"],
        "why_now": "고전은 오래된 텍스트가 아니라 오늘의 문제를 다시 보게 만드는 기준점이 될 수 있습니다.",
        "discussion_question": f"『{book['title']}』의 핵심 문제를 오늘 사회에 적용하면 어떤 쟁점이 생길까?",
        "perplexity_followup_prompt": f"{book['author']}의 {book['title']}을 현대 사회 문제와 연결해서 설명해줘.",
        "next_recommendations": [
            {"book_id": b["id"], "title": b["title"], "author": b["author"], "reason": recommendation_reason(b)} for b in recommendations
        ],
        "source_note": "Basic Program 기반 Great Books 스타일 일일 리포트"
    }


def rebuild_books_index(output_dir: Path) -> dict:
    """Scan output_dir/daily/*.json and rebuild output_dir/books-index.json.

    Returns the index dict. Reports without a 'book_id' field are skipped.
    Dates within each book entry are sorted ascending; 'latest' is the max.
    External books (source_rank>=4, if present in books.json) get normalized
    title/author fields so the client can match by (author, title).
    """
    output_dir = Path(output_dir)
    daily_dir = output_dir / 'daily'
    books: dict[str, dict] = {}
    # Build a catalog lookup once so we can annotate external entries
    try:
        catalog = json.loads(BOOKS_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        catalog = []
    catalog_by_id = {b.get('id'): b for b in catalog}

    if daily_dir.exists():
        for path in sorted(daily_dir.glob('*.json')):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"[WARN] books-index: skip {path.name}: {exc}", flush=True)
                continue
            bid = data.get('book_id')
            if bid is None:
                print(f"[WARN] books-index: {path.name} has no book_id", flush=True)
                continue
            date_str = data.get('date') or path.stem
            key = str(bid)
            entry = books.setdefault(key, {'latest': '', 'dates': []})
            if date_str not in entry['dates']:
                entry['dates'].append(date_str)
            cat = catalog_by_id.get(bid) or {}
            if cat.get('source_rank', 3) >= 4:
                entry['external'] = True
                entry['title_norm'] = _normalize(data.get('title') or cat.get('title', ''))
                entry['author_norm'] = _normalize(data.get('author') or cat.get('author', ''))

    for entry in books.values():
        entry['dates'].sort()
        entry['latest'] = entry['dates'][-1] if entry['dates'] else ''
    sorted_books = {k: books[k] for k in sorted(books.keys(), key=lambda s: int(s))}
    index = {
        'generated_at': datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds'),
        'count': len(sorted_books),
        'books': sorted_books,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'books-index.json').write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return index


def save_report(report: dict, update_today: bool = True):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_dir = OUTPUT_DIR / 'daily'
    daily_dir.mkdir(parents=True, exist_ok=True)
    (daily_dir / f"{report['date']}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if update_today:
        (OUTPUT_DIR / 'today.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    rebuild_books_index(OUTPUT_DIR)


def generate_for_date(target_date: date, update_today: bool = True, force: bool = False):
    """Generate (or reuse) the report for target_date.

    If the daily file already exists and force is False, the existing report
    is reused as-is — no Claude call, no content change. today.json and the
    books index are still refreshed so downstream consumers (Notion, index)
    stay consistent.
    """
    target_str = target_date.isoformat()
    daily_path = OUTPUT_DIR / 'daily' / f"{target_str}.json"
    if not force and daily_path.exists():
        report = json.loads(daily_path.read_text(encoding='utf-8'))
        print(f"[INFO] {target_str} already exists — reusing (skip Claude)", flush=True)
        save_report(report, update_today=update_today)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return report

    # For per-book on-demand generation, the book may live outside the
    # curated 100 (source_rank=4). Look up with externals included.
    rotation_books = load_books()  # daily rotation excludes externals
    full_books = load_books(include_external=True)
    # pick_book operates on a full list indexed by canonical date.
    book, idx = pick_book(target_date, full_books)
    fallback_recs = next_books(idx, rotation_books, 3)  # only used if Claude fails
    excluded_titles = [f"{b['author']} / {b['title']}" for b in full_books]
    prompt = build_prompt(book, target_str, excluded_titles)
    try:
        report = call_claude(prompt)
    except Exception as e:
        print(f"[WARN] Claude API failed: {e}", flush=True)
        report = fallback_report(book, target_str, fallback_recs)
    save_report(report, update_today=update_today)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def date_for_book_id(book_id: int) -> date:
    # Search external-inclusive list first so externally-added books resolve.
    books = load_books(include_external=True)
    for idx, b in enumerate(books):
        if b.get("id") == book_id:
            start = datetime.strptime(START_DATE, "%Y-%m-%d").date()
            return start + timedelta(days=idx)
    raise ValueError(f"book_id {book_id} not found in books list (READING_MODE={READING_MODE})")


def _parse_arg(arg: str) -> date:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", arg):
        return datetime.strptime(arg, "%Y-%m-%d").date()
    if re.fullmatch(r"\d+", arg):
        return date_for_book_id(int(arg))
    raise ValueError(f"Argument must be YYYY-MM-DD or a book_id integer, got: {arg!r}")


def generate_for_external(title: str, author: str, update_today: bool = False, force: bool = False) -> dict:
    """Register an external classic in books.json, then run the normal
    generate_for_date pipeline against its canonical date.
    Returns the generated report.
    """
    entry = add_external_book(title, author)
    target_date = date_for_book_id(entry["id"])
    return generate_for_date(target_date, update_today=update_today, force=force)


def main():
    args = [a for a in sys.argv[1:] if a]
    force = "--force" in args

    if "--external" in args:
        i = args.index("--external")
        rest = [a for a in args[i + 1 :] if not a.startswith("--")]
        if len(rest) < 2:
            raise SystemExit('--external requires: --external "<title>" "<author>"')
        title, author = rest[0], rest[1]
        generate_for_external(title, author, update_today=False, force=force)
        return

    positional = [a for a in args if not a.startswith("--")]
    if positional:
        target = _parse_arg(positional[0])
        today = get_today_local()
        generate_for_date(target, update_today=(target == today), force=force)
    else:
        generate_for_date(get_today_local(), force=force)


if __name__ == '__main__':
    main()
