import { useCallback, useMemo } from 'react';
import { ConsoleActionBar } from '../components/ConsoleActionBar';
import { strategyTypeToKorean, UI_TEXT } from '../constants/uiText';
import { useConsoleLogs } from '../hooks/useConsoleLogs';
import { formatCount, formatNumber, formatPercent, formatSymbol } from '../utils/format';
import type { ConsoleSnapshot } from '../types/consoleView';
import { reasonCodeToKorean, reliabilityToKorean } from '../constants/uiText';

interface SignalsPageProps {
  snapshot: ConsoleSnapshot;
  loading: boolean;
  errorMessage: string;
  onRefresh: () => void;
}

export function SignalsPage({ snapshot, loading, errorMessage, onRefresh }: SignalsPageProps) {
  const { entries, push, clear } = useConsoleLogs();
  const signals = (snapshot.signals.signals || []).slice(0, 80);
  const allowedCount = signals.filter((row) => row.entry_allowed).length;
  const blockedCount = signals.length - allowedCount;
  const emptyMessage = errorMessage ? UI_TEXT.empty.signalsMissingData : UI_TEXT.empty.signalsNoMatches;

  const handleRefresh = useCallback(() => {
    onRefresh();
    push('info', '신호 데이터를 수동 갱신했습니다.');
  }, [onRefresh, push]);

  const statusItems = useMemo(() => ([
    {
      label: '전체 신호',
      value: `${signals.length}건`,
      tone: 'neutral' as const,
    },
    {
      label: '진입 허용',
      value: `${allowedCount}건`,
      tone: 'good' as const,
    },
    {
      label: '차단',
      value: `${blockedCount}건`,
      tone: blockedCount > 0 ? 'bad' as const : 'neutral' as const,
    },
    {
      label: '장세/위험도',
      value: `${snapshot.signals.regime || '-'} / ${snapshot.signals.risk_level || '-'}`,
      tone: 'neutral' as const,
    },
  ]), [allowedCount, blockedCount, signals.length, snapshot.signals.regime, snapshot.signals.risk_level]);

  return (
    <div className="app-shell">
      <div className="page-frame">
        <div className="content-shell" style={{ display: 'grid', gap: 16 }}>
          <ConsoleActionBar
            title="신호 관리"
            subtitle="진입 허용/차단 사유와 검증 신뢰도를 운영 기준으로 확인합니다."
            lastUpdated={snapshot.fetchedAt}
            loading={loading}
            errorMessage={errorMessage}
            statusItems={statusItems}
            onRefresh={handleRefresh}
            logs={entries}
            onClearLogs={clear}
            settingsPanel={(
              <div style={{ display: 'grid', gap: 10, fontSize: 12, color: 'var(--text-3)' }}>
                <div>표시 최대 건수: 80건</div>
                <div>정렬 기준: EV 내림차순</div>
                <div>차단 사유는 상세 보기로 확인하세요.</div>
              </div>
            )}
          />

          <div className="page-section" style={{ padding: 0, overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 1320 }}>
              <thead>
                <tr style={{ background: 'var(--bg-soft)', textAlign: 'left' }}>
                  <th style={{ padding: 12, fontSize: 12 }}>종목</th>
                  <th style={{ padding: 12, fontSize: 12 }}>전략</th>
                  <th style={{ padding: 12, fontSize: 12 }}>점수/신뢰</th>
                  <th style={{ padding: 12, fontSize: 12 }}>EV</th>
                  <th style={{ padding: 12, fontSize: 12 }}>진입</th>
                  <th style={{ padding: 12, fontSize: 12 }}>권장 수량</th>
                  <th style={{ padding: 12, fontSize: 12 }}>검증 신뢰도</th>
                  <th style={{ padding: 12, fontSize: 12 }}>유동성/슬리피지</th>
                  <th style={{ padding: 12, fontSize: 12 }}>사유</th>
                </tr>
              </thead>
              <tbody>
                {signals.map((signal) => {
                  const ev = signal.ev_metrics?.expected_value;
                  const winProbability = signal.ev_metrics?.win_probability;
                  const size = signal.size_recommendation?.quantity ?? 0;
                  const sizeReason = signal.size_recommendation?.reason || '-';
                  const reliability = reliabilityToKorean(String(signal.ev_metrics?.reliability || ''));
                  const liquidity = signal.execution_realism?.liquidity_gate_status || '-';
                  const slippage = signal.execution_realism?.slippage_bps;
                  const reasons = (signal.reason_codes || []).map((reason) => reasonCodeToKorean(reason));
                  const blocked = !signal.entry_allowed;
                  return (
                    <tr key={`${signal.market || ''}:${signal.code || ''}`} style={{ borderTop: '1px solid var(--border)' }}>
                      <td style={{ padding: 12, fontSize: 12 }}>{formatSymbol(signal.code, signal.name)} ({signal.market || '-'})</td>
                      <td style={{ padding: 12, fontSize: 12 }}>{strategyTypeToKorean(signal.strategy_type || '')}</td>
                      <td style={{ padding: 12, fontSize: 12 }}>
                        {formatNumber((signal as { score?: number }).score, 2)} / {winProbability === undefined ? '-' : formatPercent(winProbability, 2, true)}
                      </td>
                      <td style={{ padding: 12, fontSize: 12, fontWeight: 700 }}>
                        {ev === undefined ? '-' : formatNumber(ev, 2)}
                      </td>
                      <td style={{ padding: 12, fontSize: 12, color: blocked ? 'var(--down)' : 'var(--up)', fontWeight: 700 }}>
                        {blocked ? UI_TEXT.status.blocked : UI_TEXT.status.allowed}
                      </td>
                      <td style={{ padding: 12, fontSize: 12 }}>
                        {size > 0 ? formatCount(size, '주') : `0주 (${sizeReason})`}
                      </td>
                      <td style={{ padding: 12, fontSize: 12 }}>{reliability || '-'}</td>
                      <td style={{ padding: 12, fontSize: 12 }}>
                        {liquidity} / {slippage === undefined ? '-' : `${formatNumber(slippage, 2)} bps`}
                      </td>
                      <td style={{ padding: 12, fontSize: 12, color: blocked ? 'var(--down)' : 'var(--text-4)' }}>
                        {reasons.length <= 1 && (reasons[0] || '-')}
                        {reasons.length > 1 && (
                          <details>
                            <summary>상세 {reasons.length}건</summary>
                            <div style={{ marginTop: 6, display: 'grid', gap: 4 }}>
                              {reasons.map((reason, idx) => <div key={`${signal.code}-${idx}`}>{reason}</div>)}
                            </div>
                          </details>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {signals.length === 0 && (
                  <tr>
                    <td colSpan={9} style={{ padding: 14, fontSize: 12, color: 'var(--text-4)' }}>
                      {emptyMessage}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {loading && <div style={{ color: 'var(--text-3)', fontSize: 12 }}>{UI_TEXT.common.loading}</div>}
        </div>
      </div>
    </div>
  );
}
