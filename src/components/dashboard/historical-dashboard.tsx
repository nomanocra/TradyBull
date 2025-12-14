'use client';

import { useState, useMemo, useEffect } from 'react';
import { MemoizedCandlestickChart } from '@/components/chart/candlestick-chart';
import { CandleData } from '@/types/market';

const API_URL = 'http://localhost:8000/api/backtest/data';

interface HistoricalDashboardProps {
  pageName?: string;
  showBollinger?: boolean;
  showMACD?: boolean;
  showIchimoku?: boolean;
  showMovingAverages?: boolean;
  showRSI?: boolean;
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

  // Fetch historical data
  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        const response = await fetch(`${API_URL}?limit=50000`);
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
    };

    fetchData();
  }, []);

  // Price info
  const lastPrice = data.length > 0 ? data[data.length - 1].close : null;
  const prevPrice = data.length > 1 ? data[data.length - 2].close : null;
  const priceChange = lastPrice && prevPrice ? ((lastPrice - prevPrice) / prevPrice) * 100 : null;

  // Date range info
  const dateRange = useMemo(() => {
    if (data.length === 0) return null;
    const firstDate = new Date(data[0].time * 1000);
    const lastDate = new Date(data[data.length - 1].time * 1000);
    return {
      from: firstDate.toLocaleDateString('fr-FR'),
      to: lastDate.toLocaleDateString('fr-FR'),
    };
  }, [data]);

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
          {dateRange && (
            <span className="text-[10px] text-gray-600 font-mono">
              {dateRange.from} → {dateRange.to}
            </span>
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
