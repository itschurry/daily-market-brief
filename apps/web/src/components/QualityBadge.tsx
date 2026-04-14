import type { ReactNode } from 'react';
import { freshnessToKorean, gradeToKorean } from '../constants/uiText';

export function freshnessBadgeMeta(value: string | null | undefined): { label: string; className: string } {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'fresh') return { label: freshnessToKorean(normalized), className: 'inline-badge is-success' };
  if (normalized === 'stale') return { label: freshnessToKorean(normalized), className: 'inline-badge is-danger' };
  if (normalized === 'invalid') return { label: freshnessToKorean(normalized), className: 'inline-badge is-danger' };
  if (normalized === 'missing') return { label: freshnessToKorean(normalized), className: 'inline-badge' };
  if (normalized === 'derived') return { label: freshnessToKorean(normalized), className: 'inline-badge' };
  return { label: freshnessToKorean(normalized), className: 'inline-badge' };
}

export function gradeBadgeMeta(value: string | null | undefined): { label: string; className: string } {
  const normalized = String(value || '').trim().toUpperCase();
  if (normalized === 'A') return { label: gradeToKorean(normalized), className: 'inline-badge is-success' };
  if (normalized === 'B') return { label: gradeToKorean(normalized), className: 'inline-badge' };
  if (normalized === 'C') return { label: gradeToKorean(normalized), className: 'inline-badge is-danger' };
  if (normalized === 'D') return { label: gradeToKorean(normalized), className: 'inline-badge is-danger' };
  return { label: gradeToKorean(normalized), className: 'inline-badge' };
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
