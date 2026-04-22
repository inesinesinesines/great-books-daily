# Great Books Daily — Project Instructions

## Product Summary
매일 Great Books 1권을 자동 선택해 Claude API로 리포트(JSON)를 생성하고, 정적 웹(`index.html`) + Notion DB에 누적하는 서비스.
배포는 GitHub Pages + GitHub Actions(`daily-update.yml`, `backfill.yml`).

## Layout
```
books.json              # 100권 마스터 데이터 (id, author, title, category, tradition, source_rank)
books-ranked.json       # 출처 기반 재정렬판
data/today.json         # 오늘의 리포트
data/daily/{YYYY-MM-DD}.json  # 날짜별 리포트 (BackFill 포함)
generate_daily_report.py      # Claude API 호출 + JSON 저장
push_to_notion.py             # Notion DB 적재
run_daily.py                  # 위 2개를 순차 실행
index.html                    # GitHub Pages 진입 페이지 (data/today.json fetch)
.github/workflows/            # daily-update, backfill
```

## Tech Stack
- Python 3 (anthropic, python-dotenv, notion-client — `requirements.txt`)
- 정적 프론트(바닐라 JS, 단일 `index.html`)
- GitHub Actions로 스케줄/백필

## Conventions
- 한국어 UX/본문 (코드 주석은 영문 가능)
- JSON은 `ensure_ascii=False`, 들여쓰기 2
- 파일명·경로는 루트에 평탄하게 두는 현재 구조를 유지
- 날짜/타임존은 `TIMEZONE`(기본 `Asia/Seoul`) 기준

## Key Env Vars
`ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `NOTION_API_KEY`, `NOTION_DATABASE_ID`, `READING_MODE`(ranked|strict|extended), `TIMEZONE`, `START_DATE`, `WEB_APP_URL`, `JSON_BASE_URL`

## HALO Workflow
이 저장소는 HALO Workflow v3 규약을 사용한다.

### Usage
```
/halo-workflow [feature description]
```

### Core Principles
- **RTM = Single Source of Truth** — 매 Phase가 RTM 업데이트. JUDGE는 RTM만 읽고 판별.
- **Main Agent First** — P1~P7 메인 연속 실행. 서브는 P8(리뷰)과 JUDGE(판별)에만.
- **File = Interface** — 에이전트 간 통신과 context 복구는 파일로만.
- **Constraint Verification** — 외부 의존성(Claude API, Notion, GitHub Pages)은 실제 호출로 검증.
- **Real E2E** — E2E는 실제 환경. Mock 금지.
- **LOOPBACK never changes requirements** — 요구사항 변경 = 새 사이클.
- **Max 5 LOOPBACK, per-phase 2 max** — 초과 시 Partial Report → P9.

### Execution Model
- **Main direct** (8 Phases): P1→P2→P3→P4→P5→P6→P7→P9 — 컨텍스트 단절 0
- **Sub-agents** (2 points): P8 review (×3), JUDGE (×1 — RTM만 읽고 판별)

### RTM Flow
P1(REQ등록) → P4(Unit TC매핑) → P5(구현위치매핑) → P6(IT/E2E TC매핑) → P7(결과기록) → P8(리뷰반영) → JUDGE(RTM읽고 판별)

### Artifact Locations
```
docs/requirements/{feature}.md       # P1
docs/requirements/{feature}-rtm.md   # P1~P8 RTM (Single Source of Truth)
docs/architecture/{feature}.md       # P3
tests/unit/                          # P4 (pytest 권장)
tests/integration/                   # P6
tests/e2e/                           # P6 — 실제 환경 (예: Playwright로 index.html 검증, 실제 data/daily/*.json 사용)
reports/{feature}-completion.md      # P9
.workflow/                           # 런타임 체크포인트 (gitignored)
```

### Project-Specific Notes
- 이 프로젝트는 `src/` 레이아웃을 쓰지 않는다. Python 스크립트는 루트에, 프론트는 `index.html` 단일 파일.
- 구현 단계(P5)에서 새 Python 모듈은 기존 관행대로 루트(또는 얕은 하위 디렉토리)에 둔다.
- 동적 생성이 필요한 기능은 GitHub Pages가 정적이라는 제약을 기억할 것(GitHub Actions workflow_dispatch / repository_dispatch / 별도 서버리스 endpoint 등을 P3에서 결정).

## Agent Definitions
Sub-agent definition (P8 reviewer) is in `.claude/commands/agents/`.
