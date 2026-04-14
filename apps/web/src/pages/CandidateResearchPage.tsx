import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  fetchCandidateResearchLatest,
  fetchCandidateResearchHistory,
  fetchCandidateResearchPendingTargets,
  fetchCandidateResearchTargets,
  fetchResearchStatus,
} from '../api/domain';
import { ConsoleActionBar } from '../components/ConsoleActionBar';
import { SymbolIdentity } from '../components/SymbolIdentity';
import { freshnessToKorean, gradeToKorean, providerStatusToKorean, reasonCodeToKorean } from '../constants/uiText';
import { useConsoleLogs } from '../hooks/useConsoleLogs';
import type { ConsoleSnapshot } from '../types/consoleView';
import type { CandidateResearchSnapshot, CandidateResearchTarget } from '../types/domain';
import { formatDateTime, formatDateTimeWithAge, formatNumber } from '../utils/format';

interface CandidateResearchPageProps {
  snapshot: ConsoleSnapshot;
  loading: boolean;
  errorMessage: string;
  onRefresh: () => void;
}

const MARKET_OPTIONS = [
  { label: 'KOSPI', value: 'KOSPI' },
  { label: 'NASDAQ', value: 'NASDAQ' },
];

type SnapshotMarketView = 'ALL' | 'KOSPI' | 'NASDAQ';

function normalizeSnapshotMarket(value: string | undefined): Exclude<SnapshotMarketView, 'ALL'> {
  return String(value || '').toUpperCase() === 'KOSPI' ? 'KOSPI' : 'NASDAQ';
}

function buildMarketCounts(items: Array<{ market?: string }>): Record<SnapshotMarketView, number> {
  const counts: Record<SnapshotMarketView, number> = { ALL: items.length, KOSPI: 0, NASDAQ: 0 };
  items.forEach((item) => {
    counts[normalizeSnapshotMarket(item.market)] += 1;
  });
  return counts;
}

function filterByMarket<T extends { market?: string }>(items: T[], marketView: SnapshotMarketView): T[] {
  if (marketView === 'ALL') return items;
  return items.filter((item) => normalizeSnapshotMarket(item.market) === marketView);
}

function snapshotGrade(item: CandidateResearchSnapshot): string {
  return String(item.validation?.grade || '').toUpperCase() || '-';
}

function scoreDisplay(item: CandidateResearchSnapshot): string {
  if (snapshotGrade(item) === 'D') return '—';
  return item.research_score != null ? formatNumber(item.research_score, 1) : '점수 대기';
}

function freshnessBadge(item: CandidateResearchSnapshot): { label: string; tone: string } {
  const freshness = String(item.freshness || item.freshness_detail?.status || '').toLowerCase();
  if (freshness === 'fresh') return { label: freshnessToKorean(freshness), tone: 'inline-badge is-success' };
  if (freshness === 'stale') return { label: freshnessToKorean(freshness), tone: 'inline-badge is-danger' };
  if (freshness === 'invalid') return { label: freshnessToKorean(freshness), tone: 'inline-badge is-danger' };
  if (freshness === 'missing') return { label: freshnessToKorean(freshness), tone: 'inline-badge' };
  return { label: freshnessToKorean(freshness), tone: 'inline-badge' };
}

function gradeBadge(item: CandidateResearchSnapshot): { label: string; tone: string } {
  const grade = snapshotGrade(item);
  if (grade === 'A') return { label: gradeToKorean(grade), tone: 'inline-badge is-success' };
  if (grade === 'B') return { label: gradeToKorean(grade), tone: 'inline-badge' };
  if (grade === 'C') return { label: gradeToKorean(grade), tone: 'inline-badge is-danger' };
  if (grade === 'D') return { label: gradeToKorean(grade), tone: 'inline-badge is-danger' };
  return { label: gradeToKorean(grade), tone: 'inline-badge' };
}

function snapshotStatus(item: CandidateResearchSnapshot): { label: string; tone: string } {
  const grade = snapshotGrade(item);
  if (grade === 'D') return { label: '검증 제외', tone: 'inline-badge is-danger' };
  if (String(item.freshness || '').toLowerCase() === 'stale') return { label: '지연 리서치', tone: 'inline-badge is-danger' };
  const score = Number(item.research_score);
  if (!Number.isFinite(score)) return { label: '점수 대기', tone: 'inline-badge' };
  if (score >= 0.8) return { label: '우선 검토', tone: 'inline-badge is-success' };
  if (score >= 0.6) return { label: '리서치 후보', tone: 'inline-badge' };
  return { label: '관찰 유지', tone: 'inline-badge is-danger' };
}

function candidateStatusBadge(item: CandidateResearchTarget): { label: string; tone: string } {
  if (!item.snapshot_exists) return { label: '리서치 없음', tone: 'inline-badge' };
  if (item.snapshot_fresh) return { label: '후보 기준 최신', tone: 'inline-badge is-success' };
  return { label: '재리서치 필요', tone: 'inline-badge is-danger' };
}

function pendingCandidateBadge(item: CandidateResearchTarget): { label: string; tone: string } {
  if (!item.snapshot_exists) return { label: '신규 리서치', tone: 'inline-badge' };
  return { label: '지연 리서치', tone: 'inline-badge is-danger' };
}

function candidateActionBadge(item: CandidateResearchTarget): { label: string; tone: string } {
  const action = String(item.final_action || '').trim().toLowerCase();
  if (action === 'review_for_entry') return { label: '진입 검토', tone: 'inline-badge is-success' };
  if (action === 'watch_only') return { label: '관찰', tone: 'inline-badge' };
  if (action === 'blocked') return { label: '차단', tone: 'inline-badge is-danger' };
  if (action === 'do_not_touch') return { label: '보류', tone: 'inline-badge' };
  return { label: action || '-', tone: 'inline-badge' };
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const width = Math.max(0, Math.min(100, value * 100));
  return (
    <div className="workspace-score-row">
      <div className="workspace-score-label">{label}</div>
      <div className="workspace-score-track">
        <div className="workspace-score-fill" style={{ width: `${width}%` }} />
      </div>
      <div className="workspace-score-value">{formatNumber(value, 2)}</div>
    </div>
  );
}

function CandidateResearchCard({ item }: { item: CandidateResearchSnapshot }) {
  const components = item.components && typeof item.components === 'object' ? item.components as Record<string, number> : {};
  const warnings = Array.isArray(item.warnings) ? item.warnings : [];
  const tags = Array.isArray(item.tags) ? item.tags : [];
  const status = snapshotStatus(item);
  const freshness = freshnessBadge(item);
  const grade = gradeBadge(item);

  return (
    <div className="page-section workspace-analysis-section" style={{ padding: 16 }}>
      <div className="workspace-card-head" style={{ marginBottom: 12 }}>
        <div>
          <div className="section-title"><SymbolIdentity code={item.symbol} name={item.name} market={item.market} /></div>
          <div className="section-copy">생성 {formatDateTimeWithAge(item.generated_at || item.bucket_ts)}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 24, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
            {scoreDisplay(item)}
          </div>
          <div className="workspace-chip-row" style={{ marginTop: 6, justifyContent: 'flex-end' }}>
            <span className={status.tone}>{status.label}</span>
            <span className={freshness.tone}>{freshness.label}</span>
            <span className={grade.tone}>{grade.label}</span>
          </div>
        </div>
      </div>

      {Object.keys(components).length > 0 && (
        <div className="workspace-score-grid">
          {Object.entries(components).map(([key, value]) => (
            <ScoreBar key={key} label={key} value={typeof value === 'number' ? value : 0} />
          ))}
        </div>
      )}

      <div className="workspace-summary-card" style={{ marginTop: 12 }}>
        <div className="workspace-summary-title">요약</div>
        <div className="workspace-summary-copy">{item.validation?.grade === 'D' ? (item.validation?.exclusion_reason || '검증 불가라 점수를 표시하지 않았습니다.') : (item.summary || '요약 없음')}</div>
      </div>

      {(warnings.length > 0 || tags.length > 0) && (
        <div className="workspace-chip-row" style={{ marginTop: 12 }}>
          {warnings.map((warning, index) => <span key={`w-${index}`} className="inline-badge is-danger">{reasonCodeToKorean(String(warning))}</span>)}
          {tags.map((tag, index) => <span key={`t-${index}`} className="inline-badge">{reasonCodeToKorean(String(tag))}</span>)}
        </div>
      )}
    </div>
  );
}

interface CandidateSectionProps {
  title: string;
  copy: string;
  items: CandidateResearchTarget[];
  loading: boolean;
  marketView: SnapshotMarketView;
  onChangeMarketView: (view: SnapshotMarketView) => void;
  onSelect: (symbol: string, market: string) => void;
  emptyText: string;
  highlightPending?: boolean;
}

function CandidateSection({
  title,
  copy,
  items,
  loading,
  marketView,
  onChangeMarketView,
  onSelect,
  emptyText,
  highlightPending = false,
}: CandidateSectionProps) {
  const marketCounts = useMemo(() => buildMarketCounts(items), [items]);
  const displayedItems = useMemo(() => filterByMarket(items, marketView), [items, marketView]);

  return (
    <section className="page-section workspace-table-section">
      <div className="workspace-card-head section-head-row">
        <div>
          <div className="section-title">{title}</div>
          <div className="section-copy">{copy}</div>
        </div>
        <div className="section-toolbar">
          <div className="section-filter-row">
            {(['ALL', 'KOSPI', 'NASDAQ'] as const).map((view) => (
              <button
                key={view}
                type="button"
                className={marketView === view ? 'ghost-button is-active' : 'ghost-button'}
                onClick={() => onChangeMarketView(view)}
              >
                {view === 'ALL' ? `전체 ${marketCounts.ALL}개` : `${view} ${marketCounts[view]}개`}
              </button>
            ))}
          </div>
          <div className="inline-badge">{loading ? '불러오는 중...' : `${displayedItems.length}개`}</div>
        </div>
      </div>

      {displayedItems.length === 0 ? (
        <div className="workspace-empty-state">{loading ? '불러오는 중...' : emptyText}</div>
      ) : (
        <>
          <div style={{ overflow: 'auto' }}>
            <table className="workspace-table" style={{ minWidth: 920 }}>
              <thead>
                <tr>
                  <th>종목</th>
                  <th>전략</th>
                  <th>순위</th>
                  <th>리서치 상태</th>
                  <th>최근 리서치</th>
                  <th>액션</th>
                </tr>
              </thead>
              <tbody>
                {displayedItems.map((item, idx) => {
                  const status = candidateStatusBadge(item);
                  const pending = pendingCandidateBadge(item);
                  const action = candidateActionBadge(item);
                  const market = item.market || 'KOSPI';
                  const symbol = item.symbol || '';
                  return (
                    <tr
                      key={`${market}-${symbol}-${item.strategy_id || idx}`}
                      style={{ cursor: 'pointer' }}
                      onClick={() => symbol && onSelect(symbol, market)}
                    >
                      <td><SymbolIdentity code={item.symbol} name={item.name} market={item.market} /></td>
                      <td>{item.strategy_name || item.strategy_id || '-'}</td>
                      <td>{item.candidate_rank ?? '-'}</td>
                      <td>
                        <div className="workspace-chip-row">
                          <span className={status.tone}>{status.label}</span>
                          {highlightPending ? <span className={pending.tone}>{pending.label}</span> : null}
                        </div>
                      </td>
                      <td>{item.snapshot_generated_at ? formatDateTime(item.snapshot_generated_at) : '없음'}</td>
                      <td><span className={action.tone}>{action.label}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="responsive-card-list">
            {displayedItems.map((item, idx) => {
              const status = candidateStatusBadge(item);
              const pending = pendingCandidateBadge(item);
              const action = candidateActionBadge(item);
              const market = item.market || 'KOSPI';
              const symbol = item.symbol || '';
              return (
                <article
                  key={`${market}-${symbol}-${item.strategy_id || idx}-card`}
                  className="responsive-card"
                  onClick={() => symbol && onSelect(symbol, market)}
                >
                  <div className="responsive-card-head">
                    <div>
                      <div className="responsive-card-title">{item.name || item.symbol || '-'}</div>
                      <div className="signal-cell-copy">{item.strategy_name || item.strategy_id || '-'} · 순위 {item.candidate_rank ?? '-'}</div>
                    </div>
                    <span className={action.tone}>{action.label}</span>
                  </div>
                  <div className="responsive-card-grid">
                    <div>
                      <div className="responsive-card-label">시장</div>
                      <div className="responsive-card-value">{item.market || '-'}</div>
                    </div>
                    <div>
                      <div className="responsive-card-label">최근 리서치</div>
                      <div className="responsive-card-value">{item.snapshot_generated_at ? formatDateTime(item.snapshot_generated_at) : '없음'}</div>
                    </div>
                    <div style={{ gridColumn: '1 / -1' }}>
                      <div className="responsive-card-label">상태</div>
                      <div className="workspace-chip-row">
                        <span className={status.tone}>{status.label}</span>
                        {highlightPending ? <span className={pending.tone}>{pending.label}</span> : null}
                      </div>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}

export function CandidateResearchPage({ snapshot, loading, errorMessage, onRefresh }: CandidateResearchPageProps) {
  const { entries, push, clear } = useConsoleLogs();

  const [symbol, setSymbol] = useState('');
  const [market, setMarket] = useState('KOSPI');
  const [latestSnapshot, setLatestSnapshot] = useState<CandidateResearchSnapshot | null>(null);
  const [history, setHistory] = useState<CandidateResearchSnapshot[]>([]);
  const [localResearchStatus, setLocalResearchStatus] = useState(snapshot.research || {});
  const [scannerTargets, setScannerTargets] = useState<CandidateResearchTarget[]>([]);
  const [enrichTargets, setEnrichTargets] = useState<CandidateResearchTarget[]>([]);
  const [targetsMarketView, setTargetsMarketView] = useState<SnapshotMarketView>('ALL');
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [targetsLoading, setTargetsLoading] = useState(false);
  const [queried, setQueried] = useState(false);
  const queryRequestIdRef = useRef(0);

  const loadCandidateBoards = useCallback(async (silent = false) => {
    setTargetsLoading(true);
    try {
      const [statusPayload, scannerPayload, enrichPayload] = await Promise.all([
        fetchResearchStatus(),
        fetchCandidateResearchTargets({ market: ['KOSPI', 'NASDAQ'], limit: 200 }),
        fetchCandidateResearchPendingTargets({ market: ['KOSPI', 'NASDAQ'], limit: 30, mode: 'missing_or_stale' }),
      ]);

      setLocalResearchStatus(statusPayload?.ok !== false ? statusPayload : {});
      setScannerTargets(scannerPayload?.ok !== false && Array.isArray(scannerPayload?.items) ? scannerPayload.items : []);
      setEnrichTargets(enrichPayload?.ok !== false && Array.isArray(enrichPayload?.items) ? enrichPayload.items : []);

      if (!silent && (statusPayload?.ok === false || scannerPayload?.ok === false || enrichPayload?.ok === false)) {
        push('warning', '후보 리서치 상태 일부만 불러왔어', statusPayload?.error || scannerPayload?.error || enrichPayload?.error, 'research');
      }
    } catch {
      setLocalResearchStatus({});
      setScannerTargets([]);
      setEnrichTargets([]);
      if (!silent) push('error', '후보 리서치 상태를 불러오지 못했어', undefined, 'research');
    } finally {
      setTargetsLoading(false);
    }
  }, [push]);

  useEffect(() => {
    void loadCandidateBoards(true);
  }, [loadCandidateBoards]);

  const runQuery = useCallback(async (targetSymbol: string, targetMarket: string) => {
    const normalizedSymbol = targetSymbol.trim().toUpperCase();
    if (!normalizedSymbol) {
      push('warning', '종목 코드를 입력하세요', undefined, 'research');
      return;
    }
    const requestId = queryRequestIdRef.current + 1;
    queryRequestIdRef.current = requestId;
    setQueryLoading(true);
    setQueried(false);
    setLatestSnapshot(null);
    setHistory([]);
    setExpandedIdx(null);

    try {
      const [latestRes, histRes] = await Promise.allSettled([
        fetchCandidateResearchLatest({ symbol: normalizedSymbol, market: targetMarket }),
        fetchCandidateResearchHistory({ symbol: normalizedSymbol, market: targetMarket, limit: 50, descending: true }),
      ]);
      if (queryRequestIdRef.current !== requestId) return;

      const latestPayload = latestRes.status === 'fulfilled' ? latestRes.value : null;
      const historyPayload = histRes.status === 'fulfilled' ? histRes.value : null;
      const latestFailed = latestRes.status === 'rejected' || latestPayload?.ok === false;
      const historyFailed = histRes.status === 'rejected' || historyPayload?.ok === false;

      if (!latestFailed && latestPayload?.snapshot) {
        setLatestSnapshot(latestPayload.snapshot);
      }

      if (!historyFailed && Array.isArray(historyPayload?.snapshots)) {
        setHistory(historyPayload.snapshots);
      }

      if (latestFailed && historyFailed) {
        push('error', '조회 실패', latestPayload?.error || historyPayload?.error, 'research');
      } else {
        push('success', `${normalizedSymbol} 조회 완료`, undefined, 'research');
        setQueried(true);
      }
    } catch {
      if (queryRequestIdRef.current !== requestId) return;
      push('error', '조회 실패', undefined, 'research');
    } finally {
      if (queryRequestIdRef.current === requestId) {
        setQueryLoading(false);
      }
    }
  }, [push]);

  const handleQuery = useCallback(() => runQuery(symbol, market), [market, runQuery, symbol]);

  const handleSelectTarget = useCallback((targetSymbol: string, targetMarket: string) => {
    setSymbol(targetSymbol);
    setMarket(targetMarket);
    void runQuery(targetSymbol, targetMarket);
  }, [runQuery]);

  const handleRefresh = useCallback(() => {
    onRefresh();
    void loadCandidateBoards();
  }, [loadCandidateBoards, onRefresh]);

  const researchStatus = localResearchStatus;
  const storageStatusLabel = providerStatusToKorean(researchStatus.status);
  const storageStatusTone = researchStatus.status === 'healthy'
    ? 'good'
    : researchStatus.status === 'missing'
      ? 'neutral'
      : 'bad';

  const statusItems = [
    { label: '현재 후보', value: `${scannerTargets.length}개`, tone: scannerTargets.length > 0 ? 'good' as const : 'neutral' as const },
    { label: '지금 리서치 필요', value: `${enrichTargets.length}개`, tone: enrichTargets.length > 0 ? 'bad' as const : 'good' as const },
    { label: '저장소 상태', value: storageStatusLabel, tone: storageStatusTone as 'good' | 'neutral' | 'bad' },
  ];

  return (
    <div className="app-shell">
      <div className="page-frame">
        <div className="content-shell workspace-grid">
          <ConsoleActionBar
            title="후보 리서치"
            subtitle="저장된 캐시 전체가 아니라 현재 스캐너 후보와 지금 돌려야 할 리서치 대상을 먼저 보여줍니다."
            lastUpdated={researchStatus.last_generated_at || latestSnapshot?.generated_at || latestSnapshot?.bucket_ts || ''}
            loading={loading}
            errorMessage={errorMessage}
            statusItems={statusItems}
            onRefresh={handleRefresh}
            logs={entries}
            onClearLogs={clear}
            actions={[]}
          />

          <section className="page-section workspace-two-column">
            <div className="workspace-card-block">
              <div className="workspace-card-head">
                <div>
                  <div className="section-title">종목 조회</div>
                  <div className="section-copy">후보를 눌러도 되고, 직접 코드와 시장을 넣어서 리서치 latest/history를 볼 수도 있어.</div>
                </div>
              </div>
              <div className="workspace-query-grid">
                <div>
                  <div className="workspace-field-label">종목 코드</div>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="예: 005930, AAPL"
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && void handleQuery()}
                    style={{ width: '100%', padding: '10px 12px', fontSize: 13 }}
                  />
                </div>
                <div>
                  <div className="workspace-field-label">시장</div>
                  <select
                    className="input-field"
                    value={market}
                    onChange={(e) => setMarket(e.target.value)}
                    style={{ width: '100%', padding: '10px 12px', fontSize: 13 }}
                  >
                    {MARKET_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
                <button
                  type="button"
                  className="action-button is-primary"
                  onClick={() => void handleQuery()}
                  disabled={queryLoading}
                  style={{ alignSelf: 'end', padding: '10px 18px', fontSize: 13 }}
                >
                  {queryLoading ? '조회 중...' : '조회'}
                </button>
              </div>
            </div>

            <div className="workspace-card-block">
              <div className="workspace-card-head">
                <div>
                  <div className="section-title">리서치 운영 요약</div>
                  <div className="section-copy">현재 후보와 저장소 상태를 분리해서 본다. 전체 캐시 개수보다 지금 돌릴 대상이 먼저 중요해.</div>
                </div>
              </div>
              <div className="workspace-mini-metrics">
                <div className="workspace-mini-metric"><span>현재 후보</span><strong>{scannerTargets.length}개</strong></div>
                <div className="workspace-mini-metric"><span>즉시 리서치 대상</span><strong>{enrichTargets.length}개</strong></div>
                <div className="workspace-mini-metric"><span>저장소 fresh</span><strong>{researchStatus.fresh_symbol_count ?? 0}개</strong></div>
                <div className="workspace-mini-metric"><span>마지막 적재</span><strong>{researchStatus.last_generated_at ? formatDateTime(researchStatus.last_generated_at) : '대기'}</strong></div>
              </div>
            </div>
          </section>

          <CandidateSection
            title="지금 리서치 돌릴 후보"
            copy="라즈베리파이 부담을 줄이려고 전체 유니버스가 아니라 현재 스캐너 후보 중 missing/stale 대상만 먼저 돌린다. 기본 배치는 30개다."
            items={enrichTargets}
            loading={targetsLoading}
            marketView={targetsMarketView}
            onChangeMarketView={setTargetsMarketView}
            onSelect={handleSelectTarget}
            emptyText={targetsLoading ? '불러오는 중...' : `${targetsMarketView} 시장에서 지금 돌릴 리서치 후보가 없어.`}
            highlightPending
          />

          <CandidateSection
            title="현재 스캐너 후보 리서치 상태"
            copy="여기가 truth source다. 저장된 snapshot 전체 목록이 아니라 지금 전략이 보고 있는 후보에 리서치가 붙었는지 먼저 본다."
            items={scannerTargets}
            loading={targetsLoading}
            marketView={targetsMarketView}
            onChangeMarketView={setTargetsMarketView}
            onSelect={handleSelectTarget}
            emptyText={targetsLoading ? '불러오는 중...' : `${targetsMarketView} 시장 현재 후보가 없어.`}
          />

          {latestSnapshot && <CandidateResearchCard item={latestSnapshot} />}

          {queried && !latestSnapshot && !queryLoading && (
            <div className="page-section workspace-empty-state">
              {symbol.trim().toUpperCase()} ({market}) 에 대한 후보 리서치 이력이 없다.
            </div>
          )}

          {history.length > 0 && (
            <section className="page-section workspace-table-section">
              <div className="workspace-card-head section-head-row">
                <div>
                  <div className="section-title">스냅샷 이력</div>
                  <div className="section-copy">현재 후보를 클릭하거나 직접 종목 조회한 뒤, 저장된 리서치 이력을 상세로 확인한다.</div>
                </div>
                <div className="section-toolbar">
                  <div className="section-table-meta">선택 종목 {symbol.trim().toUpperCase() || '-'} · 시장 {market}</div>
                  <div className="inline-badge">{history.length}개</div>
                </div>
              </div>
              <div style={{ overflow: 'auto' }}>
                <table className="workspace-table" style={{ minWidth: 760 }}>
                  <thead>
                    <tr>
                      <th>기준 시각</th>
                      <th>점수</th>
                      <th>상태</th>
                      <th>신뢰도</th>
                      <th>요약</th>
                      <th>경고</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((item, idx) => {
                      const warnings = Array.isArray(item.warnings) ? item.warnings : [];
                      const components = item.components && typeof item.components === 'object' ? item.components as Record<string, number> : {};
                      const isExpanded = expandedIdx === idx;
                      const status = snapshotStatus(item);
                      return (
                        <Fragment key={`${item.bucket_ts}-${idx}`}>
                          <tr style={{ cursor: 'pointer' }} onClick={() => setExpandedIdx(isExpanded ? null : idx)}>
                            <td>{formatDateTime(item.bucket_ts)}</td>
                            <td>{scoreDisplay(item)}</td>
                            <td><span className={status.tone}>{status.label}</span></td>
                            <td>
                              <div className="workspace-chip-row">
                                <span className={freshnessBadge(item).tone}>{freshnessBadge(item).label}</span>
                                <span className={gradeBadge(item).tone}>{gradeBadge(item).label}</span>
                              </div>
                            </td>
                            <td>{item.validation?.grade === 'D' ? (item.validation?.exclusion_reason || '검증 제외') : (item.summary ? (item.summary.length > 88 ? `${item.summary.slice(0, 88)}…` : item.summary) : '요약 없음')}</td>
                            <td>{warnings.length > 0 ? warnings.join(', ') : '경고 없음'}</td>
                          </tr>
                          {isExpanded && (
                            <tr>
                              <td colSpan={6}>
                                <div className="workspace-expanded-panel">
                                  <div className="workspace-chip-row" style={{ marginBottom: 12 }}>
                                    <span className={freshnessBadge(item).tone}>{freshnessBadge(item).label}</span>
                                    <span className={gradeBadge(item).tone}>{gradeBadge(item).label}</span>
                                    {item.validation?.reason ? <span className="inline-badge">{reasonCodeToKorean(String(item.validation.reason))}</span> : null}
                                  </div>
                                  {Object.keys(components).length > 0 && (
                                    <div className="workspace-score-grid" style={{ marginBottom: 12 }}>
                                      {Object.entries(components).map(([key, value]) => (
                                        <ScoreBar key={key} label={key} value={typeof value === 'number' ? value : 0} />
                                      ))}
                                    </div>
                                  )}
                                  <div className="workspace-summary-card">
                                    <div className="workspace-summary-title">상세 요약</div>
                                    <div className="workspace-summary-copy">{item.summary || '요약 없음'}</div>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
