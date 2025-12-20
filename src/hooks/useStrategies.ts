import { useState, useEffect, useCallback } from 'react';
import { strategyEvents } from '@/lib/strategy-events';

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
  is_archived: boolean;
}

interface UseStrategiesResult {
  strategies: StrategyConfig[];         // Active (non-archived) strategies
  archivedStrategies: StrategyConfig[]; // Archived strategies
  allStrategies: StrategyConfig[];      // All strategies
  isLoading: boolean;
  error: string | null;
  archiveStrategy: (name: string) => Promise<void>;
  unarchiveStrategy: (name: string) => Promise<void>;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch available strategies from the backend API.
 * Returns strategy metadata for dynamic page generation.
 */
export function useStrategies(): UseStrategiesResult {
  const [allStrategies, setAllStrategies] = useState<StrategyConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStrategies = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${API_URL}/signals/strategies`);
      if (!response.ok) {
        throw new Error(`Failed to fetch strategies: ${response.status}`);
      }

      const data = await response.json();
      setAllStrategies(data.strategies || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load strategies');
      setAllStrategies([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  const archiveStrategy = useCallback(async (name: string) => {
    try {
      const response = await fetch(`${API_URL}/strategies/${name}/archive`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error(`Failed to archive strategy: ${response.status}`);
      }
      // Optimistic update
      setAllStrategies(prev =>
        prev.map(s => s.name === name ? { ...s, is_archived: true } : s)
      );
      // Notify other components
      strategyEvents.emit();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to archive strategy');
      // Refetch to get correct state
      await fetchStrategies();
    }
  }, [fetchStrategies]);

  const unarchiveStrategy = useCallback(async (name: string) => {
    try {
      const response = await fetch(`${API_URL}/strategies/${name}/unarchive`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error(`Failed to unarchive strategy: ${response.status}`);
      }
      // Optimistic update
      setAllStrategies(prev =>
        prev.map(s => s.name === name ? { ...s, is_archived: false } : s)
      );
      // Notify other components
      strategyEvents.emit();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to unarchive strategy');
      // Refetch to get correct state
      await fetchStrategies();
    }
  }, [fetchStrategies]);

  // Separate active and archived strategies
  const strategies = allStrategies.filter(s => !s.is_archived);
  const archivedStrategies = allStrategies.filter(s => s.is_archived);

  return {
    strategies,
    archivedStrategies,
    allStrategies,
    isLoading,
    error,
    archiveStrategy,
    unarchiveStrategy,
    refetch: fetchStrategies,
  };
}
