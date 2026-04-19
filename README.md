# Great Books Daily Service (Python Draft)

이 초안은 다음 요구사항을 포함합니다.

- UChicago Basic Program / Great Books 스타일 100권 목록
- 매일 한 권 자동 선택
- Perplexity API로 하루치 JSON 생성
- 생성된 JSON을 `today.json` 및 날짜별 파일로 저장
- Notion DB에 하루치 리포트를 row/page로 누적 저장
- 웹앱에서 `today.json`을 읽어 오늘의 리포트를 표시
- 사용자가 Perplexity에 추가 질문을 보낼 수 있는 창 제공

## 폴더 구성

- `books.json`: 100권 마스터 데이터
- `config.example.env`: 환경변수 예시
- `requirements.txt`: Python 의존성
- `generate_daily_report.py`: Perplexity API로 오늘의 리포트 JSON 생성
- `push_to_notion.py`: 오늘의 JSON을 Notion DB에 적재
- `run_daily.py`: 생성 + 적재를 한 번에 실행
- `webapp.html`: 브라우저용 앱

## 1) 환경 준비

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.env .env
```

`.env`에 아래 값을 채우세요.

- `PPLX_API_KEY`
- `NOTION_API_KEY`
- `NOTION_DATABASE_ID`
- `WEB_APP_URL`
- `JSON_BASE_URL`

## 2) Notion DB 권장 스키마

아래 속성을 가진 데이터베이스를 만들어 두는 것을 권장합니다.

- Name (title)
- Date (date)
- Book ID (number)
- Author (rich_text)
- Title (rich_text)
- Category (select)
- Tradition (select)
- One-line Summary (rich_text)
- Five-minute Summary (rich_text)
- Keywords (multi_select)
- Discussion Question (rich_text)
- Why Now (rich_text)
- JSON URL (url)
- Web App URL (url)

## 3) 실행

```bash
python run_daily.py
```

또는 개별 실행:

```bash
python generate_daily_report.py
python push_to_notion.py
```

## 4) 스케줄러 예시 (cron)

매일 12:10 실행 예시:

```cron
10 12 * * * cd /path/to/uchicago-service && /path/to/venv/bin/python run_daily.py >> service.log 2>&1
```

## 5) 배포 방식

- `data/today.json`, `data/daily/*.json`을 정적 호스팅 경로에 배포
- `webapp.html`도 함께 배포
- 웹앱은 `today.json`을 fetch해서 오늘의 리포트를 그림
- Notion 앱에서는 DB 아카이브로 과거 리포트를 다시 볼 수 있음

## 6) 운영 팁

- 처음엔 fallback 로직을 켜 둔 채 시작하고, API 응답 포맷이 안정화되면 검증 로직을 강화하세요.
- 같은 날짜 중복 적재를 막으려면 `push_to_notion.py`에서 먼저 해당 날짜를 query하는 로직을 추가하면 됩니다.
- 나중에는 메일/텔레그램 발송 스크립트도 `run_daily.py` 뒤에 붙이면 됩니다.


## 7) 출처 기반 재정렬판

`books-ranked.json`은 Basic Program 공개 페이지를 기준으로 3단계로 재정렬한 목록입니다.

- 1순위: 공개 페이지/샘플 커리큘럼에서 직접 확인되는 작품
- 2순위: 페이지에 명시된 대표 저자군 기반 보강
- 3순위: Basic Program 기반 Great Books 전통에 따라 확장 보강한 작품

앱에서 더 엄밀한 출처 기준을 쓰려면 `books.json` 대신 `books-ranked.json`을 읽도록 바꾸면 됩니다.


## 8) 출처 우선 읽기 흐름 + 다음 책 추천

이 버전은 `source_rank`를 기준으로 출처에 가까운 책부터 먼저 읽고, 이후 확장 고전으로 넓혀가는 흐름을 지원합니다.

- `READING_MODE=ranked`: 1→2→3 순으로 전체 진행
- `READING_MODE=strict`: 1→2까지만 진행
- `READING_MODE=extended`: 전체 100권 그대로 진행

생성되는 `today.json`에는 `next_recommendations` 필드가 포함되며, 웹앱과 Notion 모두 다음에 읽을 책 3권을 보여줄 수 있습니다.


## 9) Claude API 사용 버전

이 버전은 Perplexity API 대신 Anthropic Claude API를 사용합니다.

- 환경변수: `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`
- 기본 모델 예시: `claude-sonnet-4-5-20250929`
- API 키는 Anthropic Console에서 생성

실행 순서:
1. `pip install -r requirements.txt`
2. `.env`에 Claude/Notion 값 입력
3. `python generate_daily_report.py`
4. `python push_to_notion.py`


## 10) GitHub Pages 배포 권장값

GitHub 사용자명이 `inesinesinesines`이고 저장소명을 `great-books-daily`로 만들 경우 권장 URL은 아래와 같습니다.

- `WEB_APP_URL=https://inesinesinesines.github.io/great-books-daily/`
- `JSON_BASE_URL=https://inesinesinesines.github.io/great-books-daily/data`

이 버전에는 `index.html`이 포함되어 있어 GitHub Pages에서 기본 진입 페이지로 바로 사용할 수 있습니다.
