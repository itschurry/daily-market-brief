# 05. UI 작업 지시서

## 목표
사용자가 각 스캔 결과가 왜 review 대상인지, 왜 차단됐는지,
Hanna가 어떤 경고를 붙였는지 한눈에 볼 수 있어야 한다.

UI는 Layer A~E 구조를 드러내야 한다.

---

## P0. 후보 상세 화면에 Layer A~E 표시
### 표시 항목
- Layer A: universe_rule, scan_time, inclusion reason
- Layer B: quant_score, strategy_id, quant tags
- Layer C: research_score, warnings, tags, summary
- Layer D: risk result, reason codes, position cap / liquidity / spread 상태
- Layer E: final_action

### 완료 기준
- 사용자가 종목 하나를 눌렀을 때 레이어별 판단 근거를 볼 수 있다
- Layer C summary는 설명용으로만 보이고, 최종 거부권은 Layer D로 읽히게 표시된다

---

## P0. 실시간 스캐너 화면
### 표시 항목
- 현재 스캔 중인 종목 수
- 스캔 결과 Top N
- quant_score
- research_score
- final_action
- research unavailable 여부

### 완료 기준
- 장중에 “왜 이 종목이 올라왔는지” 바로 파악 가능
- `review_for_entry` / `watch_only` / `blocked` / `do_not_touch` 상태를 혼동 없이 읽을 수 있다

---

## P0. Risk / Action 로그 화면
### 표시 항목
- symbol
- strategy_id
- risk allowed / blocked
- reason codes
- final action
- created_at

### 완료 기준
- “왜 안 샀지?”를 로그 화면에서 바로 알 수 있다
- Layer D 차단과 Layer E 상태가 섞여 보이지 않는다

---

## P1. Hanna 상태 배지
### 표시 항목
- healthy
- degraded
- timeout
- research_unavailable

### 완료 기준
- Hanna API 이상 여부를 운영자가 바로 감지 가능
- timeout 시에도 live 경로가 계속 동작 중인지 함께 읽을 수 있다

---

## P1. 레거시 비퀀트 UI 제거
### 해야 할 일
- 과거 추천 엔진/뉴스 엔진 탭 제거
- direct recommendation 화면 제거
- legacy 캐시/리포트 링크 제거

### 완료 기준
- UI에 옛 비퀀트 엔진 잔재가 남아 있지 않다
- 사용자가 legacy 추천과 Layer C research score를 혼동하지 않는다
