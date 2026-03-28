import { buildSignalRows } from '../adapters/consoleViewAdapter';
import { strategyTypeToKorean, UI_TEXT } from '../constants/uiText';
import { formatNumber, formatPercent } from '../utils/format';
import type { ConsoleSnapshot } from '../types/consoleView';

interface SignalsPageProps {
  snapshot: ConsoleSnapshot;
  loading: boolean;
  errorMessage: string;
  onRefresh: () => void;
}

export function SignalsPage({ snapshot, loading, errorMessage, onRefresh }: SignalsPageProps) {
  const rows = buildSignalRows(snapshot).slice(0, 60);

  return (
    <div className="app-shell">
      <div className="page-frame">
        <div className="content-shell" style={{ display: 'grid', gap: 16 }}>
          <div className="page-section" style={{ padding: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800 }}>신호 관리</div>
              <div style={{ fontSize: 12, color: 'var(--text-4)', marginTop: 6 }}>
                장세 {snapshot.signals.regime || '-'} · 위험도 {snapshot.signals.risk_level || '-'} · 총 {snapshot.signals.count ?? 0}건
              </div>
            </div>
            <button className="ghost-button" onClick={onRefresh}>{UI_TEXT.common.refresh}</button>
          </div>

          <div className="page-section" style={{ padding: 0, overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--bg-soft)', textAlign: 'left' }}>
                  <th style={{ padding: 12, fontSize: 12 }}>종목</th>
                  <th style={{ padding: 12, fontSize: 12 }}>전략</th>
                  <th style={{ padding: 12, fontSize: 12 }}>EV</th>
                  <th style={{ padding: 12, fontSize: 12 }}>승률</th>
                  <th style={{ padding: 12, fontSize: 12 }}>추천 비중</th>
                  <th style={{ padding: 12, fontSize: 12 }}>신호 상태</th>
                  <th style={{ padding: 12, fontSize: 12 }}>차단 사유</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const signal = row.signal;
                  const ev = signal.ev_metrics?.expected_value;
                  const winProbability = signal.ev_metrics?.win_probability;
                  const size = signal.size_recommendation?.quantity ?? 0;
                  return (
                    <tr key={`${signal.market || ''}:${signal.code || ''}`} style={{ borderTop: '1px solid var(--border)' }}>
                      <td style={{ padding: 12, fontSize: 12 }}>{row.symbol}</td>
                      <td style={{ padding: 12, fontSize: 12 }}>{strategyTypeToKorean(signal.strategy_type || '')}</td>
                      <td style={{ padding: 12, fontSize: 12, fontWeight: 700 }}>
                        {ev === undefined ? '-' : formatNumber(ev, 2)}
                      </td>
                      <td style={{ padding: 12, fontSize: 12 }}>
                        {winProbability === undefined ? '-' : formatPercent(winProbability, 2, true)}
                      </td>
                      <td style={{ padding: 12, fontSize: 12 }}>
                        {size > 0 ? formatNumber(size, 0) : '-'}
                      </td>
                      <td style={{ padding: 12, fontSize: 12, color: row.statusLabel === '추천' ? 'var(--up)' : 'var(--down)', fontWeight: 700 }}>
                        {row.statusLabel}
                      </td>
                      <td style={{ padding: 12, fontSize: 12, color: row.statusLabel === '추천' ? 'var(--text-4)' : 'var(--down)' }}>
                        {row.reasonSummary}
                      </td>
                    </tr>
                  );
                })}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={7} style={{ padding: 14, fontSize: 12, color: 'var(--text-4)' }}>
                      {UI_TEXT.common.noData}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {loading && <div style={{ color: 'var(--text-3)', fontSize: 12 }}>{UI_TEXT.common.loading}</div>}
          {errorMessage && <div style={{ color: 'var(--down)', fontSize: 12 }}>{errorMessage}</div>}
        </div>
      </div>
    </div>
  );
}
