import { useState, useEffect, useCallback } from 'react';
import api from '../lib/api';
import { SavingsHistoryResponse } from '../types';

export type SavingsHistoryDays = 30 | 90 | 0;

interface UseSavingsHistoryResult {
  data: SavingsHistoryResponse | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export const useSavingsHistory = (days: SavingsHistoryDays): UseSavingsHistoryResult => {
  const [data, setData] = useState<SavingsHistoryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.get<SavingsHistoryResponse>('/api/savings/history', {
        params: { days },
      });
      setData(response.data);
    } catch (err) {
      console.error('Failed to fetch savings history:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to load savings history';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return {
    data,
    loading,
    error,
    refetch: fetchHistory,
  };
};
