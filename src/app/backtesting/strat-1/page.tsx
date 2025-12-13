'use client';

import { useEffect, useState } from 'react';
import { CandlestickChart } from '@/components/chart/candlestick-chart';
import { CandleData } from '@/types/market';

interface BacktestInfo {
  symbol: string;
  interval: string;
  count: number;
  start_date: string;
  end_date: string;
  days_coverage: number;
}

export default function Strat1Page() {
  const [data, setData] = useState<CandleData[]>([]);
  const [info, setInfo] = useState<BacktestInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchBacktestData() {
      try {
        // Fetch info first
        const infoRes = await fetch('http://localhost:8000/api/backtest/info');
        if (!infoRes.ok) throw new Error('Failed to fetch backtest info');
        const infoData = await infoRes.json();
        setInfo(infoData);

        // Fetch all data (limit high enough for all candles)
        const dataRes = await fetch('http://localhost:8000/api/backtest/data?limit=50000');
        if (!dataRes.ok) throw new Error('Failed to fetch backtest data');
        const result = await dataRes.json();

        setData(result.data);
        setIsLoading(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setIsLoading(false);
      }
    }

    fetchBacktestData();
  }, []);

  if (error) {
    return (
      <div className="h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="text-red-500 text-sm">Erreur: {error}</div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-[#0a0a0a] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[#1a1a1a]">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-bold text-white">Strat 1</h1>
          <span className="text-xs text-gray-500">Backtesting</span>
        </div>
        {info && (
          <div className="flex items-center gap-4 text-xs text-gray-400">
            <span>{info.count.toLocaleString()} bougies</span>
            <span>{info.start_date} → {info.end_date}</span>
            <span>{info.days_coverage} jours</span>
          </div>
        )}
      </div>

      {/* Chart */}
      <div className="flex-1 min-h-0">
        <CandlestickChart
          title="NQ=F 1H"
          timeframe="1h"
          data={data}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
