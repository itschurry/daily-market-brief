import {
  buildActionBoardView,
  buildTodayRecommendationView,
  buildTodayReportView,
  buildWatchDecisionView,
} from '../adapters/consoleViewAdapter';
import type { ReactNode } from 'react';
import { UI_TEXT } from '../constants/uiText';
import { formatDateTime, formatNumber, formatPercent } from '../utils/format';
import type { ConsoleSnapshot } from '../types/consoleView';
import type { ReportTab } from '../types/navigation';

interface ReportsPageProps {
  snapshot: ConsoleSnapshot;
  loading: boolean;
  errorMessage: string;
  reportTab: ReportTab;
  onRefresh: () => void;
}

function renderTodayReport(snapshot: ConsoleSnapshot) {
  const view = buildTodayReportView(snapshot);
  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div className="page-section" style={{ padding: 18 }}>
        <div style={{ fontSize: 22, fontWeight: 800 }}>{UI_TEXT.reportTabs.todayReport}</div>
        <div style={{ fontSize: 12, color: 'var(--text-4)', marginTop: 6 }}>생성 시간 {formatDateTime(view.generatedAt)}</div>
      </div>

      <div className="page-section" style={{ padding: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 700 }}>오늘 시장 요약</div>
        <div style={{ marginTop: 10, display: 'grid', gap: 8, fontSize: 13, color: 'var(--text-2)', lineHeight: 1.7 }}>
          {view.summaryLines.map((line, idx) => (
            <div key={`summary-${idx}`} style={{ borderBottom: '1px solid var(--border-light)', paddingBottom: 8 }}>
              {line}
            </div>
          ))}
        </div>
      </div>

      <div className="page-section" style={{ padding: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 700 }}>위험/주의</div>
        <div style={{ marginTop: 10, display: 'grid', gap: 8, fontSize: 13, color: 'var(--down)' }}>
          {view.riskHighlights.map((line, idx) => (
            <div key={`risk-${idx}`} style={{ borderBottom: '1px solid var(--border-light)', paddingBottom: 8 }}>
              {line}
            </div>
          ))}
        </div>
      </div>

      <div className="page-section" style={{ padding: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 700 }}>오늘의 전략 포인트</div>
        <div style={{ marginTop: 8, fontSize: 18, fontWeight: 800, color: 'var(--accent)' }}>{view.strategyPoint}</div>
      </div>
    </div>
  );
}

function renderTodayRecommendations(snapshot: ConsoleSnapshot) {
  const view = buildTodayRecommendationView(snapshot, 15);
  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div className="page-section" style={{ padding: 18 }}>
        <div style={{ fontSize: 22, fontWeight: 800 }}>{UI_TEXT.reportTabs.todayRecommendations}</div>
        <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-4)' }}>
          추천 {view.recommended.length}건 · 추천 제외 {view.excluded.length}건
        </div>
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
              <th style={{ padding: 12, fontSize: 12 }}>사유</th>
            </tr>
          </thead>
          <tbody>
            {view.recommended.map((item, idx) => (
              <tr key={`rec-${idx}`} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: 12, fontSize: 12 }}>{item.symbol}</td>
                <td style={{ padding: 12, fontSize: 12 }}>{item.strategy}</td>
                <td style={{ padding: 12, fontSize: 12 }}>{formatNumber(item.expectedValue, 2)}</td>
                <td style={{ padding: 12, fontSize: 12 }}>{formatPercent(item.winProbability, 2, true)}</td>
                <td style={{ padding: 12, fontSize: 12 }}>{formatNumber(item.size, 0)}</td>
                <td style={{ padding: 12, fontSize: 12, color: 'var(--up)', fontWeight: 700 }}>{item.status}</td>
                <td style={{ padding: 12, fontSize: 12 }}>-</td>
              </tr>
            ))}
            {view.excluded.map((item, idx) => (
              <tr key={`exc-${idx}`} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: 12, fontSize: 12 }}>{item.symbol}</td>
                <td style={{ padding: 12, fontSize: 12 }}>{item.strategy}</td>
                <td style={{ padding: 12, fontSize: 12 }}>{formatNumber(item.expectedValue, 2)}</td>
                <td style={{ padding: 12, fontSize: 12 }}>{formatPercent(item.winProbability, 2, true)}</td>
                <td style={{ padding: 12, fontSize: 12 }}>{item.size > 0 ? formatNumber(item.size, 0) : '-'}</td>
                <td style={{ padding: 12, fontSize: 12, color: 'var(--down)', fontWeight: 700 }}>{item.status}</td>
                <td style={{ padding: 12, fontSize: 12, color: 'var(--down)' }}>{item.reasonSummary}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function renderActionBoard(snapshot: ConsoleSnapshot) {
  const view = buildActionBoardView(snapshot);
  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div className="page-section" style={{ padding: 18 }}>
        <div style={{ fontSize: 22, fontWeight: 800 }}>{UI_TEXT.reportTabs.actionBoard}</div>
      </div>

      <div className="page-section" style={{ padding: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 700 }}>오늘의 기본 행동 규칙</div>
        <div style={{ marginTop: 10, display: 'grid', gap: 8, fontSize: 13, color: 'var(--text-2)' }}>
          {view.rules.map((rule, idx) => (
            <div key={`rule-${idx}`}>{rule}</div>
          ))}
        </div>
      </div>

      <div className="page-section" style={{ padding: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 700 }}>체크리스트</div>
        <div style={{ marginTop: 10, display: 'grid', gap: 10 }}>
          {view.checklist.map((item, idx) => (
            <div key={`check-${idx}`} style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 10 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: item.done ? 'var(--up)' : 'var(--down)' }}>
                {item.done ? '완료' : '확인 필요'} · {item.label}
              </div>
              <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-3)' }}>{item.detail}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function renderWatchDecision(snapshot: ConsoleSnapshot) {
  const view = buildWatchDecisionView(snapshot);
  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div className="page-section" style={{ padding: 18 }}>
        <div style={{ fontSize: 22, fontWeight: 800 }}>{UI_TEXT.reportTabs.watchDecision}</div>
        <div style={{ marginTop: 8, fontSize: 20, fontWeight: 800, color: 'var(--accent)' }}>{view.mode}</div>
      </div>

      <div className="page-section" style={{ padding: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 700 }}>판단 근거</div>
        <div style={{ marginTop: 10, display: 'grid', gap: 8, fontSize: 13, color: 'var(--text-2)' }}>
          {view.rationale.map((line, idx) => (
            <div key={`rationale-${idx}`}>{line}</div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function ReportsPage({ snapshot, loading, errorMessage, reportTab, onRefresh }: ReportsPageProps) {
  let body: ReactNode;
  if (reportTab === 'today-recommendations') {
    body = renderTodayRecommendations(snapshot);
  } else if (reportTab === 'action-board') {
    body = renderActionBoard(snapshot);
  } else if (reportTab === 'watch-decision') {
    body = renderWatchDecision(snapshot);
  } else {
    body = renderTodayReport(snapshot);
  }

  return (
    <div className="app-shell">
      <div className="page-frame">
        <div className="content-shell" style={{ display: 'grid', gap: 16 }}>
          <div className="page-section" style={{ padding: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: 12, color: 'var(--text-4)' }}>
              콘솔 데이터 기준 시각 {formatDateTime(snapshot.fetchedAt)}
            </div>
            <button className="ghost-button" onClick={onRefresh}>{UI_TEXT.common.refresh}</button>
          </div>
          {body}
          {loading && <div style={{ color: 'var(--text-3)', fontSize: 12 }}>{UI_TEXT.common.loading}</div>}
          {errorMessage && <div style={{ color: 'var(--down)', fontSize: 12 }}>{errorMessage}</div>}
        </div>
      </div>
    </div>
  );
}
