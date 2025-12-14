'use client';

import { useState, useEffect, useCallback } from 'react';
import { MemoizedCandlestickChart } from '@/components/chart/candlestick-chart';
import { DatePicker } from '@/components/ui/date-picker';
import { CandleData } from '@/types/market';

const API_URL = 'http://localhost:8000/api/backtest';

interface HistoricalDashboardProps {
  pageName?: string;
  showBollinger?: boolean;
  showMACD?: boolean;
  showIchimoku?: boolean;
  showMovingAverages?: boolean;
  showRSI?: boolean;
}

interface DateBounds {
  minDate: Date;
  maxDate: Date;
}

export function HistoricalDashboard({
  pageName = 'Historical',
  showBollinger = false,
  showMACD = false,
  showIchimoku = false,
  showMovingAverages = false,
  showRSI = false,
}: HistoricalDashboardProps) {
  const [data, setData] = useState<CandleData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dataInfo, setDataInfo] = useState<{ count: number; symbol: string } | null>(null);

  // Date range state
  const [dateBounds, setDateBounds] = useState<DateBounds | null>(null);
  const [startDate, setStartDate] = useState<Date | undefined>();
  const [endDate, setEndDate] = useState<Date | undefined>();

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
          // Initialize with full range
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
  const fetchData = useCallback(async () => {
    if (!startDate || !endDate) return;

    try {
      setIsLoading(true);
      const startTs = Math.floor(startDate.getTime() / 1000);
      // End of day for end date
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
      setIsLoading(false);
    }
  }, [startDate, endDate]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Price info (based on filtered data) - performance over entire period
  const lastPrice = data.length > 0 ? data[data.length - 1].close : null;
  const firstPrice = data.length > 0 ? data[0].close : null;
  const priceChange = lastPrice && firstPrice ? ((lastPrice - firstPrice) / firstPrice) * 100 : null;

  return (
    <div className="h-full w-full bg-[#0a0a0a] flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-3 py-1.5 border-b border-[#1a1a1a] bg-[#0d0d0d]">
        {/* Page name - Left */}
        <div className="flex-1 flex items-center gap-3">
          <span className="text-xs font-semibold text-[#C59471]">{pageName}</span>
        </div>

        {/* Symbol and price - Center */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-400">{dataInfo?.symbol || 'NQ=F'}</span>
          {lastPrice && (
            <>
              <span className="text-sm font-mono font-semibold text-white">
                {lastPrice.toFixed(2)}
              </span>
              {priceChange !== null && (
                <span className={`text-xs font-mono ${priceChange >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                  {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}%
                </span>
              )}
            </>
          )}
        </div>

        {/* Data info - Right */}
        <div className="flex-1 flex items-center justify-end gap-3">
          {error && (
            <span className="text-xs text-red-500">{error}</span>
          )}
          {/* Date pickers */}
          {dateBounds && (
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1">
                <span className="text-[9px] text-gray-500">Start</span>
                <DatePicker
                  date={startDate}
                  onDateChange={setStartDate}
                  minDate={dateBounds.minDate}
                  maxDate={endDate || dateBounds.maxDate}
                />
              </div>
              <div className="flex items-center gap-1">
                <span className="text-[9px] text-gray-500">End</span>
                <DatePicker
                  date={endDate}
                  onDateChange={setEndDate}
                  minDate={startDate || dateBounds.minDate}
                  maxDate={dateBounds.maxDate}
                />
              </div>
            </div>
          )}
          {dataInfo && (
            <span className="text-[10px] text-gray-500">
              {dataInfo.count.toLocaleString()} candles
            </span>
          )}
          <div
            className={`w-1.5 h-1.5 rounded-full ${
              error ? 'bg-red-500' :
              isLoading ? 'bg-yellow-500 animate-pulse' :
              'bg-emerald-500'
            }`}
            title={error ? 'Error' : isLoading ? 'Loading...' : 'Data loaded'}
          />
        </div>
      </header>

      {/* Single 1H Chart */}
      <div className="flex-1 p-2 bg-[#0a0a0a] min-h-0">
        <MemoizedCandlestickChart
          title="1H - Historical"
          timeframe="1h"
          data={data}
          isLoading={isLoading}
          showBollinger={showBollinger}
          showMACD={showMACD}
          showIchimoku={showIchimoku}
          showMovingAverages={showMovingAverages}
          showRSI={showRSI}
        />
      </div>
    </div>
  );
}
