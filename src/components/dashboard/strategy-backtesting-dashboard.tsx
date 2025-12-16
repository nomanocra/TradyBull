'use client';

import { useMemo } from 'react';
import { MemoizedCandlestickChart } from '@/components/chart/candlestick-chart';
import { DatePicker } from '@/components/ui/date-picker';
import { useHistoricalData } from '@/app/exploration/historical/historical-context';
import { Signal } from '@/types/market';

interface StrategyBacktestingDashboardProps {
  strategyName: string;
  showBollinger?: boolean;
  showMACD?: boolean;
  showIchimoku?: boolean;
  showMovingAverages?: boolean;
  showRSI?: boolean;
  signals: Signal[]; // Signals for 1H chart only
}

export function StrategyBacktestingDashboard({
  strategyName,
  showBollinger = false,
  showMACD = false,
  showIchimoku = false,
  showMovingAverages = false,
  showRSI = false,
  signals,
}: StrategyBacktestingDashboardProps) {
  const {
    data,
    isLoading,
    error,
    dataInfo,
    dateBounds,
    startDate,
    endDate,
    setStartDate,
    setEndDate,
  } = useHistoricalData();

  // Price info - performance over entire period
  const { lastPrice, priceChange } = useMemo(() => {
    const last = data.length > 0 ? data[data.length - 1].close : null;
    const first = data.length > 0 ? data[0].close : null;
    const change = last && first ? ((last - first) / first) * 100 : null;
    return { lastPrice: last, priceChange: change };
  }, [data]);

  // Count signals
  const signalCount = signals.length;

  return (
    <div className="h-full w-full bg-background flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-card">
        {/* Strategy name - Left */}
        <div className="flex-1 flex items-center gap-3">
          <span className="text-xs font-semibold text-[#C59471]">{strategyName}</span>
          {signalCount > 0 && (
            <span className="text-[10px] text-yellow-500 dark:text-yellow-400 font-medium">
              {signalCount} signal{signalCount > 1 ? 's' : ''}
            </span>
          )}
        </div>

        {/* Symbol and price - Center */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">{dataInfo?.symbol || 'NQ=F'}</span>
          {lastPrice && (
            <>
              <span className="text-sm font-mono font-semibold text-foreground">
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
                <span className="text-[9px] text-muted-foreground">Start</span>
                <DatePicker
                  date={startDate}
                  onDateChange={setStartDate}
                  minDate={dateBounds.minDate}
                  maxDate={endDate || dateBounds.maxDate}
                />
              </div>
              <div className="flex items-center gap-1">
                <span className="text-[9px] text-muted-foreground">End</span>
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
            <span className="text-[10px] text-muted-foreground">
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

      {/* Single 1H Chart with signals and navigator */}
      <div className="flex-1 p-2 bg-background min-h-0">
        <MemoizedCandlestickChart
          title="1H - Backtesting"
          timeframe="1h"
          data={data}
          isLoading={isLoading}
          showBollinger={showBollinger}
          showMACD={showMACD}
          showIchimoku={showIchimoku}
          showMovingAverages={showMovingAverages}
          showRSI={showRSI}
          showNavigator={true}
          signals={signals}
        />
      </div>
    </div>
  );
}
