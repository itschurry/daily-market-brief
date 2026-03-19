import { useMemo, useState } from 'react';
import { usePaperTrading } from '../hooks/usePaperTrading';

function formatKrw(value?: number | null) {
  if (value === undefined || value === null) return '—';
  return `${new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 }).format(value)}원`;
}

function formatUsd(value?: number | null) {
  if (value === undefined || value === null) return '—';
  return `$${new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value)}`;
}

function withCommaDigits(raw: string) {
  const digits = raw.replace(/\D/g, '');
  if (!digits) return '';
  return new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 }).format(Number(digits));
}

function parseCommaNumber(value: string) {
  const normalized = value.replace(/,/g, '').trim();
  if (!normalized) return 0;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatSignedPct(value?: number | null) {
  if (value === undefined || value === null) return '—';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function formatDateTime(value?: string | null) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('ko-KR');
}

export function PaperTradingTab() {
  const { account, engineState, status, lastError, refresh, reset, autoInvest, refreshEngineStatus, startEngine, stopEngine } = usePaperTrading();
  const [seedKrw, setSeedKrw] = useState('10,000,000');
  const [seedUsd, setSeedUsd] = useState('10,000');
  const [paperDays, setPaperDays] = useState('7');
  const [autoMarket] = useState<'KOSPI' | 'NASDAQ'>('NASDAQ');
  const [autoMaxPositions, setAutoMaxPositions] = useState('5');
  const [autoMinScore, setAutoMinScore] = useState('60');
  const [autoIncludeNeutral, setAutoIncludeNeutral] = useState(false);
  const [engineIntervalSeconds, setEngineIntervalSeconds] = useState('300');
  const [engineSignalInterval, setEngineSignalInterval] = useState<'1m' | '2m' | '5m' | '15m' | '30m' | '60m' | '90m' | '1d'>('5m');
  const [engineSignalRange, setEngineSignalRange] = useState<'1d' | '5d' | '1mo' | '3mo' | '6mo' | '1y'>('5d');
  const [engineRunKOSPI, setEngineRunKOSPI] = useState(true);
  const [engineRunNASDAQ, setEngineRunNASDAQ] = useState(true);
  const [engineDailyBuyLimit, setEngineDailyBuyLimit] = useState('20');
  const [engineDailySellLimit, setEngineDailySellLimit] = useState('20');
  const [engineMaxOrdersPerSymbol, setEngineMaxOrdersPerSymbol] = useState('1');
  const [engineRsiMin, setEngineRsiMin] = useState('45');
  const [engineRsiMax, setEngineRsiMax] = useState('68');
  const [engineVolumeRatioMin, setEngineVolumeRatioMin] = useState('1.2');
  const [engineStopLossPct, setEngineStopLossPct] = useState('7');
  const [engineTakeProfitPct, setEngineTakeProfitPct] = useState('18');
  const [engineMaxHoldingDays, setEngineMaxHoldingDays] = useState('30');
  const [statusMessage, setStatusMessage] = useState('');

  const initialTotalKrw = useMemo(() => {
    return (account.initial_cash_krw || 0) + ((account.initial_cash_usd || 0) * (account.fx_rate || 0));
  }, [account.initial_cash_krw, account.initial_cash_usd, account.fx_rate]);

  const runningReturnPct = useMemo(() => {
    if (!initialTotalKrw) return 0;
    return ((account.equity_krw / initialTotalKrw) - 1) * 100;
  }, [account.equity_krw, initialTotalKrw]);

  async function handleReset() {
    const result = await reset({
      initial_cash_krw: parseCommaNumber(seedKrw),
      initial_cash_usd: parseCommaNumber(seedUsd),
      paper_days: Math.max(1, Math.min(365, Math.floor(parseCommaNumber(paperDays)))),
    });
    if (!result.ok) {
      setStatusMessage(result.error || '초기화 실패');
      return;
    }
    setStatusMessage('모의계좌를 초기화했습니다.');
  }

  async function handleAutoInvest() {
    const parsedMax = Number(autoMaxPositions);
    const parsedScore = Number(autoMinScore);
    const result = await autoInvest({
      market: autoMarket,
      max_positions: Number.isFinite(parsedMax) ? Math.max(1, Math.floor(parsedMax)) : 5,
      min_score: Number.isFinite(parsedScore) ? parsedScore : 60,
      include_neutral: autoIncludeNeutral,
    });
    if (!result.ok) {
      setStatusMessage(result.error || '자동매수 실패');
      return;
    }
    const payload = result.payload || {};
    const executed = Array.isArray(payload.executed) ? payload.executed.length : 0;
    const skipped = Array.isArray(payload.skipped) ? payload.skipped.length : 0;
    if (executed === 0 && payload.message) {
      setStatusMessage(String(payload.message));
      return;
    }
    setStatusMessage(`추천 기반 자동매수 완료: 체결 ${executed}건, 스킵 ${skipped}건`);
  }

  async function handleStartEngine() {
    const markets: Array<'KOSPI' | 'NASDAQ'> = [];
    if (engineRunKOSPI) markets.push('KOSPI');
    if (engineRunNASDAQ) markets.push('NASDAQ');
    if (markets.length === 0) {
      setStatusMessage('최소 1개 시장을 선택해 주세요.');
      return;
    }
    const result = await startEngine({
      interval_seconds: Math.max(30, Math.min(3600, Math.floor(Number(engineIntervalSeconds) || 300))),
      signal_interval: engineSignalInterval,
      signal_range: engineSignalRange,
      markets,
      max_positions_per_market: Math.max(1, Math.min(20, Math.floor(Number(autoMaxPositions) || 5))),
      min_score: Math.max(0, Math.min(100, Number(autoMinScore) || 60)),
      include_neutral: autoIncludeNeutral,
      daily_buy_limit: Math.max(1, Math.min(200, Math.floor(Number(engineDailyBuyLimit) || 20))),
      daily_sell_limit: Math.max(1, Math.min(200, Math.floor(Number(engineDailySellLimit) || 20))),
      max_orders_per_symbol_per_day: Math.max(1, Math.min(10, Math.floor(Number(engineMaxOrdersPerSymbol) || 1))),
      rsi_min: Math.max(10, Math.min(90, Number(engineRsiMin) || 45)),
      rsi_max: Math.max(10, Math.min(90, Number(engineRsiMax) || 68)),
      volume_ratio_min: Math.max(0.5, Math.min(5, Number(engineVolumeRatioMin) || 1.2)),
      stop_loss_pct: Math.max(1, Math.min(50, Number(engineStopLossPct) || 7)),
      take_profit_pct: Math.max(1, Math.min(100, Number(engineTakeProfitPct) || 18)),
      max_holding_days: Math.max(1, Math.min(180, Math.floor(Number(engineMaxHoldingDays) || 30))),
    });
    if (!result.ok) {
      setStatusMessage(result.error || '자동매매 실행 실패');
      return;
    }
    setStatusMessage('추천 기반 자동매매 엔진을 시작했습니다. (매수/매도, 지표 기반, 백그라운드 반복 실행)');
    await refreshEngineStatus();
  }

  async function handleStopEngine() {
    const result = await stopEngine();
    if (!result.ok) {
      setStatusMessage(result.error || '자동매매 중지 실패');
      return;
    }
    setStatusMessage('자동매매 엔진을 중지했습니다.');
    await refreshEngineStatus();
  }

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div className="page-section" style={{ display: 'grid', gap: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 12, color: 'var(--text-4)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Paper Trading</div>
            <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-1)', marginTop: 6 }}>자동 모의투자</div>
            <div style={{ fontSize: 13, color: 'var(--text-4)', marginTop: 8 }}>KOSPI/NASDAQ를 병렬 운용하며 원화/달러 자금을 분리해 관리합니다.</div>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button className="ghost-button" onClick={() => refresh(true)}>평가 갱신</button>
            <span style={{ fontSize: 12, color: 'var(--text-4)' }}>{status === 'loading' ? '불러오는 중' : status === 'error' ? '오류' : '정상'}</span>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
          <div style={{ padding: '12px 14px', borderRadius: 14, border: '1px solid var(--border)', background: 'var(--bg-soft)' }}>
            <div style={{ fontSize: 12, color: 'var(--text-4)' }}>총자산 (KRW 환산)</div>
            <div style={{ fontSize: 22, fontWeight: 800, marginTop: 6 }}>{formatKrw(account.equity_krw)}</div>
          </div>
          <div style={{ padding: '12px 14px', borderRadius: 14, border: '1px solid var(--border)', background: 'var(--bg-soft)' }}>
            <div style={{ fontSize: 12, color: 'var(--text-4)' }}>현금 (KRW / USD)</div>
            <div style={{ fontSize: 16, fontWeight: 800, marginTop: 6 }}>{formatKrw(account.cash_krw)}</div>
            <div style={{ fontSize: 14, color: 'var(--text-3)', marginTop: 4 }}>{formatUsd(account.cash_usd)}</div>
          </div>
          <div style={{ padding: '12px 14px', borderRadius: 14, border: '1px solid var(--border)', background: 'var(--bg-soft)' }}>
            <div style={{ fontSize: 12, color: 'var(--text-4)' }}>평가손익률</div>
            <div style={{ fontSize: 22, fontWeight: 800, marginTop: 6, color: runningReturnPct >= 0 ? 'var(--up)' : 'var(--down)' }}>{formatSignedPct(runningReturnPct)}</div>
          </div>
          <div style={{ padding: '12px 14px', borderRadius: 14, border: '1px solid var(--border)', background: 'var(--bg-soft)' }}>
            <div style={{ fontSize: 12, color: 'var(--text-4)' }}>모의투자 기간</div>
            <div style={{ fontSize: 16, fontWeight: 800, marginTop: 6 }}>{account.paper_days || 0}일</div>
            <div style={{ fontSize: 12, color: 'var(--text-4)', marginTop: 4 }}>경과 {account.days_elapsed || 0}일 · 남음 {account.days_left || 0}일</div>
          </div>
        </div>
      </div>

      <div className="page-section" style={{ display: 'grid', gap: 12 }}>
        <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-1)' }}>초기 자금 / 기간 설정</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>초기 원화 자금 (KRW)</span>
            <input className="backtest-input" inputMode="numeric" value={seedKrw} onChange={(event) => setSeedKrw(withCommaDigits(event.target.value))} />
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>초기 달러 자금 (USD)</span>
            <input className="backtest-input" inputMode="numeric" value={seedUsd} onChange={(event) => setSeedUsd(withCommaDigits(event.target.value))} />
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>모의투자 기간 (일)</span>
            <input className="backtest-input" inputMode="numeric" value={paperDays} onChange={(event) => setPaperDays(withCommaDigits(event.target.value))} />
          </label>
        </div>
        <div>
          <button className="ghost-button" onClick={handleReset}>초기 자금/기간 적용</button>
        </div>
      </div>

      <div className="page-section" style={{ display: 'grid', gap: 12 }}>
        <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-1)' }}>추천 기반 자동투자 엔진</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
          <div style={{ padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 12, background: 'var(--bg-soft)', fontSize: 12, color: 'var(--text-3)' }}>
            <div>상태: <b style={{ color: engineState.running ? 'var(--up)' : 'var(--text-2)' }}>{engineState.running ? '실행 중' : '중지'}</b></div>
            <div style={{ marginTop: 4 }}>시작: {formatDateTime(engineState.started_at)}</div>
            <div style={{ marginTop: 4 }}>최근 실행: {formatDateTime(engineState.last_run_at)}</div>
            <div style={{ marginTop: 4 }}>
              최근 체결: 매수 {engineState.last_summary?.executed_buy_count ?? 0}건 / 매도 {engineState.last_summary?.executed_sell_count ?? 0}건
            </div>
            <div style={{ marginTop: 4, color: engineState.last_error ? 'var(--down)' : 'var(--text-4)' }}>
              오류: {engineState.last_error || '없음'}
            </div>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 24 }}>
            <input type="checkbox" checked={engineRunKOSPI} onChange={(event) => setEngineRunKOSPI(event.target.checked)} />
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>KOSPI 실행</span>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 24 }}>
            <input type="checkbox" checked={engineRunNASDAQ} onChange={(event) => setEngineRunNASDAQ(event.target.checked)} />
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>NASDAQ 실행</span>
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>최대 포지션 수</span>
            <input className="backtest-input" type="number" min={1} max={20} value={autoMaxPositions} onChange={(event) => setAutoMaxPositions(event.target.value)} />
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>최소 점수</span>
            <input className="backtest-input" type="number" min={0} max={100} value={autoMinScore} onChange={(event) => setAutoMinScore(event.target.value)} />
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>실행 주기(초)</span>
            <input className="backtest-input" type="number" min={30} max={3600} value={engineIntervalSeconds} onChange={(event) => setEngineIntervalSeconds(event.target.value)} />
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>지표 봉 간격</span>
            <select className="backtest-input" value={engineSignalInterval} onChange={(event) => setEngineSignalInterval(event.target.value as '1m' | '2m' | '5m' | '15m' | '30m' | '60m' | '90m' | '1d')}>
              <option value="1m">1m</option>
              <option value="2m">2m</option>
              <option value="5m">5m</option>
              <option value="15m">15m</option>
              <option value="30m">30m</option>
              <option value="60m">60m</option>
              <option value="90m">90m</option>
              <option value="1d">1d</option>
            </select>
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>지표 조회 범위</span>
            <select className="backtest-input" value={engineSignalRange} onChange={(event) => setEngineSignalRange(event.target.value as '1d' | '5d' | '1mo' | '3mo' | '6mo' | '1y')}>
              <option value="1d">1d</option>
              <option value="5d">5d</option>
              <option value="1mo">1mo</option>
              <option value="3mo">3mo</option>
              <option value="6mo">6mo</option>
              <option value="1y">1y</option>
            </select>
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>RSI 최소/최대</span>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <input className="backtest-input" type="number" min={10} max={90} value={engineRsiMin} onChange={(event) => setEngineRsiMin(event.target.value)} />
              <input className="backtest-input" type="number" min={10} max={90} value={engineRsiMax} onChange={(event) => setEngineRsiMax(event.target.value)} />
            </div>
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>최소 거래량 배수</span>
            <input className="backtest-input" type="number" min={0.5} max={5} step={0.1} value={engineVolumeRatioMin} onChange={(event) => setEngineVolumeRatioMin(event.target.value)} />
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>손절/익절(%)</span>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <input className="backtest-input" type="number" min={1} max={50} value={engineStopLossPct} onChange={(event) => setEngineStopLossPct(event.target.value)} />
              <input className="backtest-input" type="number" min={1} max={100} value={engineTakeProfitPct} onChange={(event) => setEngineTakeProfitPct(event.target.value)} />
            </div>
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>최대 보유일</span>
            <input className="backtest-input" type="number" min={1} max={180} value={engineMaxHoldingDays} onChange={(event) => setEngineMaxHoldingDays(event.target.value)} />
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>일일 매수/매도 제한</span>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <input className="backtest-input" type="number" min={1} max={200} value={engineDailyBuyLimit} onChange={(event) => setEngineDailyBuyLimit(event.target.value)} />
              <input className="backtest-input" type="number" min={1} max={200} value={engineDailySellLimit} onChange={(event) => setEngineDailySellLimit(event.target.value)} />
            </div>
          </label>
          <label style={{ display: 'grid', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>종목별 일 최대 주문</span>
            <input className="backtest-input" type="number" min={1} max={10} value={engineMaxOrdersPerSymbol} onChange={(event) => setEngineMaxOrdersPerSymbol(event.target.value)} />
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 24 }}>
            <input type="checkbox" checked={autoIncludeNeutral} onChange={(event) => setAutoIncludeNeutral(event.target.checked)} />
            <span style={{ fontSize: 12, color: 'var(--text-3)' }}>추천 없으면 중립도 포함</span>
          </label>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button className="ghost-button" style={{ background: 'var(--accent)', color: '#fffaf2', borderColor: 'var(--accent)' }} onClick={handleStartEngine}>
            자동매매 엔진 시작
          </button>
          <button className="ghost-button" onClick={handleStopEngine}>자동매매 엔진 중지</button>
          <button className="ghost-button" onClick={() => refreshEngineStatus()}>엔진 상태 새로고침</button>
          <button className="ghost-button" onClick={handleAutoInvest}>1회 자동매수 실행</button>
        </div>
      </div>

      {(statusMessage || lastError) && (
        <div className="page-section" style={{ fontSize: 13, color: lastError ? 'var(--down)' : 'var(--text-2)' }}>
          {lastError || statusMessage}
        </div>
      )}

      <div className="page-section" style={{ display: 'grid', gap: 12 }}>
        <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-1)' }}>포지션</div>
        {account.positions.length === 0 && <div style={{ color: 'var(--text-4)', fontSize: 13 }}>보유 포지션이 없습니다.</div>}
        {account.positions.length > 0 && (
          <div style={{ display: 'grid', gap: 8 }}>
            {account.positions.map((position) => (
              <div key={`${position.market}-${position.code}`} style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 10, padding: '12px 14px', border: '1px solid var(--border)', borderRadius: 14, background: 'var(--bg-soft)' }}>
                <div>
                  <div style={{ fontWeight: 700, color: 'var(--text-1)' }}>{position.name}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-4)', marginTop: 4 }}>{position.code} · {position.market} · {position.quantity}주</div>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                  <div>평균가 {position.currency === 'USD' ? formatUsd(position.avg_price_local) : formatKrw(position.avg_price_local)}</div>
                  <div style={{ marginTop: 4 }}>현재가 {position.currency === 'USD' ? formatUsd(position.last_price_local) : formatKrw(position.last_price_local)}</div>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                  <div>평가액 {formatKrw(position.market_value_krw)}</div>
                  <div style={{ marginTop: 4 }}>환율 {position.fx_rate.toFixed(2)}</div>
                </div>
                <div style={{ fontSize: 12, color: position.unrealized_pnl_krw >= 0 ? 'var(--up)' : 'var(--down)' }}>
                  <div>{formatKrw(position.unrealized_pnl_krw)}</div>
                  <div style={{ marginTop: 4 }}>{formatSignedPct(position.unrealized_pnl_pct)}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
