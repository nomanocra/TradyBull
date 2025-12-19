import { useState, useEffect, useCallback } from 'react';

const API_URL = 'http://localhost:8000/api';

export interface KPIs {
  total_return_pct: number;
  win_rate_pct: number;
  profit_factor: number;
  max_drawdown_pct: number;
  num_trades: number;
  avg_return_per_trade_pct: number;
  avg_trade_duration_hours: number;
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
