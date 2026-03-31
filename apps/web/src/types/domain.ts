export interface EVMetrics {
  expected_value?: number;
  win_probability?: number;
  expected_upside?: number;
  expected_downside?: number;
  expected_holding_days?: number;
  reliability?: string;
}

export interface StrategyScorecardPayload {
  composite_score?: number;
  components?: Record<string, number>;
  tail_risk?: Record<string, number>;
}

export interface ReliabilityGapItem {
  metric?: string;
  current?: number | null;
  required?: number;
  gap?: number | null;
  direction?: string;
  blocking?: boolean;
}

export interface ReliabilityUpliftChange {
  metric?: string;
  from?: number | null;
  to?: number | null;
  delta?: number | null;
}

export interface ReliabilityUpliftPath {
  cost?: number;
  label?: string;
  reason?: string;
  changes?: ReliabilityUpliftChange[];
}

export interface ReliabilityDiagnosticPayload {
  target_label?: string;
  current?: {
    label?: string;
    reason?: string;
    trade_count?: number;
    validation_signals?: number;
    validation_sharpe?: number;
    max_drawdown_pct?: number | null;
    passes_minimum_gate?: boolean;
    is_reliable?: boolean;
  };
  target_reached?: boolean;
  blocking_factors?: ReliabilityGapItem[];
  threshold_gaps?: ReliabilityGapItem[];
  uplift_search?: {
    target_label?: string;
    already_satisfies_target?: boolean;
    searched_candidates?: number;
    feasible?: boolean;
    recommended_path?: ReliabilityUpliftPath | null;
    alternatives?: ReliabilityUpliftPath[];
  };
}

export interface SizeRecommendation {
  quantity?: number;
  reason?: string;
  risk_budget_krw?: number;
}

export interface DomainSignal {
  code?: string;
  name?: string;
  market?: string;
  sector?: string;
  strategy_type?: string;
  score?: number;
  entry_allowed?: boolean;
  reason_codes?: string[];
  ev_metrics?: EVMetrics;
  size_recommendation?: SizeRecommendation;
  strategy_scorecard?: StrategyScorecardPayload;
  validation_snapshot?: {
    composite_score?: number;
    score_components?: Record<string, number>;
    tail_risk?: Record<string, number>;
    strategy_scorecard?: StrategyScorecardPayload;
    validation_trades?: number;
    trade_count?: number;
    validation_sharpe?: number;
    max_drawdown_pct?: number | null;
    strategy_reliability?: string;
  };
  execution_realism?: {
    slippage_model_version?: string;
    liquidity_gate_status?: string;
    slippage_bps?: number;
  };
}

export interface SignalsRankResponse {
  ok?: boolean;
  generated_at?: string;
  regime?: string;
  risk_level?: string;
  count?: number;
  signals?: DomainSignal[];
  risk_guard_state?: {
    entry_allowed?: boolean;
    reasons?: string[];
    daily_loss_left?: number;
    cooldown_until?: string;
  };
}

export interface EngineStatusResponse {
  ok?: boolean;
  mode?: {
    mode?: string;
    report_enabled?: boolean;
    paper_enabled?: boolean;
    live_enabled?: boolean;
  };
  execution?: {
    state?: {
      engine_state?: string;
      running?: boolean;
      started_at?: string;
      paused_at?: string;
      stopped_at?: string;
      last_run_at?: string;
      next_run_at?: string;
      last_success_at?: string;
      last_error?: string;
      last_error_at?: string;
      latest_cycle_id?: string;
      today_order_counts?: {
        buy?: number;
        sell?: number;
        failed?: number;
      };
      today_realized_pnl?: number;
      current_equity?: number;
      validation_policy?: {
        validation_gate_enabled?: boolean;
        validation_min_trades?: number;
        validation_min_sharpe?: number;
        validation_block_on_low_reliability?: boolean;
        validation_require_optimized_reliability?: boolean;
      };
      optimized_params?: {
        version?: string;
        optimized_at?: string;
        is_stale?: boolean;
      };
      last_summary?: Record<string, unknown>;
    };
    account?: {
      equity_krw?: number;
      cash_krw?: number;
      cash_usd?: number;
      positions?: Array<Record<string, unknown>>;
    };
  };
  allocator?: {
    strategy_counts?: Record<string, number>;
    entry_allowed_count?: number;
    blocked_count?: number;
    regime?: string;
    risk_level?: string;
  };
  risk_guard_state?: {
    entry_allowed?: boolean;
    reasons?: string[];
    daily_loss_left?: number;
  };
}

export interface PortfolioStateResponse {
  ok?: boolean;
  account?: {
    equity_krw?: number;
    cash_krw?: number;
    cash_usd?: number;
    positions?: Array<Record<string, unknown>>;
  };
  regime?: string;
  risk_level?: string;
  risk_guard_state?: {
    entry_allowed?: boolean;
    reasons?: string[];
    daily_loss_left?: number;
  };
}

export interface ValidationResponse {
  ok?: boolean;
  metrics?: Record<string, number | string | Record<string, unknown>>;
  scorecard?: StrategyScorecardPayload;
  reliability_diagnostic?: ReliabilityDiagnosticPayload;
  segments?: {
    train?: Record<string, number | string | Record<string, unknown>>;
    validation?: Record<string, number | string | Record<string, unknown>>;
    oos?: Record<string, number | string | Record<string, unknown>>;
  };
  summary?: {
    windows?: number;
    positive_windows?: number;
    oos_reliability?: string;
    composite_score?: number;
    reliability_diagnostic?: ReliabilityDiagnosticPayload;
  };
}

export interface WalkForwardDiagnosisPayload {
  label?: string;
  target_label?: string;
  summary_lines?: string[];
  strengths?: string[];
  blockers?: Array<{
    metric?: string;
    current?: number;
    threshold?: number;
    direction?: string;
    severity?: string;
    summary?: string;
  }>;
  target_adjustments?: Array<{
    metric?: string;
    current?: number;
    target?: number;
    gap?: number;
    direction?: string;
    summary?: string;
  }>;
}

export interface ValidationDiagnosticsResponse {
  ok?: boolean;
  validation?: ValidationResponse;
  diagnosis?: WalkForwardDiagnosisPayload;
  research?: {
    target_label?: string;
    base_label?: string;
    best_label?: string;
    trials_run?: number;
    trial_limit?: number;
    improvement_found?: boolean;
    notes?: string[];
    errors?: string[];
    suggestions?: Array<{
      probe_label?: string;
      rationale?: string;
      label?: string;
      reached_target?: boolean;
      improvement?: number;
      changes?: string[];
      patch?: Record<string, unknown>;
      metrics?: Record<string, number>;
      diagnosis?: WalkForwardDiagnosisPayload;
    }>;
  };
  error?: string;
}

export interface ReportsExplainResponse {
  ok?: boolean;
  generated_at?: string;
  analysis?: {
    summary_lines?: string[];
  };
  signal_reasoning?: Array<{
    code?: string;
    strategy_type?: string;
    entry_allowed?: boolean;
    reason_codes?: string[];
  }>;
}

export interface NotificationStatusResponse {
  ok?: boolean;
  channel?: string;
  enabled?: boolean;
  configured?: boolean;
  chat_id_configured?: boolean;
  last_sent_at?: string;
  last_error?: string;
}
