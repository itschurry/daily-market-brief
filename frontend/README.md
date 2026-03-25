# Frontend (daily-market-brief UI) 🖥️

daily-market-brief의 사용자 인터페이스는 **"집중력 있는 읽기"**와 **"빠른 전략 수립"**을 목표로 설계되었습니다.

---

## ✨ 핵심 사용자 경험 (UX)

### 1. 리포트 본문 동적 네비게이션
AI가 생성한 긴 리포트를 효과적으로 읽을 수 있도록 브라우저 단에서 마크다운/HTML을 파싱하여 다음 기능을 수행합니다:
- **실시간 목차(Outline) 추출**: H2, H3 태그를 바탕으로 좌측 사이드바에 즉각적인 이동 링크 생성.
- **예상 읽기 시간 계산**: 본문 텍스트량을 기반으로 오늘 리포트를 다 읽는 데 필요한 시간 표시.
- **스마트 링크(Linkification)**: 텍스트 내 URL을 자동 감지하여 클릭 가능한 링크로 변환.

### 2. 전략 플레이북 사이드바 (Playbook Integration)
리포트 본문을 읽기 전, 핵심 전술을 한눈에 파악할 수 있는 사이드바를 제공합니다:
- 시장 국면 (Risk-On/Off)
- 단기/중기 매매 편향 (Bias)
- 우선 선별 섹터 및 리스크 요인

### 3. 실시간 시장 보조 지표 (Live Context)
리포트가 정적인 분석이라면, 실시간 탭은 현재 시장 상황을 보조적으로 확인하는 용도입니다:
- 거시 지표 시각화 카드
- 수급 현황 (외국인/기관 순매수 상위)
- 종목 검색 및 AI 보조 신호 조회

---

## 🛠 Tech Stack

- **Framework**: React 19 (Latest)
- **Language**: TypeScript (Strict typing)
- **Build Tool**: Vite 8.0
- **Styling**: TailwindCSS & Native CSS Variables (Consistent UI theme)
- **Icons**: Lucide Icons & Custom SVG Assets

---

## 📂 주요 디렉토리 안내

- `src/components/AnalysisTab.tsx`: AI 리포트 본문 파싱 및 렌더링 핵심 컴포넌트.
- `src/hooks/useAnalysis.ts`: 분석 데이터를 가져오고 캐싱하는 커스텀 훅.
- `src/utils/linkify.tsx`: 텍스트 내 링크 및 종목 태그 처리 유틸리티.
- `src/types/index.ts`: 전역 타입 정의 (AnalysisData, Playbook, etc.)

---

## ⚙️ 실행 방법

백엔드 API 서버(`api_server.py`)가 먼저 실행 중이어야 합니다.

### 개발 환경 실행
```bash
cd frontend
npm install
npm run dev
```
- 기본 주소: `http://localhost:5173`

### 프로덕션 빌드
```bash
npm run build
npm run preview
```

---

## 🔗 관련 문서
- [루트 README.md](../README.md)
- [API 명세 안내](../api_server.py)
