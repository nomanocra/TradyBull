import { useState, useEffect, useCallback } from 'react';

export interface DataSource {
  source: string;
  count: number;
  start_date: string;
  end_date: string;
  days_coverage: number;
  years_coverage: number;
}

interface UseDataSourcesResult {
  dataSources: DataSource[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useDataSources(): UseDataSourcesResult {
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDataSources = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await fetch('http://localhost:8000/api/backtest/sources');
      if (!response.ok) {
        throw new Error('Failed to fetch data sources');
      }
      const data = await response.json();
      setDataSources(data.sources || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data sources');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDataSources();
  }, [fetchDataSources]);

  return {
    dataSources,
    isLoading,
    error,
    refetch: fetchDataSources,
  };
}
