# Completion Report: Book Recommendation Click-to-View

## Metadata
- Workflow: HALO v3
- Feature slug: `book-recommendation-click`
- Started: 2026-04-22
- Completed: 2026-04-22
- LOOPBACK count: 0
- Judge verdict: **PASS**

## 1. Feature Summary

"다음에 읽을 책 추천" 카드가 이제 클릭 가능하다. 클릭 시:
- `data/daily/` 내에 해당 책(book_id)의 공식 리포트가 있으면 그것을 메인 뷰에 렌더한다.
- 없으면 `books.json` 메타 기반으로 **클라이언트 프리뷰**를 즉석 합성해 렌더하고, `localStorage`에 캐시한다. 메인 뷰 상단에 "프리뷰" 칩이 표시된다.

정적 호스팅 제약(GitHub Pages)을 준수하기 위해, 서버-측 영구 저장은 `generate_daily_report.save_report()`가 호출될 때 `rebuild_books_index()`가 자동으로 `data/books-index.json`을 갱신하는 방식으로 해결했다. 클라이언트는 이 인덱스로 `book_id → date` 리졸빙을 수행한다.

### 변경 요약
- 🆕 `data/books-index.json` — 서버가 유지하는 book_id → date 인덱스
- 🆕 `rebuild_books_index()` 함수 + `save_report()` 훅 (generate_daily_report.py)
- 🔧 `index.html` — 클릭 핸들러, 프리뷰 합성, 인덱스 조회, 키보드 접근성, clickToken 레이스 가드
- 🔧 GitHub Actions — `daily-update.yml` / `backfill.yml` 의 `git add`에 인덱스 파일 추가

## 2. Artifact List

### 산출물 (신규)
- `docs/requirements/book-recommendation-click.md`
- `docs/requirements/book-recommendation-click-rtm.md`
- `docs/architecture/book-recommendation-click.md`
- `tests/unit/test_books_index.py` (7 tests)
- `tests/unit/test_save_report_hook.py` (3 tests)
- `tests/integration/test_save_report_flow.py` (1 test)
- `tests/e2e/conftest.py` (fixtures)
- `tests/e2e/test_recommendation_click.py` (8 tests)
- `pytest.ini`
- `data/books-index.json`
- `reports/book-recommendation-click-completion.md` (본 파일)

### 변경
- `generate_daily_report.py` (rebuild_books_index 함수 추가, save_report 훅 1줄 추가, import 1줄 보강)
- `index.html` (CSS 일부, JS 블록 전반)
- `.github/workflows/daily-update.yml` (git add 확장)
- `.github/workflows/backfill.yml` (git add 확장)

### 변경 없음
- `books.json`, `books-ranked.json`, `push_to_notion.py`, `run_daily.py`

## 3. RTM Final State

- Total requirements: 17 (7 REQ + 4 NFR + 6 EDGE)
- TC mapped: 16/17 (94%) — EDGE-004 는 방어적 impl로만 커버
- Implementation complete: 17/17 (100%)
- Tests passing: 19/19 (100%)
  - Unit: 10/10
  - Integration: 1/1
  - E2E: 8/8 (no mocks)
- Status: Reviewed → **Verified (PASS)**

RTM 원본: `docs/requirements/book-recommendation-click-rtm.md`

## 4. Code Review Results

P8: 3명 병렬 리뷰어 (Quality/DRY, Bugs/Correctness, Conventions/Security).
- **CRITICAL**: 0
- **MAJOR**: 0 (두 개의 MAJOR 제기가 있었으나 트리아지 후 MINOR로 재분류 — 한 건은 UX 뉘앙스, 다른 한 건은 기존 토큰 가드가 이미 방어)
- **MINOR**: 6건 (R1~R6) — 모두 JUDGE에 의해 "Known Limitations / defensive-hardening backlog" 로 분류.

## 5. Test Results

```
$ python -m pytest tests/ -v
tests/unit/test_books_index.py .......          7 PASS
tests/unit/test_save_report_hook.py ...         3 PASS
tests/integration/test_save_report_flow.py .    1 PASS
tests/e2e/test_recommendation_click.py ........ 8 PASS
===================================================
19 passed in ~20s
```

E2E Quality Gate:
- [x] No mock/stub/spy in E2E
- [x] 실 http.server 기동
- [x] 실 `data/daily/*.json` + `data/books-index.json` + `books.json` 사용
- [x] Playwright chromium headless

## 6. LOOPBACK History

없음 (0회 LOOPBACK). 테스트 실행 중 E2E-08가 초기에 실패했으나 이는 테스트 설계 보정(DOM detach 문제 → `page.evaluate` 레이어로 레이스 검증)이었고, 요구사항이나 impl 수정 없이 해소되어 LOOPBACK 카운트에 포함하지 않음.

## 7. Known Limitations (P8 MINOR backlog)

향후 하드닝 기회 (현재 기능에는 영향 없음):

| Ref | 영역 | 제안 |
|-----|------|------|
| R1 | `rebuild_books_index` | `int(s)` 정렬 시 non-numeric book_id에 대해 try/except 또는 `str.isdigit()` 폴백 |
| R2 | `rebuild_books_index` | `date_str` 필드가 ISO 형식인지 검증 후 append (`re.match(r'\d{4}-\d{2}-\d{2}', ...)`) |
| R3 | `loadBookReport` 디스패치 | `Number.isInteger` 체크로 `book_id=null → 0` 폴백 방지 |
| R4 | `buildClientPreview` 날짜 | `todayDate` 사용 가능 시 우선, 아니면 현재 동작 유지 (Asia/Seoul 일관성) |
| R5 | 프리뷰 템플릿 중복 | Python `fallback_report` 와 JS `buildClientPreview` 가 독립 유지 — 필요 시 공통 JSON 템플릿화 |
| R6 | `#sourceBasis` DOM 노드 | 프리뷰 notice 전용 DOM 영역을 분리 (cosmetic) |

## 8. Next Steps

1. `data/books-index.json`이 커밋되어야 GitHub Pages가 서빙함 → `git add data/books-index.json` 확인 후 push.
2. 사용자 피드백을 수집해 위 R1~R6 backlog 중 우선순위 재평가.
3. 향후 클라이언트 프리뷰가 "정식처럼 보이는" 오해를 줄이기 위해 프리뷰 칩 카피 강화 여부 A/B 고려.

## 9. Sign-off

- [x] RTM Verified (PASS)
- [x] JUDGE 심판 통과
- [x] P8 review issues triaged (0 CRITICAL/MAJOR)
- [x] 모든 테스트 GREEN
- [x] 산출물 체크포인트 작성 완료
