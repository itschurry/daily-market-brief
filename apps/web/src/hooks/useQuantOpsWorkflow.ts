import { useCallback, useEffect, useState } from 'react';
import {
  applyQuantOpsRuntime,
  fetchQuantOpsWorkflow,
  revalidateQuantOpsCandidate,
  saveQuantOpsCandidate,
} from '../api/domain';
import type { QuantOpsActionResponse, QuantOpsWorkflowResponse } from '../types/domain';
import type { BacktestQuery } from '../types';
import type { ValidationSettings } from './useValidationSettingsStore';

export type QuantOpsBusyAction = 'refresh' | 'revalidate' | 'save' | 'apply' | null;

export function useQuantOpsWorkflow() {
  const [workflow, setWorkflow] = useState<QuantOpsWorkflowResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<QuantOpsBusyAction>(null);
  const [lastError, setLastError] = useState('');

  const refresh = useCallback(async () => {
    setBusyAction('refresh');
    setLastError('');
    try {
      const payload = await fetchQuantOpsWorkflow();
      setWorkflow(payload);
      return payload;
    } catch {
      setLastError('quant ops workflow 상태를 불러오지 못했습니다.');
      return null;
    } finally {
      setLoading(false);
      setBusyAction(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleActionResponse = useCallback((response: { ok: boolean; data: QuantOpsActionResponse }) => {
    if (response.data.workflow) {
      setWorkflow(response.data.workflow);
    }
    if (!response.ok || !response.data.ok) {
      setLastError(response.data.error || 'quant ops workflow 작업이 실패했습니다.');
    } else {
      setLastError('');
    }
    return response.data;
  }, []);

  const revalidate = useCallback(async (query: BacktestQuery, settings: ValidationSettings) => {
    setBusyAction('revalidate');
    try {
      const response = await revalidateQuantOpsCandidate(query, settings);
      return handleActionResponse(response);
    } finally {
      setBusyAction(null);
    }
  }, [handleActionResponse]);

  const saveCandidate = useCallback(async (candidateId?: string, note?: string) => {
    setBusyAction('save');
    try {
      const response = await saveQuantOpsCandidate(candidateId, note);
      return handleActionResponse(response);
    } finally {
      setBusyAction(null);
    }
  }, [handleActionResponse]);

  const applyRuntime = useCallback(async (candidateId?: string) => {
    setBusyAction('apply');
    try {
      const response = await applyQuantOpsRuntime(candidateId);
      return handleActionResponse(response);
    } finally {
      setBusyAction(null);
    }
  }, [handleActionResponse]);

  return {
    workflow,
    loading,
    busyAction,
    lastError,
    refresh,
    revalidate,
    saveCandidate,
    applyRuntime,
  };
}
