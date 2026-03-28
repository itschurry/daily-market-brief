import { reasonCodeToKorean, reliabilityToKorean, strategyTypeToKorean } from '../constants/uiText';
import { formatSymbol } from '../utils/format';
import type {
  ActionBoardView,
  ConsoleSnapshot,
  SignalTableRow,
  TodayRecommendationItem,
  TodayRecommendationView,
  TodayReportView,
  WatchDecisionView,
} from '../types/consoleView';

function translateReasons(reasons: string[]): string[] {
  return reasons.map((reason) => reasonCodeToKorean(reason));
}

function dedupeKeepOrder(lines: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const line of lines) {
    const normalized = line.trim();
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    out.push(normalized);
  }
  return out;
}

export function buildSignalRows(snapshot: ConsoleSnapshot): SignalTableRow[] {
  const signals = snapshot.signals.signals || [];
  return signals.map((signal) => {
    const reasons = translateReasons(signal.reason_codes || []);
    return {
      signal,
      symbol: formatSymbol(signal.code, signal.name),
      statusLabel: signal.entry_allowed ? '추천' : '차단',
      reasonSummary: signal.entry_allowed ? '-' : (reasons.join(', ') || '-'),
    };
  });
}

function classifyMode(snapshot: ConsoleSnapshot): WatchDecisionView {
  const riskLevel = String(snapshot.engine.allocator?.risk_level || snapshot.portfolio.risk_level || '');
  const guardAllowed = Boolean(snapshot.engine.risk_guard_state?.entry_allowed);
  const oosReliabilityRaw = String(snapshot.validation.summary?.oos_reliability || '').toLowerCase();
  const oosReliabilityLabel = reliabilityToKorean(oosReliabilityRaw);
  const signals = snapshot.signals.signals || [];
  const allowedCount = signals.filter((item) => item.entry_allowed).length;
  const allowRatio = signals.length > 0 ? allowedCount / signals.length : 0;

  if (!guardAllowed || riskLevel === '높음' || oosReliabilityRaw === 'low') {
    return {
      mode: '관망',
      rationale: [
        `리스크 가드 또는 검증 신뢰도(${oosReliabilityLabel}) 조건이 보수 구간입니다.`,
        '신규 진입보다 기존 포지션 방어와 손실 제한을 우선합니다.',
      ],
    };
  }
  if (riskLevel === '중간' || allowRatio < 0.35) {
    return {
      mode: '선별',
      rationale: [
        '허용 신호 비율이 낮아 상위 EV 신호만 선별 진입합니다.',
        '유동성/리스크 제한 사유가 없는 종목 위주로 좁게 대응합니다.',
      ],
    };
  }
  if (riskLevel === '낮음' && oosReliabilityRaw === 'high' && allowRatio >= 0.6) {
    return {
      mode: '공격',
      rationale: [
        '시장 위험도와 OOS 신뢰도가 양호해 적극 운용 가능한 구간입니다.',
        '단, 일일 손실 한도와 섹터 익스포저 캡은 동일하게 준수합니다.',
      ],
    };
  }
  return {
    mode: '축소',
    rationale: [
      '중립 구간으로 포지션 크기를 보수적으로 조절합니다.',
      '신규 진입은 EV 우위가 뚜렷한 신호에 제한합니다.',
    ],
  };
}

export function buildTodayReportView(snapshot: ConsoleSnapshot): TodayReportView {
  const analysisLines = (snapshot.reports.analysis?.summary_lines || [])
    .map((line) => line.trim())
    .filter(Boolean);
  const summaryFallback = [
    '거시/수급 지표 변화를 기준으로 시장 위험도를 점검합니다.',
    '리스크 가드 상태와 허용 신호 비율을 함께 확인합니다.',
    '신규 진입은 EV와 유동성 조건을 동시에 충족한 종목만 고려합니다.',
  ];
  const summaryLines = dedupeKeepOrder([...analysisLines, ...summaryFallback]).slice(0, 5);

  const guardReasons = translateReasons(snapshot.engine.risk_guard_state?.reasons || []);
  const blockedReasons = translateReasons(
    (snapshot.signals.signals || []).flatMap((signal) => signal.entry_allowed ? [] : (signal.reason_codes || [])),
  );

  const riskFallback = [
    '장초/이벤트 구간에서 체결 슬리피지 확대 가능성에 유의합니다.',
    '연속 손실 구간에서는 신규 진입을 축소하고 관망 비중을 높입니다.',
    '유동성 정보가 부족한 신호는 자동으로 제외될 수 있습니다.',
  ];
  const riskHighlights = dedupeKeepOrder([
    ...guardReasons,
    ...blockedReasons,
    ...riskFallback,
  ]).slice(0, 5);

  const decision = classifyMode(snapshot);
  return {
    generatedAt: snapshot.reports.generated_at || snapshot.fetchedAt,
    summaryLines,
    riskHighlights,
    strategyPoint: decision.mode,
  };
}

function mapToRecommendationItem(
  symbol: string,
  strategy: string,
  expectedValue: number,
  winProbability: number,
  size: number,
  status: '추천' | '차단',
  reasons: string[],
): TodayRecommendationItem {
  return {
    symbol,
    strategy: strategy || '-',
    expectedValue,
    winProbability,
    size,
    status,
    reasonSummary: reasons.length > 0 ? reasons.join(', ') : '-',
  };
}

export function buildTodayRecommendationView(snapshot: ConsoleSnapshot, topN = 15): TodayRecommendationView {
  const signals = [...(snapshot.signals.signals || [])];
  signals.sort((a, b) => (b.ev_metrics?.expected_value || -9999) - (a.ev_metrics?.expected_value || -9999));

  const recommended: TodayRecommendationItem[] = [];
  const excluded: TodayRecommendationItem[] = [];

  for (const signal of signals) {
    const symbol = formatSymbol(signal.code, signal.name);
    const reasons = translateReasons(signal.reason_codes || []);
    const ev = signal.ev_metrics?.expected_value ?? 0;
    const win = signal.ev_metrics?.win_probability ?? 0;
    const size = signal.size_recommendation?.quantity ?? 0;
    const strategy = strategyTypeToKorean(signal.strategy_type || '');

    if (signal.entry_allowed && size > 0) {
      recommended.push(mapToRecommendationItem(symbol, strategy, ev, win, size, '추천', []));
      continue;
    }
    excluded.push(mapToRecommendationItem(symbol, strategy, ev, win, size, '차단', reasons));
  }

  return {
    recommended: recommended.slice(0, topN),
    excluded: excluded.slice(0, 80),
  };
}

export function buildActionBoardView(snapshot: ConsoleSnapshot): ActionBoardView {
  const watch = classifyMode(snapshot);
  const guardAllowed = Boolean(snapshot.engine.risk_guard_state?.entry_allowed);
  const oosReliabilityRaw = String(snapshot.validation.summary?.oos_reliability || '').toLowerCase();
  const oosReliability = reliabilityToKorean(oosReliabilityRaw);
  const entryAllowedCount = Number(snapshot.engine.allocator?.entry_allowed_count || 0);
  const blockedCount = Number(snapshot.engine.allocator?.blocked_count || 0);

  return {
    rules: [
      `오늘 전략 포인트: ${watch.mode}`,
      '손절/손실 한도 규칙을 우선 적용합니다.',
      '차단 사유가 없는 신호만 진입 후보로 사용합니다.',
    ],
    checklist: [
      {
        label: '리스크 가드 상태 확인',
        done: guardAllowed,
        detail: guardAllowed ? '신규 진입 가능 상태입니다.' : '리스크 가드로 신규 진입이 제한됩니다.',
      },
      {
        label: 'OOS 신뢰도 확인',
        done: oosReliabilityRaw !== 'low',
        detail: oosReliability ? `현재 OOS 신뢰도: ${oosReliability}` : 'OOS 신뢰도 데이터가 없습니다.',
      },
      {
        label: '신규 진입 허용 여부 확인',
        done: entryAllowedCount > 0,
        detail: `허용 ${entryAllowedCount}건 / 차단 ${blockedCount}건`,
      },
      {
        label: '차단 사유 점검',
        done: blockedCount === 0,
        detail: blockedCount === 0 ? '차단 신호가 없습니다.' : '차단 사유를 확인하고 진입 제외 대상을 정리하세요.',
      },
    ],
  };
}

export function buildWatchDecisionView(snapshot: ConsoleSnapshot): WatchDecisionView {
  return classifyMode(snapshot);
}
