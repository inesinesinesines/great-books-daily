# GitHub Pages 배포 메모

이 프로젝트는 GitHub Pages 기준으로 바로 배포할 수 있게 정리되었습니다.

## 권장 저장소명
`great-books-daily`

## 권장 구조
- `index.html` : 메인 웹앱 진입 파일
- `data/today.json` : 오늘의 리포트
- `data/daily/*.json` : 날짜별 아카이브

## GitHub Pages URL
- WEB_APP_URL: `https://inesinesinesines.github.io/great-books-daily/`
- JSON_BASE_URL: `https://inesinesinesines.github.io/great-books-daily/data`

## GitHub 설정 순서
1. GitHub에서 public repository `great-books-daily` 생성
2. 이 폴더의 파일들을 repository root에 업로드
3. GitHub 저장소의 `Settings` → `Pages` 이동
4. `Build and deployment`에서 `Deploy from a branch` 선택
5. Branch는 `main`, folder는 `/ (root)` 선택
6. 저장 후 배포 완료까지 대기

## 확인할 URL 예시
- 웹앱: `https://inesinesinesines.github.io/great-books-daily/`
- today.json: `https://inesinesinesines.github.io/great-books-daily/data/today.json`
- 날짜별 JSON: `https://inesinesinesines.github.io/great-books-daily/data/daily/2026-04-20.json`

## .env 예시
```env
WEB_APP_URL=https://inesinesinesines.github.io/great-books-daily/
JSON_BASE_URL=https://inesinesinesines.github.io/great-books-daily/data
```
