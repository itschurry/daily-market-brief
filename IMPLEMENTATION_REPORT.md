# 모의 투자 전략 강화 - 구현 완료 보고서

## 📋 프로젝트 개요
현재 모의 투자 전략의 문제점:
- 거래 빈도가 낮음 (매수/매도 조건이 너무 타이트)
- 매수 후 즉시 청산 (매도 조건이 너무 민감)

## 🎯 해결 방안 - 5개 Phase 구현

### Phase 1: 기본 전략 파라미터 완화 ✅
**파일**: `analyzer/shared_strategy.py`

#### KOSPI 변경
- max_holding_days: 15 → **25일**
- RSI 범위: (45-62) → **(38-72)** — 진입 기회 확대
- volume_ratio_min: 1.0 → **0.8** — 거래량 필터 완화
- stop_loss_pct: 5% → **7%** — 손절 폭 확대
- take_profit_pct: None → **15%** — 익절 목표 활성화

#### NASDAQ 변경
- max_holding_days: 30 → **40일**
- RSI 범위: (45-68) → **(38-75)**
- volume_ratio_min: 1.2 → **1.0**
- stop_loss_pct: None → **8%**
- take_profit_pct: None → **20%**

#### 청산 조건 개선
- RSI 과열: 75 → **82** (강세 모멘텀 보호)
- SMA20 이탈: `close < sma20` → **`close < sma20 * 0.99`** (1% 버퍼)
- MACD 약세: 무조건 청산 → **손실 상태(`pnl < -2%`)에서만 청산**
- MACD 진입: AND → **OR** (조건 완화)

---

### Phase 2: 5개 신규 기술 지표 추가 ✅
**파일**: `analyzer/technical_snapshot.py`

#### 신규 지표 함수

| 지표 | 함수명 | 용도 |
|------|--------|------|
| **ADX(14)** | `_adx()` | 추세 강도 측정 (0-100) |
| **Bollinger Bands(20,2σ)** | `_bollinger_bands()` | 변동성 지지/저항 |
| **OBV** | `_obv()` | 거래량 추세("up"/"down"/"flat") |
| **MFI(14)** | `_mfi()` | 거래량 가중 모멘텀 (0-100) |
| **Stochastic(14)** | `_stochastic()` | 과매수/과매도 (%K, %D) |

#### 스냅샷 반환값 확장
```python
{
    ...기존 지표들...
    "adx14": float,           # ADX(14)
    "bb_upper": float,         # 볼린저 상단
    "bb_lower": float,         # 볼린저 하단
    "bb_pct": float,           # %B (0-1)
    "obv_trend": str,          # up/flat/down
    "mfi14": float,            # MFI(14)
    "stoch_k": float,          # Stochastic K
    "stoch_d": float,          # Stochastic D
}
```

---

### Phase 3: 새 지표 평가 로직 통합 ✅
**파일**: `analyzer/technical_snapshot.py`, `analyzer/shared_strategy.py`

#### `evaluate_technical_snapshot()` 확장
새 지표별 점수 조정:
- ADX ≥ 25: +1.5점 (강추세)
- ADX < 15: -2.0점 (횡보)
- BB %B < 0.2: +1.5점 (과매도)
- OBV "up": +1.0점
- MFI < 25: +1.0점 (과매도)
- Stochastic < 25: +1.0점

#### `entry_score_from_snapshot()` 강화
기존 진입 점수 + 새 지표 점수 합산
- 최대 추가 가능 스코어: +6.5점

---

### Phase 4: 추천 엔진 강화 ✅
**파일**: `analyzer/recommendation_engine.py`, `analyzer/today_picks_engine.py`, `analyzer/openai_signal_engine.py`

#### 점수 산식 조정
- 뉴스 가중치: `min(hits, 6) × 2.5` → **`min(hits, 8) × 3.0`**
- 공시 가중치: `min(count, 2) × 4.0` → **`min(count, 3) × 5.0`**

#### Gate Penalty 완화
- caution: -6 → **-4**
- blocked: -18 → **-12**

#### 추천 신호 임계값 (`_signal()`)
- "추천": score ≥ 66 → **score ≥ 62**
- "중립": score ≥ 52 → **score ≥ 48**

#### 오늘의 추천 임계값 (`_signal_from_score()`)
- "추천": score ≥ 72 → **score ≥ 68**
- "중립": score ≥ 56 → **score ≥ 52**

#### AI 신호 범위 확대
- `score_adjustment`: `[-4.0, 4.0]` → **`[-5.0, 5.0]`**

---

### Phase 5: 몬테카를로 파라미터 그리드 확장 ✅
**파일**: `analyzer/monte_carlo.py`

#### ParamGrid 탐색 범위

| 파라미터 | 기존 | 신규 |
|---------|------|------|
| stop_loss_pct | [3,5,7,10,13] | **[5,7,10,13,15]** |
| take_profit_pct | [6,10,15,20,25] | **[10,15,20,25,30]** |
| max_holding_days | [5,10,15,20,30] | **[15,20,25,30,40]** |
| rsi_min | [30,40,50] | **[30,38,45]** |
| rsi_max | [60,70,80] | **[65,72,80]** |
| volume_ratio_min | [0.8,1.2,2.0] | **[0.6,0.8,1.0,1.2]** |

#### 신뢰도 기준 강화
- `is_reliable`: `validation_sharpe > 0` → **`validation_sharpe > 0.1`**

---

## 📊 기대 효과

| 목표 | 구현 방법 | 기대 결과 |
|------|----------|----------|
| **거래 빈도↑** | RSI 범위 확대(38-72), volume 완화(0.8), MACD OR | 진입 기회 **2배↑** |
| **보유기간↑** | max_holding(25-40일), 청산 조건 완화 | 조기 청산 **방지** |
| **수익률↑** | take_profit 활성화, 새 지표 점수 | 샤프 지수 **향상** |

---

## 🚀 다음 단계

### 1. 백테스트 실행
```bash
POST /api/backtest/run
# 쿼리 파라미터: initial_cash, max_positions, max_holding_days, 
#               rsi_min, rsi_max, volume_ratio_min, etc.
```

**확인 항목**:
- 승률 (Win Rate)
- 샤프 지수 (Sharpe Ratio)
- 최대낙폭 (Max Drawdown)
- 평균 보유일수

### 2. 몬테카를로 최적화 실행
```bash
POST /api/run-optimization
```

**결과**:
- 최적 파라미터 도출
- 신뢰 종목 선별
- 종목별 맞춤 파라미터

### 3. 자동 매매 시작
```bash
POST /api/paper-trading/auto-invest
```

**모니터링**:
- 실제 신호 생성 빈도
- 포지션 진입/청산 이유
- PnL 추이

---

## ✅ 검증 결과

- **코드 컴파일**: 6개 파일 모두 성공
- **문법 검사**: 오류 없음
- **주요 변경사항**: grep 확인 완료

### 변경된 파일 목록
1. `analyzer/shared_strategy.py` — 파라미터, 청산 조건
2. `analyzer/technical_snapshot.py` — 신규 지표 5개
3. `analyzer/recommendation_engine.py` — 추천 점수
4. `analyzer/today_picks_engine.py` — 임계값
5. `analyzer/openai_signal_engine.py` — AI 신호 범위
6. `analyzer/monte_carlo.py` — 파라미터 그리드

---

## 💡 추가 유의사항

1. **과적합 방지**: 몬테카를로를 주기적으로 재실행
2. **시장 환경**: 환경 변화 시 파라미터 재조정
3. **백테스트 검증**: 실거래 전 충분한 검증 필수
4. **리스크 관리**: 손절/익절 설정은 보수적으로

---

구현이 모두 완료되었습니다. API를 통해 백테스트로 성과를 확인하세요!
