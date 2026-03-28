import { UI_TEXT } from '../constants/uiText';
import { formatKRW } from '../utils/format';
import type { ConsoleSnapshot } from '../types/consoleView';

interface OverviewPageProps {
  snapshot: ConsoleSnapshot;
  loading: boolean;
  errorMessage: string;
  onRefresh: () => void;
}

export function OverviewPage({ snapshot, loading, errorMessage, onRefresh }: OverviewPageProps) {
  const allocator = snapshot.engine.allocator || {};
  const running = Boolean(snapshot.engine.execution?.state?.running);
  const guardOk = Boolean(snapshot.engine.risk_guard_state?.entry_allowed);

  return (
    <div className="app-shell">
      <div className="page-frame">
        <div className="content-shell" style={{ display: 'grid', gap: 16 }}>
          <div className="page-section" style={{ padding: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800 }}>엔진 개요</div>
              <div style={{ fontSize: 12, color: 'var(--text-4)', marginTop: 6 }}>
                장세 {allocator.regime || '-'} · 위험도 {allocator.risk_level || '-'}
              </div>
            </div>
            <button className="ghost-button" onClick={onRefresh}>{UI_TEXT.common.refresh}</button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>엔진 상태</div>
              <div style={{ marginTop: 8, fontSize: 20, fontWeight: 800, color: running ? 'var(--up)' : 'var(--down)' }}>
                {running ? UI_TEXT.status.running : UI_TEXT.status.stopped}
              </div>
            </div>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>신규 진입 가능</div>
              <div style={{ marginTop: 8, fontSize: 20, fontWeight: 800, color: guardOk ? 'var(--up)' : 'var(--down)' }}>
                {guardOk ? UI_TEXT.common.yes : UI_TEXT.common.no}
              </div>
            </div>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>허용 신호 수</div>
              <div style={{ marginTop: 8, fontSize: 20, fontWeight: 800 }}>{allocator.entry_allowed_count ?? 0}</div>
            </div>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>차단 신호 수</div>
              <div style={{ marginTop: 8, fontSize: 20, fontWeight: 800 }}>{allocator.blocked_count ?? 0}</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 700 }}>리스크 가드</div>
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-3)' }}>
                일일 손실 잔여: {formatKRW(snapshot.engine.risk_guard_state?.daily_loss_left)}
              </div>
              <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-3)' }}>
                사유: {(snapshot.engine.risk_guard_state?.reasons || []).join(', ') || '없음'}
              </div>
            </div>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 700 }}>계좌 요약</div>
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-3)' }}>
                총자산: {formatKRW(snapshot.portfolio.account?.equity_krw)}
              </div>
              <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-3)' }}>
                보유 종목 수: {(snapshot.portfolio.account?.positions || []).length}
              </div>
            </div>
          </div>

          {loading && <div style={{ color: 'var(--text-3)', fontSize: 12 }}>{UI_TEXT.common.loading}</div>}
          {errorMessage && <div style={{ color: 'var(--down)', fontSize: 12 }}>{errorMessage}</div>}
        </div>
      </div>
    </div>
  );
}
