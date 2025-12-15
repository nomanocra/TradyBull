'use client';

import { useState, useCallback, useMemo, useEffect } from 'react';
import { MemoizedCandlestickChart } from '@/components/chart/candlestick-chart';
import { DatePicker } from '@/components/ui/date-picker';
import { useHistoricalData } from '@/app/exploration/historical/historical-context';

const STORAGE_KEY = 'tradybull-sandbox-indicators';

interface IndicatorToggle {
  id: string;
  label: string;
  shortLabel: string;
  color: string;
  prop: 'showBollinger' | 'showMACD' | 'showIchimoku' | 'showMovingAverages' | 'showRSI';
}

const indicators: IndicatorToggle[] = [
  { id: 'bollinger', label: 'Bollinger Bands', shortLabel: 'BB', color: '#3b82f6', prop: 'showBollinger' },
  { id: 'macd', label: 'MACD', shortLabel: 'MACD', color: '#f97316', prop: 'showMACD' },
  { id: 'ichimoku', label: 'Ichimoku Cloud', shortLabel: 'Ichimoku', color: '#8b5cf6', prop: 'showIchimoku' },
  { id: 'ma', label: 'Moving Averages', shortLabel: 'MA', color: '#eab308', prop: 'showMovingAverages' },
  { id: 'rsi', label: 'Stochastic RSI', shortLabel: 'Stoch', color: '#10b981', prop: 'showRSI' },
];

export function SandboxDashboard() {
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

  // Indicators state
  const [activeIndicators, setActiveIndicators] = useState<Set<string>>(new Set());
  const [isHydrated, setIsHydrated] = useState(false);

  // Load from localStorage after hydration
  useEffect(() => {
    const savedIndicators = localStorage.getItem(STORAGE_KEY);
    if (savedIndicators) {
      try {
        setActiveIndicators(new Set(JSON.parse(savedIndicators)));
      } catch {
        // Invalid JSON
      }
    }
    setIsHydrated(true);
  }, []);

  // Save indicators to localStorage
  useEffect(() => {
    if (isHydrated) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...activeIndicators]));
    }
  }, [activeIndicators, isHydrated]);

  const toggleIndicator = useCallback((id: string) => {
    setActiveIndicators(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const indicatorProps = useMemo(() => {
    return indicators.reduce((acc, indicator) => {
      acc[indicator.prop] = activeIndicators.has(indicator.id);
      return acc;
    }, {} as Record<string, boolean>);
  }, [activeIndicators]);

  // Price info - performance over entire period
  const { lastPrice, priceChange } = useMemo(() => {
    const last = data.length > 0 ? data[data.length - 1].close : null;
    const first = data.length > 0 ? data[0].close : null;
    const change = last && first ? ((last - first) / first) * 100 : null;
    return { lastPrice: last, priceChange: change };
  }, [data]);

  return (
    <div className="h-full w-full bg-[#0a0a0a] flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-3 py-1.5 border-b border-[#1a1a1a] bg-[#0d0d0d]">
        {/* Page name - Left */}
        <div className="flex-1 flex items-center gap-3">
          <span className="text-xs font-semibold text-[#C59471]">Multi Indicator</span>
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

      {/* Indicator Bar */}
      <div className="flex items-center gap-1.5 px-2 py-1 bg-[#0d0d0d] border-b border-[#1a1a1a]">
        <span className="text-[9px] text-gray-500 uppercase tracking-wider mr-1">Indicateurs</span>
        {indicators.map((indicator) => {
          const isActive = activeIndicators.has(indicator.id);
          return (
            <button
              key={indicator.id}
              onClick={() => toggleIndicator(indicator.id)}
              className={`
                px-1.5 py-0.5 rounded-full text-[9px] font-medium
                transition-all duration-200 ease-out cursor-pointer
                border
                ${isActive
                  ? 'text-white border-transparent'
                  : 'text-gray-500 border-[#2a2a2a] hover:border-[#3a3a3a] hover:text-gray-400'
                }
              `}
              style={{
                backgroundColor: isActive ? indicator.color : 'transparent',
                boxShadow: isActive ? `0 0 8px ${indicator.color}40` : 'none',
              }}
              title={indicator.label}
            >
              {indicator.shortLabel}
            </button>
          );
        })}
        {activeIndicators.size === 0 && (
          <span className="text-[9px] text-gray-600 italic ml-1">
            Sélectionnez un indicateur
          </span>
        )}
      </div>

      {/* Single 1H Chart */}
      <div className="flex-1 p-2 bg-[#0a0a0a] min-h-0">
        <MemoizedCandlestickChart
          title="1H - Historical"
          timeframe="1h"
          data={data}
          isLoading={isLoading}
          showNavigator={true}
          {...indicatorProps}
        />
      </div>
    </div>
  );
}
