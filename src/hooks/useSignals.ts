import { useState, useEffect, useCallback } from 'react';
import { Signal } from '@/types/market';

const API_URL = 'http://localhost:8000/api';

interface UseSignalsOptions {
  strategy: string;
  startTs?: number;
  endTs?: number;
  enabled?: boolean;
}

interface UseSignalsResult {
  signals: Signal[];
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch trading signals from the backend API.
 * Used for backtesting pages where signals are pre-calculated and stored in database.
 *
 * @param strategy - Strategy name (e.g., 'bollinger-nosl')
 * @param startTs - Optional start timestamp (Unix seconds)
 * @param endTs - Optional end timestamp (Unix seconds)
 * @param enabled - Whether to enable fetching (default: true)
 */
export function useSignals({
  strategy,
  startTs,
  endTs,
  enabled = true,
}: UseSignalsOptions): UseSignalsResult {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSignals = useCallback(async (showLoading = true) => {
    if (!enabled || !strategy) return;

    try {
      if (showLoading) setIsLoading(true);
      setError(null);

      let url = `${API_URL}/signals?strategy=${encodeURIComponent(strategy)}`;
      if (startTs) url += `&start=${startTs}`;
      if (endTs) url += `&end=${endTs}`;

      const response = await fetch(url);
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || `Failed to fetch signals: ${response.status}`);
      }

      const data = await response.json();

      // Transform API response to Signal type
      const transformedSignals: Signal[] = (data.signals || []).map((s: {
        time: number;
        type: 'buy' | 'sell';
        price: number;
        label?: string;
      }) => ({
        time: s.time,
        type: s.type,
        price: s.price,
        label: s.label,
      }));

      setSignals(transformedSignals);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load signals');
      setSignals([]);
    } finally {
      if (showLoading) setIsLoading(false);
    }
  }, [strategy, startTs, endTs, enabled]);

  // Initial fetch and polling every 10 seconds
  useEffect(() => {
    fetchSignals(true); // Initial fetch with loading state

    const intervalId = setInterval(() => {
      fetchSignals(false); // Polling without loading state
    }, 10000);

    return () => clearInterval(intervalId);
  }, [fetchSignals]);

  return {
    signals,
    isLoading,
    error,
    refetch: fetchSignals,
  };
}
