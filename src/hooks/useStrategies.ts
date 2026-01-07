import { useState, useEffect, useCallback } from 'react';
import { strategyEvents, StrategyEvent } from '@/lib/strategy-events';

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
  ma_periods: number[];   // Specific MA periods to display (e.g., [50, 200])
}

interface UseStrategiesResult {
  strategies: StrategyConfig[];         // Active (non-archived) strategies
  archivedStrategies: StrategyConfig[]; // Archived strategies
  allStrategies: StrategyConfig[];      // All strategies
  isLoading: boolean;
  error: string | null;
  archiveStrategy: (name: string) => Promise<void>;
  unarchiveStrategy: (name: string) => Promise<void>;
  deleteStrategy: (name: string) => Promise<void>;
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

  // Subscribe to strategy events to stay in sync with other components
  useEffect(() => {
    const unsubscribe = strategyEvents.subscribe((event: StrategyEvent) => {
      if (event.type === 'archive') {
        setAllStrategies(prev =>
          prev.map(s => s.name === event.strategyName ? { ...s, is_archived: true } : s)
        );
      } else if (event.type === 'unarchive') {
        setAllStrategies(prev =>
          prev.map(s => s.name === event.strategyName ? { ...s, is_archived: false } : s)
        );
      } else if (event.type === 'create' || event.type === 'delete') {
        // For create/delete, we need to refetch
        fetchStrategies();
      }
    });
    return unsubscribe;
  }, [fetchStrategies]);

  const archiveStrategy = useCallback(async (name: string) => {
    try {
      const response = await fetch(`${API_URL}/strategies/${name}/archive`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error(`Failed to archive strategy: ${response.status}`);
      }
      // Notify other components (they will do optimistic update)
      strategyEvents.emit({ type: 'archive', strategyName: name });
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
      // Notify other components (they will do optimistic update)
      strategyEvents.emit({ type: 'unarchive', strategyName: name });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to unarchive strategy');
      // Refetch to get correct state
      await fetchStrategies();
    }
  }, [fetchStrategies]);

  const deleteStrategy = useCallback(async (name: string) => {
    try {
      const response = await fetch(`${API_URL}/strategies/${name}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        throw new Error(`Failed to delete strategy: ${response.status}`);
      }
      // Notify other components
      strategyEvents.emit({ type: 'delete', strategyName: name });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete strategy');
      // Refetch to get correct state
      await fetchStrategies();
    }
  }, [fetchStrategies]);

  // Separate active and archived strategies, sorted alphabetically by display_name
  const sortByDisplayName = (a: StrategyConfig, b: StrategyConfig) =>
    a.display_name.localeCompare(b.display_name);

  const strategies = allStrategies.filter(s => !s.is_archived).sort(sortByDisplayName);
  const archivedStrategies = allStrategies.filter(s => s.is_archived).sort(sortByDisplayName);

  return {
    strategies,
    archivedStrategies,
    allStrategies: [...allStrategies].sort(sortByDisplayName),
    isLoading,
    error,
    archiveStrategy,
    unarchiveStrategy,
    deleteStrategy,
    refetch: fetchStrategies,
  };
}
