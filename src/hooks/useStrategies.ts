import { useState, useEffect } from 'react';

const API_URL = 'http://localhost:8000/api';

export interface StrategyConfig {
  name: string;           // Slug (e.g., 'bollinger-nosl')
  display_name: string;   // Human-readable name (e.g., 'Bollinger NoSL')
  description: string;    // Strategy description for tooltip
  show_bollinger: boolean;
  show_macd: boolean;
  show_ichimoku: boolean;
  show_moving_averages: boolean;
  show_rsi: boolean;
}

interface UseStrategiesResult {
  strategies: StrategyConfig[];
  isLoading: boolean;
  error: string | null;
}

/**
 * Hook to fetch available strategies from the backend API.
 * Returns strategy metadata for dynamic page generation.
 */
export function useStrategies(): UseStrategiesResult {
  const [strategies, setStrategies] = useState<StrategyConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchStrategies() {
      try {
        setIsLoading(true);
        setError(null);

        const response = await fetch(`${API_URL}/signals/strategies`);
        if (!response.ok) {
          throw new Error(`Failed to fetch strategies: ${response.status}`);
        }

        const data = await response.json();

        if (!cancelled) {
          setStrategies(data.strategies || []);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load strategies');
          setStrategies([]);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    fetchStrategies();

    return () => {
      cancelled = true;
    };
  }, []);

  return {
    strategies,
    isLoading,
    error,
  };
}
