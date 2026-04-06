import { resolveSymbolName } from '../utils/format';

interface SymbolIdentityProps {
  code?: string;
  name?: string;
  market?: string;
  align?: 'left' | 'right';
  compact?: boolean;
}

export function SymbolIdentity({ code, name, market, align = 'left', compact = false }: SymbolIdentityProps) {
  const normalizedCode = String(code || '').trim().toUpperCase();
  const resolvedName = resolveSymbolName(normalizedCode, name);
  const marketLabel = String(market || '').trim().toUpperCase();
  const hasResolvedName = Boolean(resolvedName) && resolvedName.toUpperCase() !== normalizedCode;
  const wrapperClass = `symbol-identity ${align === 'right' ? 'is-right' : ''} ${compact ? 'is-compact' : ''}`.trim();
  const primaryLabel = hasResolvedName ? resolvedName : (normalizedCode || '-');
  const secondaryCodeLabel = normalizedCode;
  const secondaryMeta = hasResolvedName
    ? `${secondaryCodeLabel}${marketLabel ? ` · ${marketLabel}` : ''}`
    : (marketLabel || '-');

  return (
    <div className={wrapperClass}>
      <div className="symbol-identity-name">{primaryLabel}</div>
      <div className="symbol-identity-meta">{secondaryMeta}</div>
    </div>
  );
}
