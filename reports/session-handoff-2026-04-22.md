# Session Handoff — 2026-04-22

네트워크 단절 대비 핸드오프 기록. 다음 세션에서 이 파일 + `git log` + `docs/requirements/book-recommendation-click-rtm.md` 만 읽어도 작업을 이어갈 수 있게 작성.

## 1. 지금까지 반영된 기능 (모두 커밋·푸시됨)

브랜치: `main` — 마지막 커밋 `56c129d` "Upgrade default model to Opus 4.7".

### 1.1 핵심 기능
- **카드 클릭 → 리포트 로드**: 추천 카드를 클릭하면 메인 뷰가 해당 책 리포트로 전환. 페이지 최상단으로 스크롤.
- **인덱스 기반 조회**: `data/books-index.json` (빌드 시 서버가 자동 생성, book_id → 최신 날짜 매핑).
- **자동 생성 플로우**: 인덱스에 없는 책 클릭 시
  1. "작성 중" 상태 즉시 표시 (작성 중 chip + 안내 블록, 요약 블록 숨김)
  2. 백그라운드로 Cloudflare Worker `gbd-dispatch` → GitHub `workflow_dispatch` → Actions `generate-book.yml`
  3. `books-index.json` 5초 간격 폴링 (cache-bust) — 최대 3분
  4. 리포트 등장 시 render() 자동 호출, 새로고침 불필요
  5. 타임아웃/실패 시 프리뷰로 폴백

### 1.2 인프라
- **Cloudflare Worker**: `https://gbd-dispatch.books-dailiy.workers.dev`
  - 소스: `cloudflare-worker/src/index.js`
  - Origin 허용 목록 + (book_id, 1~500) 검증 + GITHUB_TOKEN secret 내부 보관
  - 배포 명령: `cd cloudflare-worker && npx wrangler deploy`
- **Actions 워크플로**:
  - `daily-update.yml`: 매일 03:10 UTC 실행, 오늘 책 생성 + Notion upsert
  - `backfill.yml`: 기간 지정 재생성
  - `generate-book.yml`: `workflow_dispatch(book_id)`, 단일 책 생성 + Notion upsert + 커밋
- **GitHub Pages**: 퍼블릭 정적 호스팅, `data/*` fetch 경로

### 1.3 Python 쪽 정책
- `generate_daily_report.py`:
  - CLI 인자: `<YYYY-MM-DD>` 또는 `<book_id>` (숫자) 또는 `--force`
  - `--force` 없으면 이미 존재하는 daily 파일 **재사용** (Claude 호출 0회). today.json + 인덱스만 갱신.
  - `save_report()` → 매번 `rebuild_books_index()` 호출해 인덱스 무결성 유지.
  - 기본 모델: **Opus 4.7**, `CLAUDE_MODEL` env로 오버라이드 가능 (빈 문자열도 폴백).
- `push_to_notion.py`:
  - CLI 인자: `<YYYY-MM-DD>` 또는 `<book_id>` (없으면 today.json 사용)
  - `upsert_report()` — `(Book ID, Date)` 키로 Notion DB 조회 → 있으면 `pages.update` + 기존 child 블록 삭제 후 재append, 없으면 `pages.create`.

### 1.4 외부 추천 (새로 추가, 이번 세션)
- Claude에 100권 목록을 **제외 목록**으로 전달. `next_recommendations`는 이 100권 **밖의** 고전으로.
- 응답 스키마: `{title, author, reason, external: true}` — `book_id` 없음.
- 프론트 `renderRecommendations`:
  - `book_id` 있음 → 기존 앱 내 로드
  - `book_id` 없음 → Perplexity 검색 탭 열기 (`↗ Perplexity에서 열기` 배지)
- Legacy daily 파일(`2026-04-19~22.json`)은 기존 내부 추천 유지 → 두 경로 공존.
- `fallback_report()`는 내부 추천 유지 (Claude 실패 시 안전망).

## 2. 작업 중이던 사항 — ✅ 구현 완료 (커밋 대기)

### 2.1 "외부 추천도 리포트로 만들기" — 구현됨

**구현 요약**:
- `generate_daily_report.add_external_book(title, author)`: 정규화 dedupe, source_rank=4로 books.json 추가
- `load_books(include_external)`: 기본은 외부 제외 (daily 로테이션 보호). on-demand 경로만 포함.
- `generate_for_external(title, author)`: 외부 책 등록 + canonical date 계산 + 기존 generate_for_date 파이프라인 재사용
- `rebuild_books_index`: source_rank≥4 엔트리에 `external: true, title_norm, author_norm` 부여
- Worker: `{kind: "external", title, author}` 수용, workflow_dispatch에 inputs 전달. 헤더 인젝션/길이 검증 포함.
- `generate-book.yml`: inputs 세 개(book_id, title, author) 중 적절한 쪽으로 분기. 외부의 경우 books.json도 커밋.
- 프런트 `loadExternalBookReport(title, author)`: 인덱스에 이미 있으면 즉시 로드, 없으면 Worker 디스패치 + (title_norm, author_norm) 매칭 폴링.
- `renderRecommendations`: Worker 있으면 "→ 리포트 생성" 배지, 없으면 "↗ Perplexity" 배지 (자동 폴백).

**검증**: 43 테스트 PASS (외부 책 유닛 8개, 외부 E2E 2개, 기존 전체 GREEN 유지).

### 2.1-legacy (아래는 과거 설계 메모 — 더 이상 작업 대상 아님)

**요구**: 외부 추천 카드 클릭 시 Perplexity 대신 **앱 내 Claude 리포트**로 보고 싶음.

**현 상태 제약**:
- `generate_daily_report.py`의 canonical-date 배치는 `pick_book()` 기반 → `book_id`가 `books.json`에 있어야 함
- 외부 고전은 `books.json`에 없으므로 이 경로가 막힘
- `data/daily/<date>.json` 포맷도 "날짜 1개 = 책 1권" 전제

**설계 선택지 (우선순위 순)**

#### 옵션 A — books.json에 외부 책 자동 편입 (권장)
새 엔드포인트/스크립트 `generate_external_report.py`:
```
python generate_external_report.py "Prometheus Bound" "Aeschylus"
```
1. books.json의 max id + 1을 새 id로 발급
2. source_rank=3 (확장)으로 books.json에 append (커밋됨)
3. 다음 canonical date 계산: `START_DATE + (new_idx) days` — 하지만 이건 **미래 날짜**가 됨
4. 해당 날짜에 Claude 호출로 리포트 생성 (신선한 프롬프트: 외부 책용 제약 없음)
5. `data/daily/<date>.json` 저장, books-index.json 갱신
6. Notion 업서트
7. 클라이언트가 인덱스에서 찾아 기존 루트로 렌더

**워크플로 `generate-external-book.yml`**:
```yaml
on:
  workflow_dispatch:
    inputs:
      title:
      author:
      category: { default: "Classic" }
      tradition: { default: "Unknown" }
```

**Worker 확장**: 기존 Worker에 `/external` 경로 또는 body `{kind:"external", title, author}` 수용. 검증: title/author 길이 상한 + 특수문자 제한.

**장점**: 기존 렌더링·인덱스·Notion 파이프라인 그대로 재사용.
**단점**: books.json이 무한히 커질 수 있음. 중복 추가 방지 키 필요 (`(author, title)` 튜플 dedupe).

#### 옵션 B — 날짜 독립 저장소 (data/books/<id>.json)
- 외부 책은 날짜-기반 저장 안 씀, book_id만으로 파일명
- 새 인덱스 키: `external_books`
- 클라이언트 로드 경로가 두 갈래로 분기 — 복잡도 증가

#### 옵션 C — 동적 URL 슬러그 (title-author hash)
- 파일명: `data/ext/<hash>.json`
- 프런트가 hash로 조회. 복잡하고 관리 비용 큼.

**권장 = 옵션 A**. books.json을 "앱이 아는 책 목록" 으로 재정의, source_rank=4 같은 태그로 "외부 동적 추가본" 구분하면 기존 read path 100% 재사용 가능.

### 2.2 옵션 A 구현 순서 (다음 세션 시작점)

1. **books.json 확장 규약 합의**:
   - source_rank 4 신설 ("dynamically added from recommendation click")
   - tradition/category는 Claude에게 분류 요청해서 자동 채움
   - dedupe 키 `(lower(author), lower(title))` 정규화 — 이미 있으면 재사용

2. **`generate_external_report.py`** 신규 작성 (또는 `generate_daily_report.py` 에 `--external title author` 플래그):
   ```python
   def add_external_book(title: str, author: str) -> dict:
       books = json.loads(BOOKS_PATH.read_text(encoding='utf-8'))
       key = (author.strip().lower(), title.strip().lower())
       for b in books:
           if (b['author'].strip().lower(), b['title'].strip().lower()) == key:
               return b
       new_id = max(b['id'] for b in books) + 1
       # 간단 분류: 외부 추천의 경우 Claude에게 한 번 더 메타 쿼리하거나, 템플릿만
       new = {
           'id': new_id,
           'author': author,
           'title': title,
           'category': 'Classic',
           'tradition': 'Unknown',
           'source_rank': 4,
           'source_basis': 'User-requested external recommendation'
       }
       books.append(new)
       BOOKS_PATH.write_text(json.dumps(books, ensure_ascii=False, indent=2), encoding='utf-8')
       return new
   ```

3. **프롬프트 분기**: 외부 책을 위한 별도 `build_prompt_external()`:
   - "출처 기준" 자리 대체
   - 제외 목록 여전히 전달 (순환 추천 방지)

4. **`generate_for_date`** 에 외부 책 파라미터로 래퍼. canonical date 계산 로직은 그대로.

5. **Worker `src/index.js`** 확장:
   ```javascript
   if (body.kind === "external") {
     // validate title/author strings, length, charset
     // dispatch generate-external-book.yml with inputs
   }
   ```
   또는 단일 워크플로 `generate-book.yml` 가 옵션 분기:
   ```yaml
   inputs:
     book_id:  # optional
     title:    # optional (external)
     author:   # optional (external)
   ```
   run step에서 어느 쪽이 주어졌는지 감지.

6. **프런트 `renderRecommendations`** 수정:
   - 외부 추천 카드 클릭 시 (현재 Perplexity 열기) → **Worker `kind:"external"` 요청 + 생성 중 상태 + 폴링**
   - books-index.json 에 새 id가 등장하는지 폴링 (단, id는 미리 예측 불가 → 대안: (author, title) 매칭 폴링)
   - 더 나은 방법: Worker 응답에서 새로 할당된 `book_id`를 반환 받기

7. **새 인덱스 스키마 제안** (외부 책 매칭용):
   ```json
   {
     "books": {
       "101": {
         "latest": "2026-08-07",
         "dates": ["2026-08-07"],
         "external": true,
         "title_norm": "prometheus bound",
         "author_norm": "aeschylus"
       }
     }
   }
   ```
   프런트는 클릭 시점에 `title_norm + author_norm`으로도 조회 가능 → 외부 추천 → 이미 생성된 책인지 판별.

8. **테스트 추가**:
   - `tests/unit/test_external_add.py`: `add_external_book()` dedupe, id 할당, books.json 저장 검증
   - `tests/integration/`: 외부 책 추가 → 기존 save_report 경로 → 인덱스에 올바르게 등재
   - `tests/e2e/`: 외부 추천 카드 클릭 → 생성 중 상태 → (mock 없이) 실제 Worker는 호출 안 함 (테스트 전용 WORKER_URL 사용)

### 2.3 부수 이슈 목록

- **E2E 2건 skip**: `test_e2e_04`, `test_e2e_08` — 오늘 추천 3개 중 2개가 이미 인덱스에 있으면 unindexed 후보 부족으로 skip. 지금은 book 7, 12가 인덱스돼있어서 책 8 하나뿐. 데이터 의존 테스트라 수용할만함. 대안: 오늘의 책을 동적으로 바꿔서 다양한 recs를 보이게 하거나, E2E 전용 고정 fixture 데이터 주입.
- **Notion 과거 중복**: 이번 upsert 로직은 "앞으로 생길 중복만" 방지. 기존에 쌓인 중복 페이지는 사용자가 수동 청소 필요.
- **`data/books-index.json`** 은 빌드 타임 생성물이지만 커밋됨 (Pages가 정적 호스팅이라 동적 갱신 불가). 이 설계는 유지.
- **Opus 4.7 비용**: 월 30~50 호출 기준 미미하지만, on-demand가 많아지면 체감 증가 가능. 월별 모니터링 추천.
- **사용자 secret 관리**:
  - `ANTHROPIC_API_KEY`, `NOTION_API_KEY`, `NOTION_DATABASE_ID`, `CLAUDE_MODEL` (선택), `READING_MODE`, `TIMEZONE`, `START_DATE` — GitHub repo secrets
  - `GITHUB_TOKEN` (Fine-grained PAT, Actions: write) — Cloudflare Worker secret
  - `SLACK_WEBHOOK_URL` — daily-update.yml 에서만 사용

## 3. 테스트 현황 (최신)

```
tests/unit/test_books_index.py          7 PASS
tests/unit/test_save_report_hook.py     3 PASS
tests/unit/test_skip_if_exists.py       6 PASS
tests/unit/test_notion_upsert.py        8 PASS
tests/integration/test_save_report_flow.py  1 PASS
tests/e2e/test_recommendation_click.py  9 PASS + 2 skip (데이터 의존)
─────────────────────────────────────────────
33 pass / 2 skip (총 35)
```

실행: `python -m pytest tests/ -q` (≈25초)

## 4. 핵심 파일 지도 (다시 시작할 때 먼저 열어볼 것)

### 서버 쪽
- `generate_daily_report.py` — 생성 + save + 인덱스 재구성의 단일 출처
- `push_to_notion.py` — Notion upsert
- `.github/workflows/generate-book.yml` — on-demand 엔트리 포인트

### 클라이언트 쪽
- `index.html` — 단일 파일. 의미 블록:
  - `WORKER_URL` (line ~108): 현재 `https://gbd-dispatch.books-dailiy.workers.dev`
  - `renderRecommendations` (line ~115) — 외부/내부 분기 **여기에 외부→리포트 로직을 확장**
  - `loadBookReport` (line ~295) — 내부 책 자동 생성·폴링 플로우. 외부 책용 분기/래퍼 추가 필요
  - `buildGeneratingState` (line ~252) — 재사용 가능
  - `pollForReport` (line ~283) — book_id 대신 `(author, title)` 매칭 모드가 필요해질 수도

### 인프라
- `cloudflare-worker/src/index.js` — body 검증, GITHUB_TOKEN 보관. 외부 요청용 kind 분기 추가 지점
- `cloudflare-worker/wrangler.toml` — `workers_dev = true` 유지 (CF v4 요구)

### 문서
- `docs/requirements/book-recommendation-click-rtm.md` — RTM (최종 상태)
- `docs/architecture/book-recommendation-click.md` — 아키텍처 문서 (초기 설계. 외부 추천 기능 반영 필요)
- `reports/book-recommendation-click-completion.md` — 초기 HALO 완료 보고
- **이 파일** — 이후 세션 브리프

## 5. 재개 체크리스트

다음 세션 시작 시:

- [ ] `git log --oneline -10` — 원격에 내가 모르는 커밋이 있는지 확인
- [ ] `python -m pytest tests/ -q` — 현재 상태 그린 확인
- [ ] `python -c "import json; print(len(json.load(open('data/books-index.json',encoding='utf-8'))['books']))"` — 인덱스 크기 확인
- [ ] 옵션 A 구현 시작: `books.json` 확장 규약을 사용자와 한번 더 확인 (source_rank=4, category=Classic 기본값 OK 인지)
- [ ] `generate_daily_report.py --external "<title>" "<author>"` 인터페이스부터 TDD RED
- [ ] Worker 확장 (로컬 dev server로 먼저 검증: `npm run dev` in cloudflare-worker)
- [ ] 프런트 외부 카드 클릭 핸들러 수정 + E2E 추가

## 6. 권한·보안 재확인

- Cloudflare Worker `GITHUB_TOKEN` secret 잠재 회전 주기: 1년 (Fine-grained PAT 만료일 기준)
- Worker ALLOWED_ORIGINS:
  - `https://inesinesinesines.github.io`
  - `http://127.0.0.1:8765` (dev)
  - `http://localhost:8765` (dev)
- `.gitignore`: `githubkey.txt`, `*.token`, `*.pat`, `.env`, `.claude/`, `__pycache__/` — 유출 방지 완료

## 7. 메모

- 사용자 선호: 한국어 UX, 콘솔/터미널 출력은 짧고 요점 중심
- 사용자 가치 판단: 기능 완결도 > 우아함. "진짜 동작" 이 우선.
- Notion 앱 적극 사용자 — upsert 정책이 실제 소비자 측면에서 중요.
- "테스트해보고 안 되면 알려줘" 스타일 — 실수 인정하고 빠르게 수정하는 흐름 자연스러움.
