import type { ReactNode } from 'react';

export function freshnessBadgeMeta(value: string | null | undefined): { label: string; className: string } {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'fresh') return { label: 'fresh', className: 'inline-badge is-success' };
  if (normalized === 'stale') return { label: 'stale', className: 'inline-badge is-danger' };
  if (normalized === 'invalid') return { label: 'invalid', className: 'inline-badge is-danger' };
  if (normalized === 'missing') return { label: 'missing', className: 'inline-badge' };
  if (normalized === 'derived') return { label: 'derived', className: 'inline-badge' };
  return { label: normalized || 'unknown', className: 'inline-badge' };
}

export function gradeBadgeMeta(value: string | null | undefined): { label: string; className: string } {
  const normalized = String(value || '').trim().toUpperCase();
  if (normalized === 'A') return { label: 'Grade A', className: 'inline-badge is-success' };
  if (normalized === 'B') return { label: 'Grade B', className: 'inline-badge' };
  if (normalized === 'C') return { label: 'Grade C', className: 'inline-badge is-danger' };
  if (normalized === 'D') return { label: 'Grade D', className: 'inline-badge is-danger' };
  return { label: 'Grade -', className: 'inline-badge' };
}

interface QualityBadgeProps {
  value: string | null | undefined;
  kind: 'freshness' | 'grade';
  children?: ReactNode;
}

export function QualityBadge({ value, kind, children }: QualityBadgeProps) {
  const meta = kind === 'freshness' ? freshnessBadgeMeta(value) : gradeBadgeMeta(value);
  return <span className={meta.className}>{children ?? meta.label}</span>;
}

export function FreshnessBadge({ value, children }: Omit<QualityBadgeProps, 'kind'>) {
  return <QualityBadge value={value} kind="freshness">{children}</QualityBadge>;
}

export function GradeBadge({ value, children }: Omit<QualityBadgeProps, 'kind'>) {
  return <QualityBadge value={value} kind="grade">{children}</QualityBadge>;
}
