# 04. Hanna Research Score API 명세

## 목적
Hanna는 WealthPulse의 내부 비퀀트 엔진이 아니라,
외부 research scorer API로 동작한다.

이 API는 주문 명령을 내리지 않고,
research score / warnings / tags / component score를 제공한다.

---

## Endpoint 예시
```text
POST /api/research/score
```

## Request 예시
```json
{
  "symbol": "005930",
  "market": "KR",
  "timestamp": "2026-04-02T10:30:00+09:00",
  "context": {
    "strategy_id": "kr_momentum_v1",
    "last_price": 71200,
    "change_pct": 2.8,
    "volume_ratio": 1.9,
    "quant_score": 0.74,
    "market_regime": "risk_on",
    "scanner_reasons": ["volume_expansion", "breakout_setup"],
    "universe_tags": ["large_cap", "semiconductor"],
    "risk_flags": ["none"]
  }
}
```

## Response 예시
```json
{
  "symbol": "005930",
  "market": "KR",
  "research_score": 0.61,
  "components": {
    "freshness_score": 0.80,
    "evidence_strength": 0.67,
    "theme_persistence_score": 0.55,
    "contrarian_risk_score": 0.22,
    "hype_risk_score": 0.41
  },
  "warnings": [
    "headline_stronger_than_body",
    "already_extended_intraday"
  ],
  "tags": [
    "earnings",
    "semiconductor",
    "ai_memory"
  ],
  "summary": "실적/업황 관련 이슈는 유효하지만 장중 과열 흔적이 있어 추격 주의",
  "ttl_minutes": 120,
  "generated_at": "2026-04-02T10:30:05+09:00"
}
```

## 필수 규칙
- `research_score` 범위는 0.0 ~ 1.0
- `components`는 숫자형 점수만 허용
- `warnings`는 사전 정의된 code만 허용
- `summary`는 UI 표시용 텍스트일 뿐, 엔진 의사결정의 핵심 입력이 되어서는 안 된다
- `ttl_minutes`를 이용해 캐시 가능해야 한다
- warning code는 taxonomy 문서에 등록된 stable code만 사용해야 한다
- warning code는 UI 라벨과 1:1 매핑 가능해야 한다
- free-form warning 문자열 추가는 금지한다

## 금지 응답 형태
```json
{
  "symbol": "005930",
  "action": "BUY_NOW",
  "confidence": 0.95
}
```

이런 명령형 응답은 금지한다.

## 권장 warning code
- `headline_stronger_than_body`
- `already_extended_intraday`
- `low_evidence_density`
- `theme_recycled`
- `contrarian_flow_risk`
- `policy_uncertainty`
- `liquidity_mismatch`
- `too_many_similar_news`

## 권장 해석 규칙
- `research_score`는 보조 점수
- `warnings`는 감점 또는 watch_only 유도
- `contrarian_risk_score`, `hype_risk_score`는 높을수록 불리하게 해석 가능

## Timeout / Retry
- client timeout: 1~2초 권장
- retry: 1회 이하 권장
- timeout 시 주문 경로를 멈추지 않는다
- timeout 시 기본 fallback은 `research_unavailable` warning을 남기고 quant + risk 기준으로 계속 진행한다
- timeout 자체를 action 결정 근거로 과대해석하지 않는다

## 캐시 정책
- `symbol + market + rounded timestamp bucket` 기준 단기 캐시 가능
- `ttl_minutes` 경과 시 재평가
