# daily-market-brief 📈

**"데이터는 넘쳐나지만 정보는 부족한 시대, 읽는 것만으로 전략이 세워지는 리포트 우선(Read-first) 투자 보조 앱"**

이 프로젝트는 매크로 지표, 시장 데이터, 뉴스, 공시, 수급을 자동으로 수집하여 AI(OpenAI/Gemini)가 분석한 **실행 가능한 투자 플레이북**을 생성합니다. 실시간 시세에 휘둘리는 대신, 정제된 리포트를 통해 냉철한 의사결정을 내릴 수 있도록 돕습니다.

---

## 🚀 핵심 특징

### 1. 하이브리드 분석 엔진 (Quant + AI)
- **정량적 필터링**: 수급(외국인/기관), 주요 공시, 기술적 지표(SMA, RSI, MACD 등)를 기반으로 유망 종목 후보군을 1차 선별합니다.
- **정성적 해석**: 선별된 후보군과 거시 맥락을 AI에게 전달하여, 단순 요약이 아닌 '투자 논거(Thesis)'와 '리스크'를 도출합니다.

### 2. 시장 컨텍스트 빌더 (Macro Signals)
- CPI, 고용지표, 장단기 금리차, 달러 인덱스 등을 분석하여 현재 시장을 **Risk-On / Risk-Off / Neutral** 국면으로 자동 분류합니다.
- AI가 분석을 시작하기 전, 현재의 거시적 위치를 정확히 인지하도록 가이드를 제공합니다.

### 3. 구조화된 전술 플레이북 (Tactical Playbook)
- 서술형 리포트와 함께 JSON 구조의 플레이북을 생성합니다.
- **단기/중기 바이어스**, **선호/기피 섹터**, **진입 규칙(Gating Rules)** 등 즉각적인 행동 지침을 제공합니다.

### 4. 리포트 최적화 UX (Frontend)
- **동적 목차 생성**: AI 리포트 본문을 분석하여 실시간 네비게이션 목차를 생성합니다.
- **스마트 링크**: 뉴스 소스 및 종목 정보로의 연결을 자동화합니다.
- **멀티 채널 전송**: 생성된 리포트를 웹앱뿐만 아니라 텔레그램, 이메일로도 받아볼 수 있습니다.

---

## 🛠 기술 스택

- **Backend**: Python 3.12 (Native `http.server` 기반 경량 API)
- **Frontend**: React 19, TypeScript, Vite, TailwindCSS
- **AI**: OpenAI (GPT-4o/o1), Google Gemini
- **Data Sources**: 
  - Macro: FRED (US), ECOS (KR)
  - Market: Yahoo Finance, Naver Finance
  - Disclosure: DART (KR)
  - News: RSS Feeds & Web Scraping
- **Infrastructure**: Docker, Docker Compose, Nginx

---

## 📦 프로젝트 구조

```text
.
├── analyzer/           # AI 분석 및 전략 수립 엔진 (핵심 로직)
│   ├── market_context_builder.py  # 거시 지표 기반 국면 판단
│   ├── openai_analyzer.py         # LLM 기반 리포트/플레이북 생성
│   └── technical_snapshot.py      # 기술적 지표 계산
├── collectors/         # 데이터 수집 모듈 (Macro, News, Flow, etc.)
├── api/                # 경량 API 서버 구현부
├── frontend/           # React 기반 리포트 중심 웹앱
├── scripts/            # 백테스트 및 유틸리티 스크립트
├── main.py             # 전체 리포트 생성 파이프라인
├── scheduler.py        # 자동화 스케줄러
└── api_server.py       # API 서버 실행 진입점
```

---

## ⚙️ 설치 및 실행

### 1. 환경 설정
`.env.example` 파일을 복사하여 `.env`를 생성하고 필요한 API 키를 입력하세요.
- `OPENAI_API_KEY`, `FRED_API_KEY`, `DART_API_KEY`, `ECOS_API_KEY` 필수.

### 2. 로컬 실행
```bash
# 1) 의존성 설치
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2) 리포트 1회 생성 (데이터 수집 및 AI 분석)
python3 run_once.py

# 3) API 및 웹 서버 실행
python3 api_server.py
```

### 3. Docker 실행
```bash
docker compose up --build -d
```
- 접속 주소: `http://localhost:8080`

---

## 📊 주요 기능 상세

### 한국투자증권(KIS) 연동
실제 계좌와 연동하여 잔고 조회 및 주문이 가능합니다 (상세 설정은 `README.md` 원본 참고).

### 가상 백테스트
최근 3년 데이터를 바탕으로 KOSPI100/S&P100 종목에 대한 가상 전략 검증이 가능합니다.
```bash
python scripts/run_kospi_backtest.py
```

---

## ⚠️ 면책 조항 (Disclaimer)
본 서비스에서 제공하는 모든 정보는 투자 참고용이며, 최종 투자 판단의 책임은 사용자 본인에게 있습니다. AI 분석은 오류가 있을 수 있으므로 반드시 원본 데이터를 재확인하시기 바랍니다.
