import type {
  DomainSignal,
  EngineStatusResponse,
  PortfolioStateResponse,
  ReportsExplainResponse,
  SignalsRankResponse,
  ValidationResponse,
} from './domain';

export interface ConsoleSnapshot {
  engine: EngineStatusResponse;
  signals: SignalsRankResponse;
  portfolio: PortfolioStateResponse;
  validation: ValidationResponse;
  reports: ReportsExplainResponse;
  fetchedAt: string;
}

export interface ConsoleDataState {
  snapshot: ConsoleSnapshot;
  loading: boolean;
  hasError: boolean;
  errorMessage: string;
}

export interface TodayReportView {
  generatedAt: string;
  summaryLines: string[];
  riskHighlights: string[];
  strategyPoint: '관망' | '선별' | '공격' | '축소';
}

export interface TodayRecommendationItem {
  symbol: string;
  strategy: string;
  expectedValue: number;
  winProbability: number;
  size: number;
  status: '추천' | '차단';
  reasonSummary: string;
}

export interface TodayRecommendationView {
  recommended: TodayRecommendationItem[];
  excluded: TodayRecommendationItem[];
}

export interface ActionBoardView {
  rules: string[];
  checklist: Array<{ label: string; done: boolean; detail: string }>;
}

export interface WatchDecisionView {
  mode: '관망' | '선별' | '공격' | '축소';
  rationale: string[];
}

export interface SignalTableRow {
  signal: DomainSignal;
  symbol: string;
  statusLabel: '추천' | '차단';
  reasonSummary: string;
}
