import { useState, useEffect, useCallback } from 'react';
import { strategyEvents, StrategyEvent } from '@/lib/strategy-events';

const API_URL = 'http://localhost:8000/api';

export interface KPIs {
  total_return_pct: number;
  avg_yearly_return_pct?: number;
  win_rate_pct: number;
  profit_factor: number;
  max_drawdown_pct: number;
  num_trades: number;
  avg_return_per_trade_pct: number;
  avg_trade_duration_hours: number;
  max_trade_duration_hours: number;
  score: number;
}

interface UseKPIsOptions {
  strategy: string;
  startTs?: number;
  endTs?: number;
  enabled?: boolean;
}

interface UseKPIsResult {
  kpis: KPIs | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch KPIs for a strategy from the backend API.
 */
export function useKPIs({
  strategy,
  startTs,
  endTs,
  enabled = true,
}: UseKPIsOptions): UseKPIsResult {
  const [kpis, setKPIs] = useState<KPIs | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchKPIs = useCallback(async () => {
    if (!enabled || !strategy) return;

    try {
      setIsLoading(true);
      setError(null);

      let url = `${API_URL}/kpis?strategy=${encodeURIComponent(strategy)}`;
      if (startTs) url += `&start=${startTs}`;
      if (endTs) url += `&end=${endTs}`;

      const response = await fetch(url);
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || `Failed to fetch KPIs: ${response.status}`);
      }

      const data = await response.json();
      setKPIs(data.kpis || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load KPIs');
      setKPIs(null);
    } finally {
      setIsLoading(false);
    }
  }, [strategy, startTs, endTs, enabled]);

  useEffect(() => {
    fetchKPIs();
  }, [fetchKPIs]);

  return {
    kpis,
    isLoading,
    error,
    refetch: fetchKPIs,
  };
}

// Types for all strategies KPIs
export interface StrategyKPIData {
  strategy: string;
  display_name: string;
  kpis: KPIs;
  signal_count: number;
  is_archived: boolean;
}

interface UseAllKPIsOptions {
  startTs?: number;
  endTs?: number;
  enabled?: boolean;
}

interface UseAllKPIsResult {
  data: StrategyKPIData[];
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  updateStrategyArchived: (strategyName: string, isArchived: boolean) => void;
}

/**
 * Hook to fetch KPIs for all strategies from the backend API.
 */
export function useAllKPIs({
  startTs,
  endTs,
  enabled = true,
}: UseAllKPIsOptions = {}): UseAllKPIsResult {
  const [data, setData] = useState<StrategyKPIData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAllKPIs = useCallback(async () => {
    if (!enabled) return;

    try {
      setIsLoading(true);
      setError(null);

      let url = `${API_URL}/kpis/all`;
      const params: string[] = [];
      if (startTs) params.push(`start=${startTs}`);
      if (endTs) params.push(`end=${endTs}`);
      if (params.length > 0) url += `?${params.join('&')}`;

      const response = await fetch(url);
      if (!response.ok) {
        const respData = await response.json().catch(() => ({}));
        throw new Error(respData.detail || `Failed to fetch KPIs: ${response.status}`);
      }

      const respData = await response.json();
      setData(respData.strategies || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load KPIs');
      setData([]);
    } finally {
      setIsLoading(false);
    }
  }, [startTs, endTs, enabled]);

  useEffect(() => {
    fetchAllKPIs();
  }, [fetchAllKPIs]);

  // Subscribe to strategy events to stay in sync with sidebar
  useEffect(() => {
    const unsubscribe = strategyEvents.subscribe((event: StrategyEvent) => {
      if (event.type === 'archive') {
        setData(prev =>
          prev.map(item => item.strategy === event.strategyName ? { ...item, is_archived: true } : item)
        );
      } else if (event.type === 'unarchive') {
        setData(prev =>
          prev.map(item => item.strategy === event.strategyName ? { ...item, is_archived: false } : item)
        );
      } else if (event.type === 'create' || event.type === 'delete') {
        // For create/delete, we need to refetch
        fetchAllKPIs();
      }
    });
    return unsubscribe;
  }, [fetchAllKPIs]);

  // Optimistically update a strategy's archived status without refetching
  const updateStrategyArchived = useCallback((strategyName: string, isArchived: boolean) => {
    setData(prevData =>
      prevData.map(item =>
        item.strategy === strategyName
          ? { ...item, is_archived: isArchived }
          : item
      )
    );
  }, []);

  return {
    data,
    isLoading,
    error,
    refetch: fetchAllKPIs,
    updateStrategyArchived,
  };
}
