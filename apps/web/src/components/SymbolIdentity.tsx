import { useEffect, useState } from 'react';
import { resolveSymbolName } from '../utils/format';

interface SymbolIdentityProps {
  code?: string;
  name?: string;
  market?: string;
  align?: 'left' | 'right';
  compact?: boolean;
}

const REMOTE_NAME_CACHE = new Map<string, string>();
const REMOTE_NAME_REQUESTS = new Map<string, Promise<string>>();

function cacheKey(code: string, market: string): string {
  return `${market || 'ANY'}:${code}`;
}

function fetchSymbolName(code: string, market: string): Promise<string> {
  const key = cacheKey(code, market);
  const cached = REMOTE_NAME_CACHE.get(key);
  if (cached) return Promise.resolve(cached);

  const pending = REMOTE_NAME_REQUESTS.get(key);
  if (pending) return pending;

  const request = fetch(`/api/stock-search?q=${encodeURIComponent(code)}`, { cache: 'no-store' })
    .then((response) => (response.ok ? response.json() : null))
    .then((payload) => {
      const results = Array.isArray(payload?.results) ? payload.results : [];
      const exactMatch = results.find((item: { code?: string; market?: string; name?: string }) => {
        const itemCode = String(item?.code || '').trim().toUpperCase();
        const itemMarket = String(item?.market || '').trim().toUpperCase();
        return itemCode === code && (!market || !itemMarket || itemMarket === market);
      });
      const fetchedName = String(exactMatch?.name || '').trim();
      const resolved = fetchedName && fetchedName.toUpperCase() !== code ? fetchedName : code;
      REMOTE_NAME_CACHE.set(key, resolved);
      return resolved;
    })
    .catch(() => {
      REMOTE_NAME_CACHE.set(key, code);
      return code;
    })
    .finally(() => {
      REMOTE_NAME_REQUESTS.delete(key);
    });
  REMOTE_NAME_REQUESTS.set(key, request);
  return request;
}

export function SymbolIdentity({ code, name, market, align = 'left', compact = false }: SymbolIdentityProps) {
  const normalizedCode = String(code || '').trim().toUpperCase();
  const marketLabel = String(market || '').trim().toUpperCase();
  const key = cacheKey(normalizedCode, marketLabel);
  const [remoteName, setRemoteName] = useState(() => REMOTE_NAME_CACHE.get(key) || '');
  const resolvedName = resolveSymbolName(normalizedCode, name || remoteName);
  const hasResolvedName = Boolean(resolvedName) && resolvedName.toUpperCase() !== normalizedCode;
  const wrapperClass = `symbol-identity ${align === 'right' ? 'is-right' : ''} ${compact ? 'is-compact' : ''}`.trim();
  const primaryLabel = hasResolvedName ? resolvedName : (normalizedCode || '-');
  const secondaryCodeLabel = normalizedCode;
  const secondaryMeta = hasResolvedName
    ? `${secondaryCodeLabel}${marketLabel ? ` · ${marketLabel}` : ''}`
    : (marketLabel || '-');

  useEffect(() => {
    if (!normalizedCode || hasResolvedName) return;
    const currentKey = cacheKey(normalizedCode, marketLabel);
    const cached = REMOTE_NAME_CACHE.get(currentKey);
    if (cached) {
      setRemoteName(cached);
      return;
    }
    let active = true;
    void fetchSymbolName(normalizedCode, marketLabel).then((fetchedName) => {
      if (active) setRemoteName(fetchedName);
    });
    return () => {
      active = false;
    };
  }, [hasResolvedName, marketLabel, normalizedCode]);

  return (
    <div className={wrapperClass}>
      <div className="symbol-identity-name">{primaryLabel}</div>
      <div className="symbol-identity-meta">{secondaryMeta}</div>
    </div>
  );
}
