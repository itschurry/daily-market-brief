import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { formatDateTime } from '../utils/format';
import type { ActionBarAction, ActionBarStatusItem, ConsoleLogEntry } from '../types/consoleView';

interface ConsoleActionBarProps {
  title: string;
  subtitle?: string;
  lastUpdated: string;
  loading?: boolean;
  errorMessage?: string;
  statusItems: ActionBarStatusItem[];
  onRefresh: () => void;
  actions?: ActionBarAction[];
  logs: ConsoleLogEntry[];
  onClearLogs: () => void;
  settingsPanel?: ReactNode;
}

function levelText(level: ConsoleLogEntry['level']): string {
  if (level === 'success') return '성공';
  if (level === 'warning') return '경고';
  if (level === 'error') return '오류';
  return '정보';
}

function toneClass(tone: ActionBarStatusItem['tone']): string {
  if (tone === 'good') return 'console-status-chip is-good';
  if (tone === 'bad') return 'console-status-chip is-bad';
  return 'console-status-chip';
}

function actionClass(tone: ActionBarAction['tone']): string {
  if (tone === 'primary') return 'console-action-button is-primary';
  if (tone === 'danger') return 'console-action-button is-danger';
  return 'console-action-button';
}

export function ConsoleActionBar({
  title,
  subtitle = '',
  lastUpdated,
  loading = false,
  errorMessage = '',
  statusItems,
  onRefresh,
  actions = [],
  logs,
  onClearLogs,
  settingsPanel,
}: ConsoleActionBarProps) {
  const [logOpen, setLogOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const recentLogs = useMemo(() => logs.slice(0, 40), [logs]);
  const updateText = formatDateTime(lastUpdated);

  return (
    <>
      <div className="page-section console-actionbar-shell">
        <div className="console-actionbar-head">
          <div>
            <div className="console-actionbar-title">{title}</div>
            {subtitle && <div className="console-actionbar-subtitle">{subtitle}</div>}
            <div className="console-actionbar-meta">마지막 업데이트 {updateText}</div>
          </div>
          <div className="console-actionbar-buttons">
            <button className="ghost-button" onClick={onRefresh} disabled={loading}>
              {loading ? '갱신 중' : '새로고침'}
            </button>
            <button className="ghost-button" onClick={() => setLogOpen(true)}>
              로그 보기
            </button>
            <button className="ghost-button" onClick={() => setSettingsOpen(true)}>
              설정
            </button>
            {actions.map((action) => (
              <button
                key={action.label}
                className={actionClass(action.tone)}
                onClick={action.onClick}
                disabled={Boolean(action.disabled)}
              >
                {action.label}
              </button>
            ))}
          </div>
        </div>

        <div className="console-status-grid">
          {statusItems.map((item) => (
            <div key={`${item.label}:${item.value}`} className={toneClass(item.tone)}>
              <div className="console-status-label">{item.label}</div>
              <div className="console-status-value">{item.value}</div>
            </div>
          ))}
        </div>

        {errorMessage && <div className="console-error-line">{errorMessage}</div>}
      </div>

      {(logOpen || settingsOpen) && (
        <div className="console-overlay" onClick={() => { setLogOpen(false); setSettingsOpen(false); }} />
      )}

      <aside className={`console-drawer ${logOpen ? 'open' : ''}`} aria-hidden={!logOpen}>
        <div className="console-drawer-head">
          <div className="console-drawer-title">실행 로그</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="ghost-button" onClick={onClearLogs}>로그 비우기</button>
            <button className="ghost-button" onClick={() => setLogOpen(false)}>닫기</button>
          </div>
        </div>
        <div className="console-drawer-body">
          {recentLogs.length === 0 && <div className="console-drawer-empty">기록된 로그가 없습니다.</div>}
          {recentLogs.map((log) => (
            <div key={log.id} className={`console-log-item is-${log.level}`}>
              <div className="console-log-head">
                <span>{levelText(log.level)}</span>
                <span>{formatDateTime(log.timestamp)}</span>
              </div>
              <div className="console-log-message">{log.message}</div>
              {log.context && <div className="console-log-context">{log.context}</div>}
            </div>
          ))}
        </div>
      </aside>

      <aside className={`console-drawer ${settingsOpen ? 'open' : ''}`} aria-hidden={!settingsOpen}>
        <div className="console-drawer-head">
          <div className="console-drawer-title">설정</div>
          <button className="ghost-button" onClick={() => setSettingsOpen(false)}>닫기</button>
        </div>
        <div className="console-drawer-body">
          {settingsPanel || <div className="console-drawer-empty">설정 항목이 없습니다.</div>}
        </div>
      </aside>
    </>
  );
}
