# 02. 목표 아키텍처

## 최종 구조

```text
Layer A. Universe / Scanner
  - 거래 가능 universe 생성
  - 장전/장중 종목 스캔
  - 스캔 결과 업데이트

Layer B. Quant Strategy Score
  - 전략별 지표 계산
  - 진입/청산 시그널 생성
  - quant_score 산출

Layer C. Hanna Research Score API
  - 뉴스 강도
  - 이벤트 freshness
  - 테마 지속성
  - evidence strength
  - contrarian / hype risk
  - warnings / tags 반환

Layer D. Risk / Execution Gate
  - 일 손실 한도
  - 유동성
  - 스프레드
  - 포지션 수 제한
  - 중복 포지션 방지
  - 시장 상태
  - 최종 거부권

Layer E. Final Action
  - review_for_entry
  - watch_only
  - blocked
  - do_not_touch
```

## 레이어 책임

### Layer A. Universe / Scanner
역할:
- 장 시작 전 전체 universe 구성
- 장중 경량 갱신
- 스캔 대상 종목군 관리

입력:
- 시장 목록
- 거래대금/시총/상장상태/정지상태 등 메타데이터

출력:
- universe snapshot
- scanned symbols
- scanner outputs

---

### Layer B. Quant Strategy Score
역할:
- 승인 전략 기준 quant 점수 계산
- 기술/패턴/모멘텀/변동성 기반 신호 계산
- 스캔 결과에 대한 quant_score 생성

입력:
- universe
- market data
- approved strategies

출력:
- quant_score
- quant signals
- scanner rank

---

### Layer C. Hanna Research Score API
역할:
- 외부 research score 제공
- 엔진 내부 전략이 아님
- 종목별 research score와 warnings, tags 제공

입력:
- symbol
- market
- timestamp
- optional context

출력:
- research_score
- component scores
- warnings
- tags
- ttl_minutes

금지:
- 직접 주문
- 직접 포지션 판단
- buy/sell 명령형 응답

---

### Layer D. Risk / Execution Gate
역할:
- 주문 전 최종 차단 레이어
- 규칙 기반 veto layer
- 주문 가능 여부와 거절 사유 제공

출력:
- allowed / blocked
- reason_codes
- final allowed size
- execution decision

---

### Layer E. Final Action
역할:
- 각 스캔 결과의 최종 상태 산출

권장 상태:
- `review_for_entry`
- `watch_only`
- `blocked`
- `do_not_touch`

## 추천 점수 조합
Layer C는 보조 점수 레이어여야 한다.

권장 방식:
- `research_score`는 단순 가중합보다 rank 보정, 감점, watch_only 유도, warning 기반 제약에 우선 사용한다.
- Layer C는 Layer B를 대체하지 않는다.
- Layer C는 Layer D의 veto 판단을 약화시키지 않는다.

권장 해석 예시:
```text
if "headline_stronger_than_body" in warnings:
    action_bias = "watch_only"

if "already_extended_intraday" in warnings:
    risk_penalty += 0.12

if research_score is high and quant_score is valid:
    review_priority += 1
```

비권장:
- Layer C를 Layer B와 동일 위상의 단순 가중합 점수로 취급하는 것
- research_score 단독으로 `review_for_entry`를 확정하는 것

## 중요한 제약
- Layer C 단독으로 매수 후보 확정 금지
- Layer D가 항상 최종 거부권 보유
- 실시간 경로에서 백테스트/최적화/검증 재호출 금지
