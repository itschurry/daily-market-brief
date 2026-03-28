import { useCallback, useMemo } from 'react';
import { ConsoleActionBar } from '../components/ConsoleActionBar';
import { UI_TEXT } from '../constants/uiText';
import { useConsoleLogs } from '../hooks/useConsoleLogs';
import { formatKRW } from '../utils/format';
import type { ActionBarStatusItem, ConsoleSnapshot } from '../types/consoleView';

interface OverviewPageProps {
  snapshot: ConsoleSnapshot;
  loading: boolean;
  errorMessage: string;
  onRefresh: () => void;
}

export function OverviewPage({ snapshot, loading, errorMessage, onRefresh }: OverviewPageProps) {
  const { entries, push, clear } = useConsoleLogs();
  const allocator = snapshot.engine.allocator || {};
  const running = Boolean(snapshot.engine.execution?.state?.running);
  const guardOk = Boolean(snapshot.engine.risk_guard_state?.entry_allowed);
  const riskReasons = snapshot.engine.risk_guard_state?.reasons || [];

  const handleRefresh = useCallback(() => {
    onRefresh();
    push('info', '콘솔 데이터를 수동 갱신했습니다.');
  }, [onRefresh, push]);

  const statusItems = useMemo<ActionBarStatusItem[]>(() => ([
    {
      label: '엔진 상태',
      value: running ? UI_TEXT.status.running : UI_TEXT.status.stopped,
      tone: running ? 'good' : 'bad',
    },
    {
      label: '신규 진입 가능',
      value: guardOk ? UI_TEXT.common.yes : UI_TEXT.common.no,
      tone: guardOk ? 'good' : 'bad',
    },
    {
      label: '허용/차단 신호',
      value: `${allocator.entry_allowed_count ?? 0} / ${allocator.blocked_count ?? 0}`,
      tone: 'neutral',
    },
    {
      label: '장세/위험도',
      value: `${allocator.regime || '-'} / ${allocator.risk_level || '-'}`,
      tone: 'neutral',
    },
  ]), [allocator.blocked_count, allocator.entry_allowed_count, allocator.regime, allocator.risk_level, guardOk, running]);

  return (
    <div className="app-shell">
      <div className="page-frame">
        <div className="content-shell" style={{ display: 'grid', gap: 16 }}>
          <ConsoleActionBar
            title="엔진 개요"
            subtitle="엔진 상태와 리스크 가드의 현재 운용 상태를 확인합니다."
            lastUpdated={snapshot.fetchedAt}
            loading={loading}
            errorMessage={errorMessage}
            statusItems={statusItems}
            onRefresh={handleRefresh}
            logs={entries}
            onClearLogs={clear}
            settingsPanel={(
              <div style={{ display: 'grid', gap: 10, fontSize: 12, color: 'var(--text-3)' }}>
                <div>자동 갱신 주기: 30초</div>
                <div>콘솔 데이터 기준 시각: {snapshot.fetchedAt || '-'}</div>
                <div>오류 발생 시 로그 드로어에서 원인을 먼저 확인하세요.</div>
              </div>
            )}
          />

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
                사유: {riskReasons.join(', ') || '없음'}
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
        </div>
      </div>
    </div>
  );
}
