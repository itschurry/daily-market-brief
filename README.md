# daily-market-brief

일일 시장 브리프, 추천 종목, 설명 리포트, 모의투자 엔진을 함께 운영하는 투자 리서치/운영 앱입니다.

## 주요 기능

- 매크로/시장 컨텍스트 기반 일일 브리프 생성
- 추천 종목 / 오늘의 픽 조회
- 전일 대비 리포트 비교
- 설명 가능한 리포트 API 제공
- KOSPI / NASDAQ 대상 모의투자 엔진 운용
- 웹 콘솔 기반 운영 상태 확인
- 텔레그램 알림 연동

## 저장소 구조

```text
.
├── apps/
│   ├── api/        # FastAPI backend, report pipeline, scheduler, paper trading
│   └── web/        # React/Vite console UI
├── docs/           # 운영 문서, 사용 매뉴얼
├── storage/
│   ├── reports/    # 리포트 결과물, SQLite 캐시
│   └── logs/       # 엔진 상태/주문/계좌/사이클 로그
├── docker-compose.yml
└── requirements.txt
```

## 빠른 시작

### 로컬 개발

```bash
cd /home/user/daily-market-brief

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp apps/api/.env.example apps/api/.env
cd apps/web && npm install && cd ../..

cd apps/api && python3 api_server.py
# 새 터미널
cd /home/user/daily-market-brief/apps/web && npm run dev
```

### Docker 실행

```bash
cd /home/user/daily-market-brief
cp apps/api/.env.example apps/api/.env
# .env 수정

docker compose up -d --build
```

## 기본 접속 주소

- API: `http://127.0.0.1:8001`
- Web Dev: `http://127.0.0.1:5173`
- Web Prod: `http://127.0.0.1:8081`
- Health: `http://127.0.0.1:8001/health`

## 자주 쓰는 명령

### 원샷 리포트 생성

```bash
cd apps/api
python3 run_once.py
```

### 스케줄러 실행

```bash
cd apps/api
python3 scheduler.py
```

### 모의투자 엔진 상태 조회

```bash
curl http://127.0.0.1:8001/api/paper/engine/status
```

### 모의투자 엔진 시작

```bash
curl -X POST http://127.0.0.1:8001/api/paper/engine/start \
  -H "Content-Type: application/json" \
  -d '{"markets":["KOSPI","NASDAQ"],"interval_seconds":300}'
```

## 문서

- 상세 사용 매뉴얼: [`docs/usage.md`](docs/usage.md)
- 사용 매뉴얼 내 포함: 기능 소개 / 스크린샷 플레이스홀더 / 아키텍처 다이어그램
- 최근 신뢰도 기준선 문서: [`docs/quant-reliability-baseline-2026-03-31.md`](docs/quant-reliability-baseline-2026-03-31.md)

## 환경 변수 핵심

백엔드 `.env` 예시:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Ollama 사용 시:

```bash
LLM_PROVIDER=ollama
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=nemotron-3-super
```

정확한 설정 항목과 운영 절차는 `docs/usage.md` 참고.

## 테스트 / 빌드

### 백엔드 테스트

```bash
cd apps/api
python -m unittest discover -s tests
```

### 프런트엔드 빌드

```bash
cd apps/web
npm run build
```

### Docker 빌드

```bash
docker compose up -d --build
```

## 라이선스

`LICENSE` 참고.
