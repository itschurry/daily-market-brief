# Refactoring Result

리팩토링 날짜: 2026-03-21  
기준 커밋: `d201c4a` (fix: 플레이북 프롬프트 포맷 문자열 이스케이프 보완)

---

## 개요

`revision.md`에 정의된 4개 Phase 리팩토링을 전면 적용했습니다.

| Phase | 내용 | 상태 |
|-------|------|------|
| 1 | 데이터 수집 파이프라인 병렬화 | ✅ 완료 |
| 2 | JSON 파일 저장 → SQLite 교체 | ✅ 완료 |
| 3 | `api_server.py` 모듈 분리 | ✅ 완료 |
| 4 | 폴링 스케줄러 → APScheduler 교체 | ✅ 완료 |

---

## Phase 1 — 수집 파이프라인 병렬화

### 변경 파일: `main.py`

**변경 전**  
`collect_market()`, `collect_news()`, `collect_macro()` 등 6개 수집 함수를 순차 호출.

**변경 후**  
`asyncio.gather()` + `ThreadPoolExecutor`로 6개 함수를 동시 실행.

```python
# 변경 전
market_data = collect_market()
news_data = collect_news()
macro_data = collect_macro()
# ... 순차 실행

# 변경 후
loop = asyncio.get_event_loop()
with ThreadPoolExecutor(max_workers=6) as pool:
    results = loop.run_until_complete(asyncio.gather(
        loop.run_in_executor(pool, collect_market),
        loop.run_in_executor(pool, collect_news),
        ...
        return_exceptions=True
    ))
```

- 예외는 `return_exceptions=True`로 처리하여 일부 실패 시 나머지 수집은 계속 진행
- market 실패 시 `None`, 리스트형 데이터 실패 시 `[]` 폴백

---

## Phase 2 — JSON 파일 저장 → SQLite 교체

### 신규 파일: `reporter/storage.py` (75줄)

SQLite WAL 모드 기반 리포트 저장소.

| 함수 | 설명 |
|------|------|
| `save_report(date, key, payload)` | 리포트를 DB에 저장 (UPSERT) |
| `load_report(date, key)` | 특정 날짜·키로 조회 |
| `load_latest_report(key)` | 가장 최근 날짜 기준 조회 |
| `list_report_dates()` | 저장된 날짜 목록 반환 |

- DB 경로: `report/market_brief.db`
- `PRAGMA journal_mode=WAL` — 동시 읽기 안전
- 연결을 호출마다 열고 닫아 Raspberry Pi 메모리 절약

### 변경 파일: `reporter/report_generator.py`

11개 `save_*_cache()` 함수 모두 JSON 파일 쓰기 대신 `storage.save_report()` 호출로 교체.

사용 키 목록: `analysis`, `analysis_playbook`, `recommendations`, `macro`, `calendar`, `disclosures`, `investor_flows`, `ai_signals`, `market_context`, `news`, `today_picks`

### 변경 파일: `api_server.py` (Phase 2 부분)

- `import glob` 제거
- `_resolve_reports_dir()`, `REPORTS_DIR` 제거 → `REPORT_OUTPUT_DIR` (config) 사용
- 캐시 딕트 키 `"mtime"` → `"ts"` (파일 수정시간 기반 → TTL 기반)
- `REPORT_CACHE_TTL = 60` 추가
- 6개 리포트 캐시 함수 전부 `load_report()` / `load_latest_report()` 호출로 교체

### 신규 파일: `scripts/migrate_json_to_sqlite.py` (104줄)

기존 JSON 파일을 SQLite로 일괄 마이그레이션하는 1회성 스크립트.

- 패턴 매칭: `{date}_{key}.json`, `{date}_{key}_cache.json` 모두 처리
- 마이그레이션 완료 파일은 `report/archive/`로 이동
- **실행 완료**: 22개 파일 마이그레이션, `report/market_brief.db` (384KB) 생성

---

## Phase 3 — `api_server.py` 모듈 분리

### 구조 변화

```
# 변경 전
api_server.py  (2,174줄 — 단일 파일)

# 변경 후
api_server.py          (140줄 — HTTP 디스패처만)
api/
├── __init__.py
├── cache.py           (35줄)
├── helpers.py         (98줄)
└── routes/
    ├── __init__.py
    ├── market.py      (294줄)
    ├── reports.py     (380줄)
    ├── watchlist.py   (338줄)
    ├── trading.py     (840줄)
    └── backtest.py    (188줄)
```

### 신규 파일: `api/cache.py` (35줄)

프로세스 전역 상태를 한 곳에 집중 관리.

- TTL 상수: `CACHE_TTL`, `REPORT_CACHE_TTL`, `TECHNICAL_CACHE_TTL`, `INVESTOR_FLOW_CACHE_TTL`
- 캐시 딕트: `_market_cache`, `_analysis_cache`, `_recommendation_cache` 등
- KIS 클라이언트, 모의투자 엔진, 자동매매 스레드 상태

### 신규 파일: `api/helpers.py` (98줄)

순수 유틸리티 함수 모음.

| 함수 | 설명 |
|------|------|
| `_now_iso()` | UTC 기준 ISO 8601 타임스탬프 |
| `_format_krw()` / `_format_usd()` | 통화 포맷 |
| `_strip_html()` | HTML 태그 제거 |
| `_normalize_text()` | 공백 정규화 |
| `_send_paper_trade_notification()` | 텔레그램 체결 알림 |
| `_get_kis_client()` | KIS 클라이언트 싱글톤 (순환 참조 방지 목적으로 여기 배치) |

### 신규 파일: `api/routes/market.py` (294줄)

| 함수 | 설명 |
|------|------|
| `handle_live_market()` | `/api/live-market` — 실시간 지수/환율 |
| `handle_stock_search(query)` | `/api/stock-search` — 종목 검색 |
| `handle_stock_price(code, market)` | `/api/stock/{code}` — 종목 시세 |
| `_resolve_stock_quote()` | KIS 시세 조회 내부 함수 (trading.py에서 import) |
| `_paper_fx_rate()` | 모의투자용 환율 조회 (trading.py에서 import) |

### 신규 파일: `api/routes/reports.py` (380줄)

| 함수 | 설명 |
|------|------|
| `handle_reports()` | `/api/reports` — 날짜 목록 |
| `handle_analysis(date)` | `/api/analysis` |
| `handle_recommendations(date)` | `/api/recommendations` |
| `handle_today_picks(date)` | `/api/today-picks` |
| `handle_compare(base, prev)` | `/api/compare` |
| `handle_macro()` | `/api/macro/latest` |
| `handle_market_context(date)` | `/api/market-context/latest` |
| `handle_market_dashboard()` | `/api/market-dashboard` |

### 신규 파일: `api/routes/watchlist.py` (338줄)

| 함수 | 설명 |
|------|------|
| `handle_watchlist_get()` | `GET /api/watchlist` |
| `handle_watchlist_save(payload)` | `POST /api/watchlist/save` |
| `handle_watchlist_actions(payload)` | `POST /api/watchlist-actions` — 기술적 지표·투자자 동향 포함 |

### 신규 파일: `api/routes/trading.py` (840줄)

모의투자 + 자동매매 엔진 전체.

| 함수 | 설명 |
|------|------|
| `handle_paper_account(refresh_quotes)` | 모의투자 계좌 조회 |
| `handle_paper_order(payload)` | 주문 실행 |
| `handle_paper_reset(payload)` | 초기화 |
| `handle_paper_auto_invest(payload)` | 자동 종목 선정 매수 |
| `handle_paper_engine_start(payload)` | 자동매매 엔진 시작 |
| `handle_paper_engine_stop()` | 자동매매 엔진 중지 |
| `handle_paper_engine_status()` | 자동매매 상태 조회 |

### 신규 파일: `api/routes/backtest.py` (188줄)

| 함수 | 설명 |
|------|------|
| `handle_backtest_run(query)` | `/api/backtest/run` — 파라미터 백테스트 |
| `handle_kospi_backtest()` | `/api/backtest/kospi` — 저장된 백테스트 결과 조회 |

### 변경 파일: `api_server.py` (2,174줄 → 140줄)

Handler 클래스의 `do_GET` / `do_POST`는 라우팅만 수행하고 각 `handle_*` 함수에 위임.  
`_json_resp()`, `_read_json_body()`, `run()`, `log_message()` 인프라 메서드만 보유.

**모듈 간 의존 관계:**
```
api/cache.py          ← 의존 없음 (공유 상태 허브)
api/helpers.py        ← api.cache
api/routes/market.py  ← api.cache, api.helpers
api/routes/reports.py ← api.cache, reporter.storage
api/routes/watchlist.py ← api.cache, api.routes.market, api.routes.reports
api/routes/trading.py ← api.cache, api.helpers, api.routes.market, api.routes.reports, api.routes.watchlist
api/routes/backtest.py ← api.cache, reporter.storage (간접)
api_server.py         ← api.routes.*
```

---

## Phase 4 — APScheduler 교체

### 변경 파일: `scheduler.py` (전면 재작성, 114줄)

**변경 전**  
`while True` + `time.sleep()` 폴링 루프, 장 시간대를 수동으로 계산.

**변경 후**  
`APScheduler BlockingScheduler` + `CronTrigger` 3개 잡으로 교체.

| 잡 이름 | 트리거 | 설명 |
|---------|--------|------|
| `_kr_market_job` | KST 9:00–15:00, 매 :00/:30 | 한국 장중 수집 |
| `_us_market_job` | ET 9:00–15:00, 매 :00/:30 | 미국 장중 수집 |
| `_off_session_job` | KST 6:00–21:00, 매 정시 | 장외 수집 |

- `max_instances=1` — 잡 중복 실행 방지
- `_run()` 함수 보존 — 기존 `main.py` 호출 인터페이스 유지
- `misfire_grace_time=120` — Raspberry Pi 재부팅 후 최대 2분 이내 놓친 잡 실행

### 변경 파일: `requirements.txt`

```
+ APScheduler==3.10.4
```

---

## 파일 변경 요약

| 파일 | 변경 종류 | 주요 내용 |
|------|-----------|-----------|
| `main.py` | 수정 | 순차 수집 → `asyncio.gather` 병렬화 |
| `scheduler.py` | 수정 (전면 재작성) | 폴링 루프 → APScheduler CronTrigger |
| `api_server.py` | 수정 (2174→140줄) | 비즈니스 로직 제거, HTTP 디스패처만 유지 |
| `reporter/report_generator.py` | 수정 | 11개 `save_*_cache()` → `storage.save_report()` |
| `requirements.txt` | 수정 | `APScheduler==3.10.4` 추가 |
| `reporter/storage.py` | 신규 | SQLite WAL 저장소 모듈 |
| `scripts/migrate_json_to_sqlite.py` | 신규 | JSON → SQLite 마이그레이션 스크립트 (실행 완료) |
| `api/__init__.py` | 신규 | 패키지 초기화 |
| `api/cache.py` | 신규 | 전역 캐시/상태 허브 |
| `api/helpers.py` | 신규 | 유틸리티 함수 |
| `api/routes/__init__.py` | 신규 | 패키지 초기화 |
| `api/routes/market.py` | 신규 | 시장 데이터 라우트 |
| `api/routes/reports.py` | 신규 | 리포트 라우트 |
| `api/routes/watchlist.py` | 신규 | 관심종목 라우트 |
| `api/routes/trading.py` | 신규 | 모의투자/자동매매 라우트 |
| `api/routes/backtest.py` | 신규 | 백테스트 라우트 |
| `report/market_brief.db` | 신규 | SQLite DB (22개 레코드, 384KB) |
| `report/archive/` | 신규 | 마이그레이션된 기존 JSON 22개 보관 |
