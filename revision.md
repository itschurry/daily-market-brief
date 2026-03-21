# daily-market-brief 리팩토링 작업 지시서

> GitHub Copilot에게 순서대로 지시할 것. 각 Phase를 완료하고 동작 확인 후 다음 Phase로 넘어갈 것.

-----

## Phase 1 — 파이프라인 병렬화 (`main.py`)

### 목표

`run_daily_report()`의 데이터 수집 6단계를 순차 실행에서 병렬 실행으로 변경한다.

### 지시 내용

`main.py`의 `run_daily_report()` 함수에서 아래 6개 수집 호출을 `asyncio.gather()`로 병렬화해라.

**현재 코드 (순차):**

```python
market = collect_market()
news = collect_news()
macro = collect_macro()
calendar_events = collect_calendar_events()
disclosures = collect_disclosures()
investor_flows = collect_investor_flows()
```

**변경 방향:**

1. 위 6개 함수가 동기 함수(`def`)이므로, `asyncio.get_event_loop().run_in_executor()`를 사용하거나 `functools.partial` + `ThreadPoolExecutor`로 감싸서 병렬 실행한다.
1. 구체적으로는 `asyncio.gather()`에 `loop.run_in_executor(executor, fn)` 형태로 전달한다.
1. 결과는 기존과 동일한 변수명에 언패킹한다.
1. 수집 단계 로그(`[1/10]` ~ `[6/10]`)는 병렬 시작 전에 “수집 병렬 시작” 로그 하나로 대체하고, 완료 후 “수집 완료”를 찍는다.
1. 개별 수집 함수가 예외를 던지면 해당 항목은 빈 리스트/None으로 폴백하고 나머지는 계속 진행한다. `asyncio.gather(return_exceptions=True)`를 활용하고, 결과 타입이 `Exception`이면 경고 로그를 찍고 폴백값을 사용한다.

**폴백 기본값:**

- `collect_market()` 실패 → `None`
- `collect_news()` 실패 → `[]`
- `collect_macro()` 실패 → `[]`
- `collect_calendar_events()` 실패 → `[]`
- `collect_disclosures()` 실패 → `[]`
- `collect_investor_flows()` 실패 → `[]`

**주의:** `DailyData` 생성 이후 코드는 변경하지 않는다.

-----

## Phase 2 — JSON 파일 저장을 SQLite로 교체

### 목표

`report/` 디렉토리에 날짜별로 쌓이는 JSON 파일들을 SQLite DB 단일 파일로 대체한다. 기존 JSON 저장 함수들의 인터페이스는 유지해서 호출부(`main.py`)는 수정하지 않는다.

### 지시 내용

#### 2-1. `reporter/storage.py` 신규 생성

아래 스펙으로 `reporter/storage.py`를 새로 만들어라.

```
- DB 파일 경로: REPORT_OUTPUT_DIR / "market_brief.db" (settings에서 가져옴)
- 테이블 1개: reports
  - id: INTEGER PRIMARY KEY AUTOINCREMENT
  - date: TEXT NOT NULL  (예: "2025-03-20")
  - key: TEXT NOT NULL   (예: "analysis", "macro", "recommendations" 등)
  - data: TEXT NOT NULL  (JSON 문자열)
  - created_at: TEXT NOT NULL (ISO8601 UTC)
  - UNIQUE(date, key)
- 함수 save_report(date: str, key: str, data: Any) -> None
  - data를 json.dumps로 직렬화해서 INSERT OR REPLACE로 저장
  - 파일 잠금: sqlite3의 WAL 모드 활성화 (PRAGMA journal_mode=WAL)
  - 연결은 함수 호출마다 열고 닫는다 (라즈베리파이 메모리 절약)
- 함수 load_report(date: str, key: str) -> Any | None
  - 해당 date+key의 data를 json.loads로 역직렬화해서 반환
  - 없으면 None 반환
- 함수 load_latest_report(key: str) -> Any | None
  - 해당 key에서 가장 최근 date의 data 반환
- 함수 list_report_dates(key: str) -> list[str]
  - 해당 key가 존재하는 date 목록을 내림차순으로 반환
```

#### 2-2. `reporter/report_generator.py` 수정

기존 `save_*_cache()` 함수들을 내부적으로 `storage.save_report()`를 호출하도록 교체한다.

예시:

```python
# 기존
def save_analysis_cache(analysis, date_str, playbook=None):
    path = Path(REPORTS_DIR) / f"{date_str}_analysis.json"
    path.write_text(json.dumps({...}), encoding="utf-8")

# 변경 후
def save_analysis_cache(analysis, date_str, playbook=None):
    from reporter.storage import save_report
    save_report(date_str, "analysis", {"text": analysis, "playbook": playbook})
```

**모든 `save_*_cache()` 함수를 같은 방식으로 교체한다.** key 이름은 기존 파일명의 `{date}_` 이후 `_cache` 이전 부분을 사용한다 (예: `analysis`, `macro`, `recommendations`, `ai_signals`, `calendar`, `disclosures`, `investor_flows`, `market_context`, `news`, `today_picks`).

#### 2-3. `api_server.py`의 파일 읽기 로직 수정

`api_server.py`에서 `glob()`이나 `Path(...).read_text()`로 JSON 파일을 읽는 모든 부분을 `storage.load_report()` 또는 `storage.load_latest_report()`로 교체한다.

예시:

```python
# 기존
def _get_analysis():
    files = sorted(glob(f"{REPORTS_DIR}/*_analysis.json"))
    ...

# 변경 후
def _get_analysis():
    from reporter.storage import load_latest_report
    return load_latest_report("analysis") or {}
```

#### 2-4. 마이그레이션 스크립트 `scripts/migrate_json_to_sqlite.py` 생성

기존에 `report/` 디렉토리에 쌓인 JSON 파일들을 SQLite로 마이그레이션하는 1회성 스크립트를 만든다.

```
- report/ 디렉토리의 모든 *.json 파일을 순회
- 파일명 패턴: {date}_{key}.json 또는 {date}_{key}_cache.json
- date와 key를 파싱해서 storage.save_report() 호출
- 처리 결과를 stdout에 출력
- 이미 DB에 존재하면 스킵 (INSERT OR IGNORE)
```

-----

## Phase 3 — `api_server.py` 라우터별 파일 분리

### 목표

2300줄짜리 `api_server.py`를 기능 단위로 분리한다. HTTP 서버 코어와 라우팅 진입점은 `api_server.py`에 유지하고, 실제 핸들러 로직을 `api/` 패키지로 분리한다.

### 지시 내용

#### 3-1. 디렉토리 구조 생성

```
api/
├── __init__.py
├── routes/
│   ├── __init__.py
│   ├── market.py        # /api/live-market, /api/stock-search, /api/stock/{code}
│   ├── reports.py       # /api/analysis, /api/recommendations, /api/macro/latest,
│   │                    # /api/market-context/latest, /api/today-picks
│   ├── watchlist.py     # /api/watchlist (GET/POST/DELETE)
│   ├── trading.py       # /api/paper-*, /api/auto-invest, /api/auto-trader
│   └── backtest.py      # /api/backtest
└── helpers.py           # _format_krw, _format_usd, _now_iso 등 공용 유틸
```

#### 3-2. 분리 규칙

각 `routes/*.py`에 다음 형태로 핸들러 함수를 이동한다:

```python
# api/routes/market.py 예시
def handle_live_market(query_params: dict) -> tuple[int, dict]:
    """
    returns (http_status_code, response_dict)
    """
    ...
```

- 모든 핸들러는 `(status_code: int, body: dict)` 튜플을 반환한다.
- HTTP 파싱/직렬화는 `api_server.py`의 `do_GET`/`do_POST`에서만 처리한다.
- 전역 캐시 변수(`_market_cache`, `_analysis_cache` 등)는 `api/cache.py`로 분리한다.
- `api_server.py`의 `do_GET`은 path prefix를 보고 적절한 `routes/*.py` 함수를 호출하는 디스패처 역할만 한다.

#### 3-3. `api_server.py` 최종 형태

분리 후 `api_server.py`는 다음만 담당한다:

```
- PORT, 서버 시작 로직
- BaseHTTPRequestHandler 서브클래스 (do_GET, do_POST)
- path 파싱 후 적절한 routes 함수 호출
- JSON 직렬화 및 응답 전송
- 전역 초기화 (KIS 클라이언트, paper engine 등)
```

목표 라인 수: **400줄 이하**

-----

## Phase 4 — 스케줄러 APScheduler 교체

### 목표

`scheduler.py`의 `while True + time.sleep(30)` 폴링 방식을 `APScheduler`로 교체한다.

### 지시 내용

#### 4-1. 의존성 추가

`requirements.txt`에 추가:

```
APScheduler==3.10.4
```

#### 4-2. `scheduler.py` 전면 재작성

아래 스펙으로 `scheduler.py`를 재작성한다.

```python
"""
APScheduler 기반 스케줄러.
- 한국장 정규장: KST 09:00-15:30, 30분 단위 cron
- 미국장 정규장: ET 09:30-16:00, 30분 단위 cron  
- 장외: KST 06:00-21:00, 매 정시 cron
"""
```

**구현 조건:**

1. `BlockingScheduler` 사용 (백그라운드 실행 불필요, systemd가 관리)
1. 한국장 슬롯: `CronTrigger(hour='9-15', minute='0,30', timezone='Asia/Seoul')`
- 단, 15:30 이후는 제외 → `hour='9-14'`는 `minute='0,30'`, `hour='15'`는 `minute='0,30'`으로 분리하되 15:30까지만 → `hour=15, minute=0,30` 그대로 두고 핸들러 내에서 15:30 초과 시 스킵
1. 미국장 슬롯: ET 기준 `CronTrigger(hour='9-15', minute='0,30', timezone='America/New_York')`
- 동일하게 16:00 이후는 핸들러에서 스킵
1. 장외 슬롯: `CronTrigger(hour='6-21', minute=0, timezone='Asia/Seoul')`
1. 각 슬롯 실행 전 `config.market_calendar.is_market_half_hour_slot()` 검사는 유지한다 (공휴일 필터)
1. 실행 함수는 기존 `_run()`을 그대로 재사용한다 (`asyncio.run(run_daily_report())`)
1. 중복 실행 방지: `max_instances=1` 옵션 사용
1. 실행 시작/완료/실패 로그는 기존과 동일하게 유지

**스케줄러 시작 코드:**

```python
if __name__ == "__main__":
    scheduler = BlockingScheduler()
    # ... add_job 호출들 ...
    logger.info("APScheduler 시작")
    _log_schedule_policy()
    scheduler.start()
```

-----

## 공통 주의사항

- **각 Phase 완료 후 `python3 run_once.py`로 동작 확인할 것**
- Phase 2 완료 후에는 반드시 `python3 scripts/migrate_json_to_sqlite.py` 실행
- 기존 `report/*.json` 파일은 마이그레이션 후 삭제하지 말고 `report/archive/`로 이동
- `requirements.txt` 변경 시 라즈베리파이에서 `pip install -r requirements.txt` 재실행 필요
- 각 Phase는 독립적으로 동작해야 함 — Phase 3을 건너뛰어도 Phase 4가 동작해야 함

-----

## 변경 후 예상 효과

|항목                  |변경 전         |변경 후         |
|--------------------|-------------|-------------|
|수집 파이프라인 소요 시간      |~60초 (순차)    |~15초 (병렬)    |
|저장 안정성              |JSON 동시 쓰기 위험|SQLite WAL 모드|
|`api_server.py` 라인 수|2300줄        |~400줄        |
|스케줄러 CPU 사용         |30초마다 폴링     |이벤트 기반 대기    |
