# Architecture: Book Recommendation Click-to-View

## 1. Design Overview

정적 호스팅(GitHub Pages) 제약 아래서 "있으면 표시, 없으면 생성/저장 후 표시"를 2-Tier로 구현한다.

```
┌────────────────────────────────────────────────────────────────┐
│  Client (index.html)                                            │
│                                                                  │
│   [rec-item 클릭]                                               │
│       │                                                          │
│       ▼                                                          │
│   loadBookReport(book_id)                                       │
│       │                                                          │
│       ├── ① books-index.json 조회 (build-time 생성됨)          │
│       │     ├─ hit  → data/daily/<date>.json fetch → render()    │
│       │     └─ miss → ② 로컬 프리뷰 합성                         │
│       │                                                          │
│       └── ② buildClientPreview(book_id)                         │
│             ├─ books.json 에서 메타 추출                         │
│             ├─ fallback 스타일 리포트 합성 (generated_client_side:true) │
│             ├─ localStorage에 캐시 (key: book-preview-<id>)     │
│             └─ render()                                          │
└────────────────────────────────────────────────────────────────┘
                          │
                          │ (배포 파이프라인 / backfill)
                          ▼
┌────────────────────────────────────────────────────────────────┐
│  Server (Python)                                                │
│                                                                 │
│   generate_daily_report.save_report(report)                    │
│       ├─ data/daily/<date>.json 저장 (기존)                     │
│       ├─ data/today.json 갱신 (기존)                            │
│       └─ 🆕 rebuild_books_index()                               │
│             → data/daily/*.json 전수 스캔                       │
│             → data/books-index.json 재작성                      │
└─────────────────────────────────────────────────────────────────┘
```

**용어**:
- **Authoritative report**: `data/daily/<date>.json` — 서버에서 Claude API로 생성·저장된 공식 리포트.
- **Client preview**: 클라이언트가 `books.json` 메타로 합성한 임시 리포트. `generated_client_side: true` 플래그로 식별.

## 2. File Structure

### 신규
```
data/books-index.json           # 🆕 빌드 타임 생성 (서버 save_report 출력)
tests/unit/test_books_index.py  # 🆕 pytest — rebuild_books_index() 검증
tests/unit/test_save_report.py  # 🆕 pytest — save_report 인덱스 갱신 훅 검증
tests/e2e/conftest.py           # 🆕 Playwright + http.server fixture
tests/e2e/test_recommendation_click.py  # 🆕 실서버 E2E
pytest.ini                      # 🆕 최소 설정
```

### 변경
```
generate_daily_report.py        # ~20줄 추가: rebuild_books_index() + save_report() 훅
index.html                      # ~50줄 추가: 클릭 핸들러, 프리뷰 합성, 인덱스 조회
```

### 변경 없음
```
books.json, books-ranked.json, push_to_notion.py, run_daily.py,
.github/workflows/daily-update.yml, .github/workflows/backfill.yml
```
(`daily-update.yml`은 `save_report` 훅 덕분에 자동으로 인덱스를 커밋함.)

## 3. Interface Contract

### 3.1 Server: `generate_daily_report.py`

```python
def rebuild_books_index(output_dir: Path) -> dict:
    """
    Scan output_dir/daily/*.json and produce a book_id -> dates mapping.
    Returns the dict and writes it to output_dir/books-index.json.

    Output schema (written to disk):
    {
      "generated_at": "2026-04-22T12:34:56+09:00",
      "count": 4,
      "books": {
        "1":   { "latest": "2026-04-20", "dates": ["2026-04-20"] },
        "2":   { "latest": "2026-04-21", "dates": ["2026-04-21"] },
        "5":   { "latest": "2026-04-22", "dates": ["2026-04-22"] },
        "100": { "latest": "2026-04-19", "dates": ["2026-04-19"] }
      }
    }
    """

def save_report(report: dict, update_today: bool = True) -> None:
    # (기존) daily/<date>.json + today.json 저장
    # (신규 후속 호출) rebuild_books_index(OUTPUT_DIR)
```

**계약**:
- `rebuild_books_index`는 순수 함수(외부 상태 없음). `output_dir`만 입력으로 받음.
- 각 `YYYY-MM-DD.json` 의 `book_id` 키를 요구. 없으면 skip + 경고.
- `dates` 배열은 ASC 정렬. `latest`는 ISO 문자열 비교로 최신.
- 재기록은 멱등(동일 입력 → 동일 출력).

### 3.2 Client: `index.html` 내 JS (신규 함수)

```js
// 인덱스 조회 (1회 캐시)
async function getBooksIndex(): Promise<object|null>

// 클릭 진입점
async function loadBookReport(bookId: number): Promise<void>
//   내부 순서: index 조회 → date hit? → loadDate(date) → render()
//                                ↓ miss
//                            buildClientPreview(bookId) → render()

// books.json 메타 + fallback 스타일로 프리뷰 합성
function buildClientPreview(bookId: number): ReportObject
//   반환 스키마는 기존 report와 동일. 추가 필드:
//     generated_client_side: true
//     preview_notice: "아직 정식 리포트가 준비되지 않아 임시 요약을 보여드려요"

// 카드 렌더(갱신): data-book-id / role=button / tabindex / click·keydown 바인딩
function renderRecommendations(recs: Array<{book_id,title,author,reason}>): void
```

**계약**:
- `loadBookReport`는 인플라이트 토큰을 써서 연속 클릭 시 마지막 것만 렌더(EDGE-003).
- 인덱스가 없거나 404여도 `buildClientPreview` 경로로 반드시 렌더 성공(NFR-002).
- `books.json`은 최초 1회 로드 후 모듈 변수 캐시.
- 프리뷰는 `localStorage.setItem('book-preview-<id>', JSON.stringify(report))`로 캐시. 재방문 시 네트워크 없이 즉시 재현.

### 3.3 books-index.json 스키마 예시

```json
{
  "generated_at": "2026-04-22T12:34:56+09:00",
  "count": 4,
  "books": {
    "1":   { "latest": "2026-04-20", "dates": ["2026-04-20"] },
    "2":   { "latest": "2026-04-21", "dates": ["2026-04-21"] },
    "5":   { "latest": "2026-04-22", "dates": ["2026-04-22"] },
    "100": { "latest": "2026-04-19", "dates": ["2026-04-19"] }
  }
}
```

### 3.4 클라이언트 프리뷰 리포트 스키마 (합성 결과)

기존 스키마 모두 포함 + 다음 추가:
```json
{
  "...기존 필드...": "...",
  "generated_client_side": true,
  "preview_notice": "아직 정식 리포트가 준비되지 않아 임시 요약을 보여드려요"
}
```

## 4. Data Flow

### 4.1 해피 패스 — 기존 리포트 있음 (REQ-003)

```
[click rec-item (data-book-id=7)]
  → loadBookReport(7)
  → getBooksIndex()       (첫 호출만 네트워크)
  → books-index.json.books["7"].latest = "2026-05-12"
  → fetch data/daily/2026-05-12.json
  → render(data)          (기존 함수 그대로)
  → renderRecommendations(data.next_recommendations)  (연쇄 지원)
```

### 4.2 폴백 패스 — 리포트 없음 (REQ-004)

```
[click rec-item (data-book-id=42)]
  → loadBookReport(42)
  → getBooksIndex()
  → books["42"] 없음
  → buildClientPreview(42)
       ├─ books.json 에서 book 42 메타 조회
       └─ fallback 스타일 요약 합성 (+generated_client_side:true)
  → localStorage.setItem('book-preview-42', ...)
  → render(previewReport)
```

### 4.3 서버 생성 → 인덱스 갱신 (REQ-007)

```
python generate_daily_report.py 2026-05-01
  → pick_book / build_prompt / call_claude
  → save_report(report)
       ├─ daily/2026-05-01.json 저장
       ├─ today.json 갱신 (조건부)
       └─ rebuild_books_index(OUTPUT_DIR)
            → books-index.json 재작성 (+2026-05-01의 book_id 포함)
  → 다음 cron / 다음 사용자 진입 시 인덱스 hit
```

## 5. Integration Points

- **기존 `render()` 재사용**: 새 프리뷰 리포트도 동일 `render()`에 전달 → 회귀 위험 최소. `d.generated_client_side`가 true일 때만 타이틀 또는 eyebrow에 "프리뷰" 라벨을 덧붙이는 한 줄 추가.
- **기존 `loadDate()` 재사용**: date 기반 fetch를 그대로 씀. 새 래퍼 `loadBookReport`가 인덱스로 date 결정 후 호출.
- **`push_to_notion.py` 변경 없음**: Notion은 계속 `today.json`만 소비.
- **GitHub Actions**: `daily-update.yml`은 이미 `git add data/today.json data/daily`를 하고 있음. `data/books-index.json`도 커밋되도록 `git add`에 추가해야 함(or, `save_report`가 위치를 `OUTPUT_DIR` 루트에 쓰므로 `git add data/books-index.json` 필요). → **워크플로 2곳에 `data/books-index.json` 추가**.
- **backfill.yml**: `data/daily`만 add. 인덱스도 포함 필요.

### 워크플로 변경 (최소)
```yaml
# daily-update.yml
- git add data/today.json data/daily data/books-index.json || true

# backfill.yml
- git add data/daily data/books-index.json || true
```

## 6. Non-Functional Approach

- **NFR-001 (<800ms)**: 인덱스는 4KB 수준 단일 JSON. fetch 1회 + 리포트 fetch 1회 = 2 round-trip. 로컬에서 50ms 대에 완료됨이 E2E에서 확인 예정.
- **NFR-002 (404 fallback)**: `getBooksIndex` 내부 try/catch. 실패 시 `null` 반환 → `loadBookReport`는 바로 프리뷰 경로.
- **NFR-003 (API 키 비노출)**: 클라이언트는 Claude API를 직접 호출하지 않음. `buildClientPreview`는 순수 문자열 템플릿.
- **NFR-004 (키보드)**: `role="button"` + `tabindex="0"` + Enter/Space keydown.

## 7. Test Strategy

| 레이어 | 범위 | 도구 |
|--------|------|------|
| Unit | `rebuild_books_index()`, `save_report` 훅 | pytest |
| Unit | `buildClientPreview()` 스키마 보존 | E2E 내부 evaluate 로 대체 (JS 단독 단위테스트 인프라 부재) |
| Integration | save_report ↔ 실제 파일 시스템 ↔ 인덱스 재작성 | pytest (tmp_path) |
| E2E | 실서버(http.server) + Playwright 브라우저 자동화 | Playwright |

E2E는 CLAUDE.md 규약에 따라 **모킹 없이** 실제 `data/daily/*.json` 과 `http.server`를 사용한다.
