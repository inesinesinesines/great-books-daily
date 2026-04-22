# Requirements: Book Recommendation Click-to-View

## 1. Functional Requirements

| REQ-ID | Requirement | Priority | Acceptance Criteria |
|--------|-------------|----------|---------------------|
| REQ-001 | "다음에 읽을 책 추천" 카드는 클릭 가능한 UI로 노출된다 | P1 | cursor: pointer, 포커스 가능 (button 또는 role=button), hover 시각 피드백 |
| REQ-002 | 카드 클릭 시 해당 책(book_id)의 리포트가 메인 뷰(`.hero` 영역)에 렌더된다 | P1 | 타이틀, 메타, 한줄/5분 요약, 키워드, why_now, discussion_question, source_basis, 다음 추천이 모두 갱신됨 |
| REQ-003 | `data/daily/` 내 파일 중 `book_id`가 일치하는 가장 최신 리포트가 이미 있으면 그것을 로드해 표시한다 | P1 | 인덱스로 책-id → 날짜 매핑 조회 후 해당 날짜 JSON 페치 성공 시 그대로 렌더 |
| REQ-004 | 해당 책 리포트가 data/daily/에 없으면 신규 생성해 저장 후 표시한다 | P1 | 클라이언트에서 즉시 "프리뷰 리포트"를 합성(books.json 메타 기반)해 렌더하고, 합성된 리포트를 book-id 기준으로 기록하는 매커니즘을 제공한다. 합성 본문에는 `generated_client_side: true` 플래그를 포함한다 |
| REQ-005 | 리포트 교체 후에도 날짜 네비게이션/테마/질의 상자 동작이 유지된다 | P2 | 이전/다음/오늘 버튼이 기존 대로 동작, 질의 상자는 새 책 기준으로 갱신 |
| REQ-006 | 리포트 파일에 포함된 `next_recommendations`도 다시 클릭 가능하게 렌더되어 연쇄 탐색을 지원한다 | P2 | 렌더 후 .rec-item에 동일한 click handler 바인딩 |
| REQ-007 | 추가된 static index는 빌드/배포 시 자동으로 최신화된다 | P2 | `generate_daily_report.save_report()`가 저장 시 `data/books-index.json`을 함께 업데이트 |

## 2. Non-Functional Requirements

| NFR-ID | Category | Requirement | Measurement |
|--------|----------|-------------|-------------|
| NFR-001 | Performance | 기존 리포트 클릭 → 렌더까지 800ms 이하 (캐시 미적용, 로컬 서버 기준) | Playwright trace |
| NFR-002 | Resilience | 인덱스 파일 없음 / 네트워크 오류 시에도 프론트는 부드럽게 프리뷰로 폴백 | 인덱스 404에도 렌더 성공 |
| NFR-003 | Security | 브라우저에서 Claude API 키 노출 금지 | 클라이언트 코드/네트워크 트래픽에 `ANTHROPIC_API_KEY`가 나타나지 않음 |
| NFR-004 | Accessibility | 카드는 키보드로도 활성화 가능 (Enter/Space) | role=button + tabindex + keydown 핸들러 |

## 3. Edge Cases

| EDGE-ID | Scenario | Expected Behavior | Related REQ |
|---------|----------|-------------------|-------------|
| EDGE-001 | 해당 책의 리포트가 `data/daily/` 어디에도 없음 | `books.json` 메타로 프리뷰 리포트를 합성해 렌더 (`generated_client_side: true`) | REQ-004 |
| EDGE-002 | 인덱스 파일(`books-index.json`) 자체가 404 | 날짜 순회 없이 곧장 프리뷰 모드로 폴백, 콘솔 경고만 남김 | NFR-002 |
| EDGE-003 | 사용자가 같은 카드를 빠르게 연속 클릭 | 마지막 요청의 결과만 렌더 (이전 인플라이트 요청은 버림) | REQ-002 |
| EDGE-004 | 추천 책 id가 books.json에 없음 | 렌더를 차단하고 콘솔 에러, 화면에 "리포트를 불러올 수 없습니다" 표시 | REQ-003 |
| EDGE-005 | 리포트 JSON은 있지만 스키마가 부분 누락 | 누락 필드는 빈 값으로 안전 렌더 (기존 `render()` 패턴과 동일) | REQ-002 |
| EDGE-006 | 클릭 후 사용자가 "오늘" 버튼 누름 | 오늘의 리포트로 복구 | REQ-005 |

## 4. Constraints (Verified)

- **정적 호스팅(GitHub Pages)**: 브라우저에서 서버 파일을 쓸 수 없음 → "저장"은 빌드 타임에 수행된 후 인덱스로 노출하거나, 클라이언트 프리뷰/localStorage 수준에서 수행.  *검증: index.html은 `fetch('./data/...')` 읽기만 사용함. 쓰기 엔드포인트 없음.*
- **기존 리포트 스키마**: `data/today.json`·`data/daily/YYYY-MM-DD.json` 스키마 일치 확인. `book_id`, `title`, `author`, `summary[]`, `next_recommendations[]` 필수. *검증: 2026-04-19~22 4개 파일 검토.*
- **Python 3.13 런타임**: GitHub Actions runner와 로컬 일치. *검증: `python --version` = 3.13.5.*
- **pytest/Playwright 사용 가능**: P4/P6 테스트 가능. *검증: `pip install pytest playwright` 성공, `playwright install chromium` 성공.*
- **ANTHROPIC_API_KEY**: 서버(GitHub Actions)에서만 사용. 프런트 노출 금지. *검증: index.html에 키 참조 없음.*

## 5. System Decisions (Not Greenfield)

기존 프로젝트 — System Decisions는 신규 결정 없이 기존 규약(바닐라 JS 단일 index.html + 루트 Python 스크립트) 준수.

## 6. Decisions (Auto-resolved)

- **"저장" 의미**: 정적 호스팅 제약상 브라우저에서 `data/daily/`로 실시간 쓰기는 불가. "저장"은 (a) 클라이언트-측 `localStorage` 캐시, (b) `generate_daily_report.py` 재실행/워크플로를 통한 서버-측 영구 저장 두 층으로 해석. 프리뷰 본문은 `generated_client_side: true`로 식별.
- **책-id → 날짜 매핑**: `pick_book`이 결정적이므로 `data/books-index.json`을 빌드 시 만든다. 포함 필드: `{ "<book_id>": ["YYYY-MM-DD", ...] }` 중 가장 최근 항목 선택.
- **테스트 경계**: JS 로직(인덱스 조회, 프리뷰 합성, 클릭 핸들러)은 Playwright(E2E)로 검증. Python 변경분(`save_report` 인덱스 갱신, 프리뷰 합성 로직의 파이썬 레퍼런스 포트)은 pytest(Unit)로 검증.
- **E2E 스코프**: `python -m http.server`로 프로젝트 루트를 서빙, Playwright chromium이 `http://127.0.0.1:PORT/`를 로드해 실 JSON을 사용. 모킹 금지.
