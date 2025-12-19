'use client';

import { useMemo } from 'react';
import { Info } from 'lucide-react';
import { MemoizedCandlestickChart } from '@/components/chart/candlestick-chart';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useRealtimeData } from '@/app/exploration/real-time/realtime-context';
import { Signal } from '@/types/market';

const FETCH_INTERVAL = 10;

interface StrategyRealtimeDashboardProps {
  strategyName: string;
  strategyDescription?: string;
  showBollinger?: boolean;
  showMACD?: boolean;
  showIchimoku?: boolean;
  showMovingAverages?: boolean;
  showRSI?: boolean;
  signals: Signal[]; // Signals for 1H chart only
}

export function StrategyRealtimeDashboard({
  strategyName,
  strategyDescription,
  showBollinger = false,
  showMACD = false,
  showIchimoku = false,
  showMovingAverages = false,
  showRSI = false,
  signals,
}: StrategyRealtimeDashboardProps) {
  const {
    data,
    isLoading,
    error,
    lastFetchTime,
    marketOpen,
    standby,
    dataSource,
    countdown,
    isResetting,
    wsConnected,
  } = useRealtimeData();

  // Memoize price calculations to avoid recalculations on every render
  const { lastPrice, priceChange } = useMemo(() => {
    const last = data['1h'].length > 0 ? data['1h'][data['1h'].length - 1].close : null;
    const prev = data['1h'].length > 1 ? data['1h'][data['1h'].length - 2].close : null;
    const change = last && prev ? ((last - prev) / prev) * 100 : null;
    return { lastPrice: last, priceChange: change };
  }, [data]);

  // Get display time
  const { displayTime, displayDate } = useMemo(() => {
    if (data['1h'].length > 0) {
      const lastCandle = data['1h'][data['1h'].length - 1];
      const date = new Date(lastCandle.time * 1000);
      const time = date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

      if (standby) {
        const dateStr = date.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
        return { displayTime: time, displayDate: dateStr };
      }

      return { displayTime: lastFetchTime || time, displayDate: null };
    }
    return { displayTime: lastFetchTime, displayDate: null };
  }, [lastFetchTime, data, standby]);

  return (
    <div className="h-full w-full bg-background flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-card">
        {/* Strategy name - Left */}
        <div className="flex-1 flex items-center gap-2">
          <span className="text-xs font-semibold text-brand">{strategyName}</span>
          {strategyDescription && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" className="inline-flex">
                  <Info className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground cursor-help transition-colors" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-xs text-xs">
                {strategyDescription}
              </TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* Symbol and price - Center */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">{dataSource || 'NASDAQ'}</span>
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

        {/* Status indicators - Right */}
        <div className="flex-1 flex items-center justify-end gap-3">
          {error && (
            <span className="text-xs text-red-500">{error}</span>
          )}
          {/* Circular countdown spinner */}
          {!standby && (
            <div className="relative w-4 h-4" title={`${countdown}s`}>
              <svg className="w-4 h-4 -rotate-90" viewBox="0 0 16 16">
                <circle cx="8" cy="8" r="6" fill="none" className="stroke-muted" strokeWidth="2" />
                <circle
                  cx="8"
                  cy="8"
                  r="6"
                  fill="none"
                  className="stroke-muted-foreground"
                  strokeWidth="2"
                  strokeDasharray={2 * Math.PI * 6}
                  strokeDashoffset={2 * Math.PI * 6 * (countdown / FETCH_INTERVAL)}
                  strokeLinecap="round"
                  style={{ transition: isResetting ? 'none' : 'stroke-dashoffset 1s linear' }}
                />
              </svg>
            </div>
          )}
          {displayTime && (
            <div className="flex flex-col items-end leading-tight">
              <span className="text-[10px] text-muted-foreground font-mono">{displayTime}</span>
              {displayDate && (
                <span className="text-[9px] text-muted-foreground/70 font-mono">{displayDate}</span>
              )}
            </div>
          )}
          <span className={`text-[10px] font-medium ${marketOpen ? 'text-emerald-500' : 'text-muted-foreground'}`}>
            {marketOpen ? 'MARKET OPEN' : 'MARKET CLOSED'}
          </span>
          <div
            className={`w-1.5 h-1.5 rounded-full ${
              error ? 'bg-red-500' :
              !wsConnected ? 'bg-yellow-500 animate-pulse' :
              standby ? 'bg-muted-foreground' :
              marketOpen ? 'bg-emerald-500 animate-pulse' : 'bg-emerald-500'
            }`}
            title={
              error ? 'Error' :
              !wsConnected ? 'Connecting...' :
              standby ? 'Standby (Weekend)' :
              marketOpen ? 'Market Open' : 'Market Closed'
            }
          />
        </div>
      </header>

      {/* Charts Grid */}
      <div className="flex-1 flex flex-col gap-2 p-2 bg-background min-h-0">
        {/* Main Chart - 1 Hour with signals */}
        <div className="flex-[1.2] min-h-0">
          <MemoizedCandlestickChart
            title="1H"
            timeframe="1h"
            data={data['1h']}
            isLoading={isLoading}
            showBollinger={showBollinger}
            showMACD={showMACD}
            showIchimoku={showIchimoku}
            showMovingAverages={showMovingAverages}
            showRSI={showRSI}
            signals={signals}
          />
        </div>

        {/* Bottom Row - No signals on 15min and 1day */}
        <div className="flex-1 flex gap-2 min-h-0">
          <div className="flex-1 min-w-0">
            <MemoizedCandlestickChart
              title="1D"
              timeframe="1day"
              data={data['1day']}
              isLoading={isLoading}
              showBollinger={showBollinger}
              showMACD={showMACD}
              showIchimoku={showIchimoku}
              showMovingAverages={showMovingAverages}
              showRSI={showRSI}
            />
          </div>
          <div className="flex-1 min-w-0">
            <MemoizedCandlestickChart
              title="15M"
              timeframe="15min"
              data={data['15min']}
              isLoading={isLoading}
              showBollinger={showBollinger}
              showMACD={showMACD}
              showIchimoku={showIchimoku}
              showMovingAverages={showMovingAverages}
              showRSI={showRSI}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
