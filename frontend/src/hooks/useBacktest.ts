import { useCallback, useEffect, useState } from 'react';
import type { BacktestData, BacktestQuery } from '../types';

export const DEFAULT_BACKTEST_QUERY: BacktestQuery = {
  market_scope: 'kospi',
  lookback_days: 1095,
  initial_cash: 10_000_000,
  max_positions: 5,
  max_holding_days: 30,
  rsi_min: 45,
  rsi_max: 68,
  volume_ratio_min: 1.2,
  stop_loss_pct: 7,
  take_profit_pct: 18,
};

const BACKTEST_QUERY_STORAGE_KEY = 'backtest_query_v1';

function buildQueryString(query: BacktestQuery) {
  const params = new URLSearchParams();
  params.set('market_scope', query.market_scope);
  params.set('lookback_days', String(query.lookback_days));
  params.set('initial_cash', String(query.initial_cash));
  params.set('max_positions', String(query.max_positions));
  params.set('max_holding_days', String(query.max_holding_days));
  params.set('rsi_min', String(query.rsi_min));
  params.set('rsi_max', String(query.rsi_max));
  params.set('volume_ratio_min', String(query.volume_ratio_min));
  if (query.stop_loss_pct !== null && query.stop_loss_pct !== undefined) {
    params.set('stop_loss_pct', String(query.stop_loss_pct));
  }
  if (query.take_profit_pct !== null && query.take_profit_pct !== undefined) {
    params.set('take_profit_pct', String(query.take_profit_pct));
  }
  return params.toString();
}

function readNumber(value: unknown, fallback: number) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function readNullableNumber(value: unknown, fallback: number | null | undefined) {
  if (value === null) return null;
  return typeof value === 'number' && Number.isFinite(value) ? value : (fallback ?? null);
}

function normalizeBacktestQuery(value: unknown): BacktestQuery {
  const raw = value && typeof value === 'object' ? (value as Partial<BacktestQuery>) : {};
  return {
    market_scope: raw.market_scope === 'nasdaq' ? 'nasdaq' : DEFAULT_BACKTEST_QUERY.market_scope,
    lookback_days: readNumber(raw.lookback_days, DEFAULT_BACKTEST_QUERY.lookback_days),
    initial_cash: readNumber(raw.initial_cash, DEFAULT_BACKTEST_QUERY.initial_cash),
    max_positions: readNumber(raw.max_positions, DEFAULT_BACKTEST_QUERY.max_positions),
    max_holding_days: readNumber(raw.max_holding_days, DEFAULT_BACKTEST_QUERY.max_holding_days),
    rsi_min: readNumber(raw.rsi_min, DEFAULT_BACKTEST_QUERY.rsi_min),
    rsi_max: readNumber(raw.rsi_max, DEFAULT_BACKTEST_QUERY.rsi_max),
    volume_ratio_min: readNumber(raw.volume_ratio_min, DEFAULT_BACKTEST_QUERY.volume_ratio_min),
    stop_loss_pct: readNullableNumber(raw.stop_loss_pct, DEFAULT_BACKTEST_QUERY.stop_loss_pct),
    take_profit_pct: readNullableNumber(raw.take_profit_pct, DEFAULT_BACKTEST_QUERY.take_profit_pct),
  };
}

export function loadBacktestQuery() {
  try {
    return normalizeBacktestQuery(JSON.parse(localStorage.getItem(BACKTEST_QUERY_STORAGE_KEY) || 'null'));
  } catch {
    return { ...DEFAULT_BACKTEST_QUERY };
  }
}

export function saveBacktestQuery(query: BacktestQuery) {
  localStorage.setItem(BACKTEST_QUERY_STORAGE_KEY, JSON.stringify(query));
}

export function useBacktest(initialQuery: BacktestQuery = DEFAULT_BACKTEST_QUERY) {
  const [query, setQuery] = useState<BacktestQuery>(initialQuery);
  const [data, setData] = useState<BacktestData>({});
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading');

  const run = useCallback(async (nextQuery: BacktestQuery) => {
    setStatus('loading');
    try {
      const res = await fetch(`/api/backtest/run?${buildQueryString(nextQuery)}`, { cache: 'no-store' });
      const payload: BacktestData = await res.json();
      setData(payload);
      setQuery(nextQuery);
      setStatus(payload.error ? 'error' : 'ok');
    } catch {
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    run(initialQuery);
  }, [initialQuery, run]);

  return { data, query, status, run, setQuery };
}
