import { reliabilityToKorean, UI_TEXT } from '../constants/uiText';
import { formatNumber, formatPercent } from '../utils/format';
import type { ConsoleSnapshot } from '../types/consoleView';

interface BacktestValidationPageProps {
  snapshot: ConsoleSnapshot;
  loading: boolean;
  errorMessage: string;
  onRefresh: () => void;
}

function metricValue(metrics: Record<string, number> | undefined, key: string): number | undefined {
  if (!metrics) return undefined;
  const value = metrics[key];
  return Number.isFinite(value) ? value : undefined;
}

export function BacktestValidationPage({ snapshot, loading, errorMessage, onRefresh }: BacktestValidationPageProps) {
  const oos = snapshot.validation.segments?.oos as Record<string, number> | undefined;
  const train = snapshot.validation.segments?.train as Record<string, number> | undefined;
  const validation = snapshot.validation.segments?.validation as Record<string, number> | undefined;

  return (
    <div className="app-shell">
      <div className="page-frame">
        <div className="content-shell" style={{ display: 'grid', gap: 16 }}>
          <div className="page-section" style={{ padding: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800 }}>백테스트/검증</div>
              <div style={{ fontSize: 12, color: 'var(--text-4)', marginTop: 6 }}>
                OOS 신뢰도 {reliabilityToKorean(String(snapshot.validation.summary?.oos_reliability || ''))} · 윈도우 {snapshot.validation.summary?.windows ?? 0}개
              </div>
            </div>
            <button className="ghost-button" onClick={onRefresh}>{UI_TEXT.common.refresh}</button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>학습 구간 수익률</div>
              <div style={{ marginTop: 8, fontSize: 20, fontWeight: 800 }}>
                {formatPercent(metricValue(train, 'total_return_pct'), 2)}
              </div>
            </div>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>검증 구간 수익률</div>
              <div style={{ marginTop: 8, fontSize: 20, fontWeight: 800 }}>
                {formatPercent(metricValue(validation, 'total_return_pct'), 2)}
              </div>
            </div>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>OOS 수익률</div>
              <div style={{ marginTop: 8, fontSize: 20, fontWeight: 800 }}>
                {formatPercent(metricValue(oos, 'total_return_pct'), 2)}
              </div>
            </div>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>OOS Profit Factor</div>
              <div style={{ marginTop: 8, fontSize: 20, fontWeight: 800 }}>
                {formatNumber(metricValue(oos, 'profit_factor'), 2)}
              </div>
            </div>
          </div>

          <div className="page-section" style={{ padding: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>검증 체크</div>
            <div style={{ marginTop: 8, display: 'grid', gap: 6, fontSize: 12, color: 'var(--text-3)' }}>
              <div>양수 OOS 윈도우: {snapshot.validation.summary?.positive_windows ?? 0}개</div>
              <div>OOS 거래수: {formatNumber(metricValue(oos, 'trade_count'), 0)}</div>
              <div>OOS 승률: {formatPercent(metricValue(oos, 'win_rate_pct'), 2)}</div>
              <div>OOS 최대낙폭: {formatPercent(metricValue(oos, 'max_drawdown_pct'), 2)}</div>
            </div>
          </div>

          {loading && <div style={{ color: 'var(--text-3)', fontSize: 12 }}>{UI_TEXT.common.loading}</div>}
          {errorMessage && <div style={{ color: 'var(--down)', fontSize: 12 }}>{errorMessage}</div>}
        </div>
      </div>
    </div>
  );
}
