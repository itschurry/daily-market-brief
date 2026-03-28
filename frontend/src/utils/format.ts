import { UI_TEXT } from '../constants/uiText';
import { COMPANY_CATALOG } from '../data/companyCatalog';

const KRW_DECIMAL_FMT = new Intl.NumberFormat('ko-KR', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const NAME_BY_CODE = new Map<string, string>();
for (const entry of COMPANY_CATALOG) {
  if (!entry.code) continue;
  NAME_BY_CODE.set(entry.code.toUpperCase(), entry.name);
}

const WARNED_SYMBOL_CODES = new Set<string>();

export function formatNumber(value: number | string | null | undefined, decimals = 0): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '-';
  return numeric.toLocaleString('ko-KR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatPercent(value: number | null | undefined, decimals = 2, ratio = false): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '-';
  const pctValue = ratio ? value * 100 : value;
  return `${formatNumber(pctValue, decimals)}%`;
}

export function formatKRW(value: number | null | undefined, withSuffix = false): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '-';
  const body = KRW_DECIMAL_FMT.format(value);
  return withSuffix ? `${body}원` : body;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  const dd = String(date.getDate()).padStart(2, '0');
  const hh = String(date.getHours()).padStart(2, '0');
  const mi = String(date.getMinutes()).padStart(2, '0');
  const ss = String(date.getSeconds()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}`;
}

function resolveSymbolName(code?: string, payloadName?: string): string {
  const normalizedCode = String(code || '').toUpperCase().trim();
  const normalizedPayloadName = String(payloadName || '').trim();
  if (normalizedPayloadName) return normalizedPayloadName;
  if (!normalizedCode) return '';
  const mapped = NAME_BY_CODE.get(normalizedCode);
  if (mapped) return mapped;
  if (!WARNED_SYMBOL_CODES.has(normalizedCode)) {
    WARNED_SYMBOL_CODES.add(normalizedCode);
    console.warn(UI_TEXT.errors.symbolNameMissing, { code: normalizedCode });
  }
  return '';
}

export function formatSymbol(code?: string, name?: string): string {
  const normalizedCode = String(code || '').toUpperCase().trim();
  const resolvedName = resolveSymbolName(normalizedCode, name);
  if (normalizedCode && resolvedName) return `${normalizedCode} ${resolvedName}`;
  if (normalizedCode) return normalizedCode;
  if (resolvedName) return resolvedName;
  return '-';
}
