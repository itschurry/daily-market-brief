import { useCallback, useMemo } from 'react';
import { ConsoleActionBar } from '../components/ConsoleActionBar';
import { UI_TEXT } from '../constants/uiText';
import { useConsoleLogs } from '../hooks/useConsoleLogs';
import { formatCount, formatDateTime, formatKRW, formatNumber } from '../utils/format';
import type { ActionBarStatusItem, ConsoleSnapshot } from '../types/consoleView';

interface OverviewPageProps {
  snapshot: ConsoleSnapshot;
  loading: boolean;
  errorMessage: string;
  onRefresh: () => void;
}

function engineStateLabel(raw: string): string {
  if (raw === 'running') return UI_TEXT.status.running;
  if (raw === 'paused') return UI_TEXT.status.paused;
  if (raw === 'error') return UI_TEXT.status.error;
  return UI_TEXT.status.stopped;
}

export function OverviewPage({ snapshot, loading, errorMessage, onRefresh }: OverviewPageProps) {
  const { entries, push, clear } = useConsoleLogs();
  const allocator = snapshot.engine.allocator || {};
  const state = snapshot.engine.execution?.state || {};
  const account = snapshot.engine.execution?.account || snapshot.portfolio.account || {};
  const engineState = String(state.engine_state || (state.running ? 'running' : 'stopped'));
  const guardOk = Boolean(snapshot.engine.risk_guard_state?.entry_allowed);
  const riskReasons = snapshot.engine.risk_guard_state?.reasons || [];
  const staleOptimized = Boolean(state.optimized_params?.is_stale);
  const todayOrderCounts = state.today_order_counts || {};
  const todayFailed = Number(todayOrderCounts.failed || 0);
  const todaySkipped = Number((state.last_summary as Record<string, unknown> | undefined)?.skipped_count || 0)
    || Number((state.last_summary as Record<string, unknown> | undefined)?.skipped ? ((state.last_summary as { skipped?: unknown[] }).skipped || []).length : 0);

  const handleRefresh = useCallback(() => {
    onRefresh();
    push('info', '콘솔 데이터를 수동 갱신했습니다.');
  }, [onRefresh, push]);

  const statusItems = useMemo<ActionBarStatusItem[]>(() => ([
    {
      label: '엔진 상태',
      value: engineStateLabel(engineState),
      tone: engineState === 'running' ? 'good' : engineState === 'error' ? 'bad' : 'neutral',
    },
    {
      label: '다음 실행',
      value: formatDateTime(state.next_run_at),
      tone: 'neutral',
    },
    {
      label: '오늘 주문(B/S)',
      value: `${formatNumber(todayOrderCounts.buy, 0)} / ${formatNumber(todayOrderCounts.sell, 0)}`,
      tone: 'neutral',
    },
    {
      label: '오늘 실현손익',
      value: formatKRW(state.today_realized_pnl, true),
      tone: Number(state.today_realized_pnl || 0) >= 0 ? 'good' : 'bad',
    },
  ]), [engineState, state.next_run_at, state.today_realized_pnl, todayOrderCounts.buy, todayOrderCounts.sell]);

  return (
    <div className="app-shell">
      <div className="page-frame">
        <div className="content-shell" style={{ display: 'grid', gap: 16 }}>
          {!!state.last_error && (
            <div
              className="page-section"
              style={{ padding: 12, border: '1px solid var(--down-border)', background: 'var(--down-bg)', color: 'var(--down)' }}
            >
              최근 엔진 오류: {String(state.last_error)} ({formatDateTime(state.last_error_at)})
            </div>
          )}
          {staleOptimized && (
            <div className="page-section" style={{ padding: 12, border: '1px solid #e9b557', background: '#fff7e6', color: '#8a621a' }}>
              경고: 최적화 파라미터가 stale 상태입니다. 최신 optimization 재실행을 권장합니다.
            </div>
          )}
          <ConsoleActionBar
            title="엔진 개요"
            subtitle="운영 지표 기준으로 엔진/손익/차단 상태를 즉시 확인합니다."
            lastUpdated={snapshot.fetchedAt}
            loading={loading}
            errorMessage={errorMessage}
            statusItems={statusItems}
            onRefresh={handleRefresh}
            logs={entries}
            onClearLogs={clear}
            settingsPanel={(
              <div style={{ display: 'grid', gap: 10, fontSize: 12, color: 'var(--text-3)' }}>
                <div>빠른 polling(8초): 엔진/계좌</div>
                <div>중간 polling(20초): 시그널</div>
                <div>느린 polling(60초): 검증/리포트</div>
                <div>콘솔 데이터 기준 시각: {formatDateTime(snapshot.fetchedAt)}</div>
              </div>
            )}
          />

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
            <div className="page-section" style={{ padding: 14 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>최근 실행 시각</div>
              <div style={{ marginTop: 8, fontWeight: 700 }}>{formatDateTime(state.last_run_at)}</div>
            </div>
            <div className="page-section" style={{ padding: 14 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>현재 Equity</div>
              <div style={{ marginTop: 8, fontWeight: 700 }}>{formatKRW(state.current_equity || account.equity_krw, true)}</div>
            </div>
            <div className="page-section" style={{ padding: 14 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>포지션 수</div>
              <div style={{ marginTop: 8, fontWeight: 700 }}>{formatCount((account.positions || []).length, '종목')}</div>
            </div>
            <div className="page-section" style={{ padding: 14 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>오늘 실패/스킵</div>
              <div style={{ marginTop: 8, fontWeight: 700 }}>{formatCount(todayFailed + todaySkipped, '건')}</div>
            </div>
            <div className="page-section" style={{ padding: 14 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>Validation Gate</div>
              <div style={{ marginTop: 8, fontWeight: 700 }}>
                {state.validation_policy?.validation_gate_enabled ? UI_TEXT.status.active : UI_TEXT.status.inactive}
              </div>
              <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-3)' }}>
                min trades {formatNumber(state.validation_policy?.validation_min_trades, 0)} / min sharpe {formatNumber(state.validation_policy?.validation_min_sharpe, 2)}
              </div>
            </div>
            <div className="page-section" style={{ padding: 14 }}>
              <div style={{ fontSize: 12, color: 'var(--text-4)' }}>Optimized Params</div>
              <div style={{ marginTop: 8, fontWeight: 700 }}>{staleOptimized ? 'Stale' : 'Active'}</div>
              <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-3)' }}>
                {String(state.optimized_params?.version || '-')} / {formatDateTime(state.optimized_params?.optimized_at)}
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 700 }}>리스크 가드</div>
              <div style={{ marginTop: 8, display: 'grid', gap: 6, fontSize: 12, color: 'var(--text-3)' }}>
                <div>
                  현재 진입 제한: <b style={{ color: guardOk ? 'var(--up)' : 'var(--down)' }}>
                    {guardOk ? '없음' : '있음'}
                  </b>
                </div>
                <div>일일 손실 잔여: {formatKRW(snapshot.engine.risk_guard_state?.daily_loss_left, true)}</div>
                <div>사유: {riskReasons.join(', ') || '현재 차단 사유가 없습니다.'}</div>
              </div>
            </div>
            <div className="page-section" style={{ padding: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 700 }}>신호 집계</div>
              <div style={{ marginTop: 8, display: 'grid', gap: 6, fontSize: 12, color: 'var(--text-3)' }}>
                <div>허용/차단: {formatCount(allocator.entry_allowed_count, '건')} / {formatCount(allocator.blocked_count, '건')}</div>
                <div>장세/위험도: {allocator.regime || '-'} / {allocator.risk_level || '-'}</div>
                <div>latest cycle id: {String(state.latest_cycle_id || '-')}</div>
              </div>
            </div>
          </div>

          {loading && <div style={{ color: 'var(--text-3)', fontSize: 12 }}>{UI_TEXT.common.loading}</div>}
        </div>
      </div>
    </div>
  );
}
