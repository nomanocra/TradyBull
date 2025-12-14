import { useState, useEffect, useCallback } from 'react';

const API_URL = 'http://localhost:8000/api/signals';

export interface Signal {
  indicator: string;
  signal_type: 'buy' | 'sell';
  timestamp: number;
  candle_timestamp: number;
  price: number;
  is_major: boolean;
}

interface UseSignalsOptions {
  indicator?: string;
  enabled?: boolean;
  start?: number;
  end?: number;
}

interface UseSignalsResult {
  signals: Signal[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useSignals(options: UseSignalsOptions = {}): UseSignalsResult {
  const { indicator = 'all', enabled = true, start, end } = options;
  const [signals, setSignals] = useState<Signal[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSignals = useCallback(async () => {
    if (!enabled) {
      setSignals([]);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set('indicator', indicator);
      if (start) params.set('start', String(start));
      if (end) params.set('end', String(end));

      const response = await fetch(`${API_URL}?${params}`);
      if (!response.ok) {
        throw new Error('Failed to fetch signals');
      }

      const data = await response.json();
      setSignals(data.signals || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load signals');
      setSignals([]);
    } finally {
      setIsLoading(false);
    }
  }, [indicator, enabled, start, end]);

  useEffect(() => {
    fetchSignals();
  }, [fetchSignals]);

  return { signals, isLoading, error, refetch: fetchSignals };
}
