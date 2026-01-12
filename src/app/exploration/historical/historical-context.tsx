'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { CandleData } from '@/types/market';

const API_URL = 'http://localhost:8000/api/backtest';

interface DateBounds {
  minDate: Date;
  maxDate: Date;
}

interface ZoomState {
  fromPercent: number; // 0-1, percentage of data range
  toPercent: number;   // 0-1, percentage of data range
}

interface HistoricalContextValue {
  data: CandleData[];
  isLoading: boolean;
  error: string | null;
  dataInfo: { count: number; symbol: string } | null;
  dateBounds: DateBounds | null;
  startDate: Date | undefined;
  endDate: Date | undefined;
  setStartDate: (date: Date | undefined) => void;
  setEndDate: (date: Date | undefined) => void;
  zoomState: ZoomState;
  setZoomState: (state: ZoomState) => void;
}

const HistoricalContext = createContext<HistoricalContextValue | null>(null);

export function useHistoricalData() {
  const context = useContext(HistoricalContext);
  if (!context) {
    throw new Error('useHistoricalData must be used within HistoricalProvider');
  }
  return context;
}

interface HistoricalProviderProps {
  children: ReactNode;
}

// Default zoom: show last 20% of data (most recent)
const DEFAULT_ZOOM: ZoomState = { fromPercent: 0.8, toPercent: 1 };

export function HistoricalProvider({ children }: HistoricalProviderProps) {
  const [data, setData] = useState<CandleData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dataInfo, setDataInfo] = useState<{ count: number; symbol: string } | null>(null);

  const [dateBounds, setDateBounds] = useState<DateBounds | null>(null);
  const [startDate, setStartDate] = useState<Date | undefined>();
  const [endDate, setEndDate] = useState<Date | undefined>();
  const [zoomState, setZoomState] = useState<ZoomState>(DEFAULT_ZOOM);

  // Fetch available date bounds
  useEffect(() => {
    const fetchBounds = async () => {
      try {
        const response = await fetch(`${API_URL}/info`);
        if (!response.ok) throw new Error('Failed to fetch data info');
        const info = await response.json();

        if (info.count > 0) {
          const minDate = new Date(info.start_timestamp * 1000);
          const maxDate = new Date(info.end_timestamp * 1000);
          setDateBounds({ minDate, maxDate });
          setStartDate(minDate);
          setEndDate(maxDate);
        }
      } catch (err) {
        console.error('Failed to fetch date bounds:', err);
      }
    };

    fetchBounds();
  }, []);

  // Fetch historical data when dates change
  const fetchData = useCallback(async (showLoading = true) => {
    if (!startDate || !endDate) return;

    try {
      if (showLoading) setIsLoading(true);
      const startTs = Math.floor(startDate.getTime() / 1000);
      const endDateEod = new Date(endDate);
      endDateEod.setHours(23, 59, 59, 999);
      const endTs = Math.floor(endDateEod.getTime() / 1000);

      const response = await fetch(`${API_URL}/data?start=${startTs}&end=${endTs}&limit=50000`);
      if (!response.ok) {
        throw new Error('Failed to fetch backtest data');
      }
      const result = await response.json();
      setData(result.data || []);
      setDataInfo({ count: result.count, symbol: result.symbol });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      if (showLoading) setIsLoading(false);
    }
  }, [startDate, endDate]);

  // Initial fetch and polling every 10 seconds
  useEffect(() => {
    fetchData(true); // Initial fetch with loading state

    const intervalId = setInterval(() => {
      fetchData(false); // Polling without loading state
    }, 10000);

    return () => clearInterval(intervalId);
  }, [fetchData]);

  const value: HistoricalContextValue = {
    data,
    isLoading,
    error,
    dataInfo,
    dateBounds,
    startDate,
    endDate,
    setStartDate,
    setEndDate,
    zoomState,
    setZoomState,
  };

  return (
    <HistoricalContext.Provider value={value}>
      {children}
    </HistoricalContext.Provider>
  );
}
