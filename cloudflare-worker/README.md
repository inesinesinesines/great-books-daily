# gbd-dispatch — Cloudflare Worker

프런트(정적 GitHub Pages)에서 `generate-book.yml` 워크플로를 원클릭으로 트리거할 수 있도록 해주는 얇은 프록시.

```
[브라우저] → POST /generate {book_id}
             │
             ▼
[Cloudflare Worker]   ← GITHUB_TOKEN (Wrangler secret)
             │
             ▼
[GitHub REST workflow_dispatch]
             │
             ▼
[Actions: generate-book.yml → data/daily 커밋 → Pages 재배포]
```

## 처음 한 번만 배포

### 1. 의존성 설치
```bash
cd cloudflare-worker
npm install
```

### 2. Cloudflare 로그인 (브라우저 팝업)
```bash
npx wrangler login
```

### 3. GitHub PAT을 Worker 시크릿에 등록
```bash
npx wrangler secret put GITHUB_TOKEN
```
프롬프트가 뜨면 PAT 값을 붙여 넣고 Enter. (터미널에 값이 남지 않음)

### 4. 배포
```bash
npx wrangler deploy
```

배포 완료 후 Wrangler가 `https://gbd-dispatch.<your-cf-subdomain>.workers.dev` 주소를 출력합니다. 그 주소를 복사해서 다음 두 곳에 반영하세요:

- 저장소 `index.html` 상단 JS 상수 `WORKER_URL` (비어 있으면 Worker 호출 경로가 비활성화되고 기존 GitHub Actions 링크 동작으로 폴백합니다)

## 운영 중 명령

| 명령 | 용도 |
|---|---|
| `npm run tail` | 실시간 로그 스트림 |
| `npm run deploy` | 코드 변경 후 재배포 |
| `npx wrangler secret put GITHUB_TOKEN` | PAT 로테이션 |
| `npx wrangler secret delete GITHUB_TOKEN` | 비상시 비활성화 |

## 보안 경계

- **Origin 허용 목록**: `index.js` 상단 `ALLOWED_ORIGINS`에 GitHub Pages 도메인 + 로컬 dev만 포함.
- **PAT 스코프 최소화**: Fine-grained PAT, `Actions: Read and write` + `Contents: Read` 만 권장.
- **Rate limiting**: Worker 자체에는 없음 — 동일 `book_id` 반복 dispatch는 GitHub Actions가 idempotent하게 처리 (리포트가 이미 있으면 커밋 없이 종료).
- **PAT 유출 방지**: Wrangler 시크릿은 브라우저/로그/응답 어디에도 노출되지 않음. 로컬 `.dev.vars` 파일도 gitignore됨.

## 로컬 테스트
```bash
echo 'GITHUB_TOKEN="<your-pat>"' > .dev.vars    # 로컬 전용
npm run dev
# 별도 터미널:
curl -X POST http://127.0.0.1:8787 \
  -H "Origin: https://inesinesinesines.github.io" \
  -H "Content-Type: application/json" \
  -d '{"book_id": 7}'
```
