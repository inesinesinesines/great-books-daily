배포 메모

1. 이 폴더를 서버 또는 GitHub 저장소에 업로드합니다.
2. 정적 호스팅 시 `webapp.html`과 `data/` 경로가 함께 배포되어야 합니다.
3. Python 스크립트는 서버/스케줄러에서 실행합니다.
4. Notion DB는 미리 생성해두고 integration을 연결합니다.
5. cron 또는 GitHub Actions schedule로 `python run_daily.py`를 실행합니다.
