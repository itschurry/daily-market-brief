# 03. 백엔드 작업 지시서

## P0. 기존 비퀀트 엔진 전수 제거
### 해야 할 일
- 추천형 엔진, 뉴스 기반 직접 매수 엔진, 테마 직접 매수 엔진 등 기존 비퀀트 엔진 전부 제거
- 주문 경로에 남아 있는 비퀀트 분기 제거
- legacy 추천 결과 캐시/테이블/API가 주문 경로에 연결돼 있으면 제거 또는 비활성화

### 완료 기준
- 엔진 내부에 비퀀트 추천 전략이 남아 있지 않다
- 주문 경로는 market data + quant score + hanna api result + risk gate + execution 판단만 사용한다

---

## P0. Layer A~E 파이프라인 생성
### 해야 할 일
- 레이어별 서비스/모듈 분리
- 각 레이어 책임을 코드 구조에서 분리
- 레이어 간 입출력 DTO 명확화

### 권장 디렉토리 예시
```text
app/
  live/
    layer_a_universe/
    layer_b_quant/
    layer_c_research/
    layer_d_risk_execution/
    layer_e_action/
  strategy/
  portfolio/
  jobs/
  api/
```

### 완료 기준
- Layer A~E가 코드 구조 상 분리되어 있다
- 한 레이어가 다른 레이어 책임을 침범하지 않는다

---

## P0. ResearchScorer 인터페이스 도입
### 해야 할 일
- 외부 research score 제공자용 인터페이스 추가
- 기본 구현체:
  - `NullResearchScorer`
  - `HannaResearchScorer`

### 예시
```python
class ResearchScorer(Protocol):
    async def score(self, request: ResearchScoreRequest) -> ResearchScoreResult: ...
```

### 완료 기준
- 엔진은 구현체가 아니라 인터페이스에 의존한다
- Hanna 제거/교체가 가능하다
- ResearchScorer 부재 시에도 live 경로가 깨지지 않는다

---

## P0. Hanna API 어댑터 구현
### 해야 할 일
- HTTP client 또는 connector adapter 추가
- timeout, retry, ttl 처리
- invalid response 방어 로직 추가
- score/result schema 검증

### 완료 기준
- Layer C는 Hanna API 응답을 구조화된 DTO로만 반환한다
- free-form text 파싱으로 엔진이 동작하지 않는다
- timeout 또는 장애 시 `research_unavailable` 상태를 구조적으로 남긴다

---

## P0. Final Action 결정 서비스 구현
### 해야 할 일
- Layer A~D 결과를 받아 Layer E action 산출
- 최소 상태:
  - `review_for_entry`
  - `watch_only`
  - `blocked`
  - `do_not_touch`

### 예시 규칙
- risk blocked => blocked
- quant 약함 + research 약함 => do_not_touch
- quant 강함 + research 중간 + risk pass => review_for_entry
- quant 강함 + research 경고 다수 + risk pass => watch_only

### 완료 기준
- 엔진이 “최종 상태 snapshot”을 명시적으로 기록/표시한다
- snapshot에는 timestamp와 source context가 포함된다

---

## P1. 점수 조합 정책 분리
### 해야 할 일
- final decision 정책을 하드코딩하지 말고 정책 객체/설정으로 분리
- research weight 조정 가능
- strategy별 hanna 사용 여부 설정 가능
- research_score는 단순 합산보다 rank 보정, 감점, watch_only 유도, warning 기반 제약에 우선 사용

### 완료 기준
- 특정 전략에는 Hanna를 끌 수 있다
- watch-only mode로도 운용 가능하다
- research_score 단독으로 `review_for_entry`가 확정되지 않는다

---

## P1. Layer별 이벤트 로그 도입
### 기록 항목
- Layer A universe snapshot id
- Layer B quant score
- Layer C research score / warnings
- Layer D risk result / reason codes
- Layer E final action

### 완료 기준
- 종목별로 어느 레이어에서 탈락했는지 추적 가능하다
- final action이 어느 입력 기준에서 계산됐는지 복원 가능하다

---

## P1. 실패 대비 fallback
### 해야 할 일
- Hanna API timeout 또는 오류 시 fallback 규칙 정의
- 권장 기본 동작:
  - research unavailable 상태로 mark
  - quant-only continue
  - risk / execution은 정상 진행

### 완료 기준
- Hanna 장애가 전체 엔진 장애로 번지지 않는다
- fallback 동작이 구현체마다 달라지지 않고 일관된다
