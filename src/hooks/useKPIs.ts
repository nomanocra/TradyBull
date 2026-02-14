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
  // Yearly performance metrics
  yearly_returns_std_pct: number;
  best_year_return_pct: number;
  worst_year_return_pct: number;
  best_year: number;
  worst_year: number;
}

interface UseKPIsOptions {
  strategy: string;
  startTs?: number;
  endTs?: number;
  enabled?: boolean;
  dataSource?: string;
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
  dataSource,
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
      if (dataSource) url += `&data_source=${encodeURIComponent(dataSource)}`;

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
  }, [strategy, startTs, endTs, enabled, dataSource]);

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
  dataSource?: string;
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
 * Loads non-archived strategies first (fast), then archived ones in background.
 */
export function useAllKPIs({
  startTs,
  endTs,
  enabled = true,
  dataSource,
}: UseAllKPIsOptions = {}): UseAllKPIsResult {
  const [data, setData] = useState<StrategyKPIData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAllKPIs = useCallback(async () => {
    if (!enabled) return;

    try {
      setIsLoading(true);
      setError(null);

      // Build base params
      const baseParams: string[] = [];
      if (startTs) baseParams.push(`start=${startTs}`);
      if (endTs) baseParams.push(`end=${endTs}`);
      if (dataSource) baseParams.push(`data_source=${encodeURIComponent(dataSource)}`);

      // First, fetch non-archived strategies (fast)
      const activeParams = [...baseParams, 'include_archived=false'];
      const activeUrl = `${API_URL}/kpis/all?${activeParams.join('&')}`;

      const activeResponse = await fetch(activeUrl);
      if (!activeResponse.ok) {
        const respData = await activeResponse.json().catch(() => ({}));
        throw new Error(respData.detail || `Failed to fetch KPIs: ${activeResponse.status}`);
      }

      const activeData = await activeResponse.json();
      setData(activeData.strategies || []);
      setIsLoading(false);

      // Then, fetch archived strategies in background and merge
      const archivedParams = [...baseParams, 'include_archived=true'];
      const archivedUrl = `${API_URL}/kpis/all?${archivedParams.join('&')}`;

      const archivedResponse = await fetch(archivedUrl);
      if (archivedResponse.ok) {
        const archivedData = await archivedResponse.json();
        setData(archivedData.strategies || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load KPIs');
      setData([]);
      setIsLoading(false);
    }
  }, [startTs, endTs, enabled, dataSource]);

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
      } else if (event.type === 'delete') {
        // Optimistic removal - remove from local state immediately
        setData(prev => prev.filter(item => item.strategy !== event.strategyName));
      } else if (event.type === 'create') {
        // For create, we need to refetch
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
