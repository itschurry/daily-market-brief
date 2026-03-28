export const UI_TEXT = {
  appName: '자동투자 운영 콘솔',
  topTabs: {
    console: '콘솔',
    reports: '리포트',
  },
  consoleTabs: {
    overview: '개요',
    signals: '신호',
    paper: '모의투자',
    validation: '백테스트/검증',
  },
  reportTabs: {
    todayReport: '오늘 리포트',
    todayRecommendations: '오늘의 추천',
    actionBoard: '액션보드',
    watchDecision: '관망/관심목표 판단',
  },
  common: {
    refresh: '새로고침',
    loading: '데이터를 불러오는 중입니다.',
    noData: '표시할 데이터가 없습니다.',
    unknown: '알 수 없음',
    yes: '예',
    no: '아니오',
  },
  errors: {
    loadFailed: '데이터를 불러오지 못했습니다.',
    partialLoadFailed: '일부 데이터를 불러오지 못했습니다.',
    symbolNameMissing: '종목명 매핑 미완성',
  },
  status: {
    running: '실행 중',
    stopped: '중지',
    allowed: '추천',
    blocked: '차단',
    active: '활성',
    inactive: '비활성',
  },
} as const;

export const REASON_CODE_KR: Record<string, string> = {
  allocator_block: '전략 할당 규칙 차단',
  ev_non_positive: '기대값이 0 이하',
  daily_loss_limit_reached: '일일 손실 한도 도달',
  loss_streak_cooldown: '연속 손실 쿨다운',
  regime_risk_off: '리스크 오프 구간',
  risk_level_high: '시장 위험도 높음',
  liquidity_unknown: '유동성 정보 부족',
  liquidity_low_volume: '평균 거래량 부족',
  liquidity_low_notional: '평균 거래대금 부족',
  exposure_or_cash_limit: '현금 또는 익스포저 한도',
  account_unavailable: '계좌 정보 없음',
  size_zero: '권장 수량 0',
  invalid_unit_price: '유효하지 않은 가격',
};

export function reasonCodeToKorean(code: string): string {
  return REASON_CODE_KR[code] || code;
}

const STRATEGY_TYPE_KR: Record<string, string> = {
  breakout: '돌파',
  pullback: '눌림목',
  'event-driven': '이벤트',
  'news-theme momentum': '뉴스/테마 모멘텀',
  'mean-reversion': '평균회귀',
};

const RELIABILITY_KR: Record<string, string> = {
  high: '높음',
  medium: '보통',
  low: '낮음',
  insufficient: '부족',
};

export function strategyTypeToKorean(strategyType: string): string {
  return STRATEGY_TYPE_KR[strategyType] || strategyType || '-';
}

export function reliabilityToKorean(reliability: string): string {
  return RELIABILITY_KR[reliability] || reliability || '-';
}
