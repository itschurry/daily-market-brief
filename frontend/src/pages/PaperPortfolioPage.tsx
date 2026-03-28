import { UI_TEXT } from '../constants/uiText';
import { formatKRW, formatNumber, formatPercent, formatSymbol } from '../utils/format';
import type { ConsoleSnapshot } from '../types/consoleView';

interface PaperPortfolioPageProps {
  snapshot: ConsoleSnapshot;
  loading: boolean;
  errorMessage: string;
  onRefresh: () => void;
}

export function PaperPortfolioPage({ snapshot, loading, errorMessage, onRefresh }: PaperPortfolioPageProps) {
  const account = snapshot.portfolio.account || {};
  const positions = (account.positions || []) as Array<Record<string, unknown>>;

  return (
    <div className="app-shell">
      <div className="page-frame">
        <div className="content-shell" style={{ display: 'grid', gap: 16 }}>
          <div className="page-section" style={{ padding: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800 }}>모의투자 포트폴리오</div>
              <div style={{ fontSize: 12, color: 'var(--text-4)', marginTop: 6 }}>
                장세 {snapshot.portfolio.regime || '-'} · 위험도 {snapshot.portfolio.risk_level || '-'}
              </div>
            </div>
            <button className="ghost-button" onClick={onRefresh}>{UI_TEXT.common.refresh}</button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>총자산(원화)</div>
              <div style={{ marginTop: 8, fontSize: 20, fontWeight: 800 }}>{formatKRW(account.equity_krw as number | undefined)}</div>
            </div>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>원화 현금</div>
              <div style={{ marginTop: 8, fontSize: 20, fontWeight: 800 }}>{formatKRW(account.cash_krw as number | undefined)}</div>
            </div>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>달러 현금</div>
              <div style={{ marginTop: 8, fontSize: 20, fontWeight: 800 }}>{formatNumber(account.cash_usd as number | undefined, 2)}</div>
            </div>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>가드 상태</div>
              <div style={{ marginTop: 8, fontSize: 20, fontWeight: 800, color: snapshot.portfolio.risk_guard_state?.entry_allowed ? 'var(--up)' : 'var(--down)' }}>
                {snapshot.portfolio.risk_guard_state?.entry_allowed ? UI_TEXT.status.active : UI_TEXT.status.inactive}
              </div>
            </div>
          </div>

          <div className="page-section" style={{ padding: 0, overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--bg-soft)', textAlign: 'left' }}>
                  <th style={{ padding: 12, fontSize: 12 }}>종목</th>
                  <th style={{ padding: 12, fontSize: 12 }}>시장</th>
                  <th style={{ padding: 12, fontSize: 12 }}>보유수량</th>
                  <th style={{ padding: 12, fontSize: 12 }}>평균단가</th>
                  <th style={{ padding: 12, fontSize: 12 }}>평가손익률</th>
                  <th style={{ padding: 12, fontSize: 12 }}>손절/익절</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((position) => {
                  const pnlPct = Number(position.unrealized_pnl_pct ?? NaN);
                  return (
                    <tr key={`${String(position.market || '')}:${String(position.code || '')}`} style={{ borderTop: '1px solid var(--border)' }}>
                      <td style={{ padding: 12, fontSize: 12 }}>{formatSymbol(String(position.code || ''), String(position.name || ''))}</td>
                      <td style={{ padding: 12, fontSize: 12 }}>{String(position.market || '-')}</td>
                      <td style={{ padding: 12, fontSize: 12 }}>{formatNumber(position.quantity as number | undefined, 0)}</td>
                      <td style={{ padding: 12, fontSize: 12 }}>{formatNumber(position.avg_price_local as number | undefined, 2)}</td>
                      <td style={{ padding: 12, fontSize: 12, color: pnlPct >= 0 ? 'var(--up)' : 'var(--down)' }}>
                        {Number.isFinite(pnlPct) ? formatPercent(pnlPct, 2) : '-'}
                      </td>
                      <td style={{ padding: 12, fontSize: 12 }}>
                        {formatPercent(position.stop_loss_pct as number | undefined, 2)} / {formatPercent(position.take_profit_pct as number | undefined, 2)}
                      </td>
                    </tr>
                  );
                })}
                {positions.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ padding: 14, fontSize: 12, color: 'var(--text-4)' }}>
                      보유 포지션이 없습니다.
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
