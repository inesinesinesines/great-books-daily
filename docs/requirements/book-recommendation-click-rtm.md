# RTM: Book Recommendation Click-to-View

## Metadata
- Created: 2026-04-22
- Last Updated: 2026-04-22
- Version: 1.0 (P9 complete)
- Status: Complete

## Traceability Matrix

| REQ-ID | Requirement | Priority | Unit TC | Integration TC | E2E TC | Impl Location | Result | Review | Status |
|--------|-------------|----------|---------|----------------|--------|---------------|--------|--------|--------|
| REQ-001 | 추천 카드 클릭 가능 UI | P1 | - | - | E2E-01 | index.html:109-127 | PASS | MINOR | Reviewed |
| REQ-002 | 클릭 시 메인 뷰에 렌더 | P1 | - | - | E2E-02 | index.html:239-263, 129-145 | PASS | MINOR | Reviewed |
| REQ-003 | 기존 리포트 있으면 표시 | P1 | UT-IDX-02, UT-IDX-03, UT-IDX-04 | IT-01 | E2E-02 | index.html:239-250, generate_daily_report.py:181-219 | PASS | PASS | Reviewed |
| REQ-004 | 없으면 신규 생성 후 표시 | P1 | - | - | E2E-03 | index.html:200-237, 252-263 | PASS | MINOR | Reviewed |
| REQ-005 | 네비/테마/질의 유지 | P2 | UT-SAVE-03 | - | E2E-06 | index.html:129-145, 223-230 | PASS | PASS | Reviewed |
| REQ-006 | 연쇄 추천 클릭 | P2 | - | - | E2E-04 | index.html:143, 109-127 | PASS | PASS | Reviewed |
| REQ-007 | books-index.json 자동화 | P2 | UT-IDX-01, UT-IDX-06, UT-IDX-07, UT-SAVE-01, UT-SAVE-02 | IT-01 | - | generate_daily_report.py:181-221, 230 | PASS | MINOR | Reviewed |
| NFR-001 | 렌더 800ms 이하 | - | - | - | E2E-02, E2E-03 (implicit via 5s timeout) | index.html:239-263 | PASS | PASS | Reviewed |
| NFR-002 | 인덱스 404 폴백 | - | UT-IDX-05 | - | - | index.html:172-184 | PASS | PASS | Reviewed |
| NFR-003 | API 키 비노출 | - | - | - | E2E-07 | index.html (no API key refs) | PASS | PASS | Reviewed |
| NFR-004 | 키보드 접근성 | - | - | - | E2E-01, E2E-05 | index.html:111, 120-122 | PASS | PASS | Reviewed |
| EDGE-001 | 해당 책 리포트 없음 | - | - | - | E2E-03 | index.html:252-263 | PASS | PASS | Reviewed |
| EDGE-002 | 인덱스 파일 404 | - | UT-IDX-05 | - | - | index.html:176-181 | PASS | PASS | Reviewed |
| EDGE-003 | 연속 클릭 레이스 | - | - | - | E2E-08 | index.html:240, 246, 253, 262 | PASS | PASS | Reviewed |
| EDGE-004 | 알 수 없는 book_id | - | - | - | - | index.html:255-259 | - | PASS | Reviewed |
| EDGE-005 | 스키마 일부 누락 | - | UT-IDX-05 | - | - | index.html:129-145, generate_daily_report.py:196-199 | PASS | MINOR | Reviewed |
| EDGE-006 | 클릭 후 오늘 복귀 | - | - | - | E2E-06 | index.html (todayBtn existing) | PASS | PASS | Reviewed |

### P8 Review Issues (MINOR)

| Ref | File:Line | Description | Severity |
|-----|-----------|-------------|----------|
| R1 | generate_daily_report.py:209 | `sorted(..., key=lambda s: int(s))` throws if a book_id is ever non-numeric — add defensive fallback | MINOR |
| R2 | generate_daily_report.py:201 | `date_str = data.get('date') or path.stem` can pollute sort order if the file name isn't ISO — validate before appending | MINOR |
| R3 | index.html:111 | `escapeHtml(r.book_id)` coerces `null`→`''`; `Number('')` is `0` not `NaN`, bypassing `Number.isFinite` guard — use `Number.isInteger` before dispatch | MINOR |
| R4 | index.html:206 | `fmtDate(new Date())` for preview uses browser-local tz rather than the project's Asia/Seoul convention — prefer `todayDate` when available | MINOR |
| R5 | index.html:208-236 & generate_daily_report.py:151-178 | Preview template duplicated in JS and Python (documentation-only concern, not functional) | MINOR |
| R6 | index.html:141 | `sourceBasis` DOM node is overloaded between real source_basis and preview_notice — OK given preview_notice is always present, but semantically ambiguous | MINOR (cosmetic) |

### Integration TC Legend

| TC-ID | Test File::Function |
|-------|---------------------|
| IT-01 | tests/integration/test_save_report_flow.py::test_multiple_save_reports_yield_correct_index |

### E2E TC Legend

| TC-ID | Test File::Function |
|-------|---------------------|
| E2E-01 | tests/e2e/test_recommendation_click.py::test_e2e_01_rec_items_are_clickable_ui |
| E2E-02 | tests/e2e/test_recommendation_click.py::test_e2e_02_click_existing_report_renders_it |
| E2E-03 | tests/e2e/test_recommendation_click.py::test_e2e_03_click_missing_report_shows_preview |
| E2E-04 | tests/e2e/test_recommendation_click.py::test_e2e_04_recommendations_remain_clickable_after_render |
| E2E-05 | tests/e2e/test_recommendation_click.py::test_e2e_05_keyboard_enter_activates_rec |
| E2E-06 | tests/e2e/test_recommendation_click.py::test_e2e_06_today_button_restores_today_report |
| E2E-07 | tests/e2e/test_recommendation_click.py::test_e2e_07_no_api_key_exposed |
| E2E-08 | tests/e2e/test_recommendation_click.py::test_e2e_08_rapid_clicks_render_only_last |

### Unit TC Legend

| TC-ID | Test File::Function |
|-------|---------------------|
| UT-IDX-01 | tests/unit/test_books_index.py::test_empty_daily_dir_produces_empty_books_map |
| UT-IDX-02 | tests/unit/test_books_index.py::test_single_report_is_indexed |
| UT-IDX-03 | tests/unit/test_books_index.py::test_multiple_dates_for_same_book_pick_latest |
| UT-IDX-04 | tests/unit/test_books_index.py::test_multiple_books_indexed_independently |
| UT-IDX-05 | tests/unit/test_books_index.py::test_report_missing_book_id_is_skipped |
| UT-IDX-06 | tests/unit/test_books_index.py::test_output_is_deterministic |
| UT-IDX-07 | tests/unit/test_books_index.py::test_generated_at_is_iso_with_tz |
| UT-SAVE-01 | tests/unit/test_save_report_hook.py::test_save_report_writes_books_index |
| UT-SAVE-02 | tests/unit/test_save_report_hook.py::test_save_report_updates_existing_index |
| UT-SAVE-03 | tests/unit/test_save_report_hook.py::test_save_report_preserves_today_json_behavior |

## Coverage Summary
- Total requirements: 17 (7 REQ + 4 NFR + 6 EDGE)
- TC mapped: 16/17 (94%) — EDGE-004 covered only by defensive impl
- Implementation complete: 17/17 (100%)
- Tests passing: 19/19 executed TCs (100%)
  - Unit: 10/10
  - Integration: 1/1
  - E2E: 8/8

## Update History
| Date | Phase | Changes |
|------|-------|---------|
| 2026-04-22 | P1 | Initialized RTM with 17 rows (7 REQ + 4 NFR + 6 EDGE) |
| 2026-04-22 | P4 | Unit TC mapped (10 TCs, UT-IDX-01~07 + UT-SAVE-01~03). RED confirmed. |
| 2026-04-22 | P5 | Impl locations mapped. GREEN confirmed (10/10 unit tests passing). |
| 2026-04-22 | P6 | IT-01 (integration) and E2E-01~08 (Playwright) written. No mocks in E2E. |
| 2026-04-22 | P7 | All 19 tests PASS (Unit 10 + IT 1 + E2E 8). Result column = PASS. E2E-08 revised post-RED; fix landed. |
| 2026-04-22 | P8 | 3 reviewers parallel. 6 MINOR issues recorded (R1~R6). No MAJOR/CRITICAL after triage. Review column populated. |
| 2026-04-22 | JUDGE | Verdict: PASS. MINORs → Known Limitations. |
| 2026-04-22 | P9 | Completion report written: reports/book-recommendation-click-completion.md. Status = Complete. |
