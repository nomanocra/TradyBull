'use client';

import { useState, useCallback, useMemo, useEffect } from 'react';
import { MemoizedCandlestickChart } from '@/components/chart/candlestick-chart';
import { ChartNavigator } from '@/components/chart/chart-navigator';
import { Checkbox } from '@/components/ui/checkbox';
import { CandleData } from '@/types/market';
import { useSignals } from '@/hooks/useSignals';

const STORAGE_KEY = 'tradybull-sandbox-indicators';
const SIGNALS_STORAGE_KEY = 'tradybull-signals-sandbox';
const API_URL = 'http://localhost:8000/api/backtest/data';

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
  const [data, setData] = useState<CandleData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dataInfo, setDataInfo] = useState<{ count: number; symbol: string } | null>(null);

  // Indicators state
  const [activeIndicators, setActiveIndicators] = useState<Set<string>>(new Set());
  const [isHydrated, setIsHydrated] = useState(false);

  // Signals state
  const [signalsEnabled, setSignalsEnabled] = useState(false);

  // Navigator visible range state
  const [visibleRange, setVisibleRange] = useState<{ from: number; to: number } | null>(null);
  const [navigatorRange, setNavigatorRange] = useState<{ from: number; to: number } | null>(null);

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
    const savedSignals = localStorage.getItem(SIGNALS_STORAGE_KEY);
    if (savedSignals !== null) {
      setSignalsEnabled(savedSignals === 'true');
    }
    setIsHydrated(true);
  }, []);

  // Save indicators to localStorage
  useEffect(() => {
    if (isHydrated) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...activeIndicators]));
    }
  }, [activeIndicators, isHydrated]);

  // Save signals preference
  useEffect(() => {
    if (isHydrated) {
      localStorage.setItem(SIGNALS_STORAGE_KEY, String(signalsEnabled));
    }
  }, [signalsEnabled, isHydrated]);

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

  // Handle visible range changes from chart (source of truth for actual displayed range)
  const handleVisibleRangeChange = useCallback((from: number, to: number) => {
    // Always update navigator to reflect what the chart is actually showing
    // This ensures navigator respects chart's zoom limits
    setNavigatorRange({ from, to });
  }, []);

  // Handle range changes from navigator
  const handleNavigatorRangeChange = useCallback((from: number, to: number) => {
    setVisibleRange({ from, to });
  }, []);

  const indicatorProps = useMemo(() => {
    return indicators.reduce((acc, indicator) => {
      acc[indicator.prop] = activeIndicators.has(indicator.id);
      return acc;
    }, {} as Record<string, boolean>);
  }, [activeIndicators]);

  const hasSignalIndicator = activeIndicators.has('bollinger');

  // Fetch pre-calculated signals from API
  const { signals: preCalculatedSignals, isLoading: signalsLoading } = useSignals({
    indicator: 'all',
    enabled: hasSignalIndicator && signalsEnabled,
  });

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
        {/* Page name + Signals toggle - Left */}
        <div className="flex-1 flex items-center gap-3">
          <span className="text-xs font-semibold text-[#C59471]">Sandbox</span>
          {hasSignalIndicator && (
            <label htmlFor="sandbox-signals-toggle" className="flex items-center gap-1.5 cursor-pointer select-none">
              <Checkbox
                id="sandbox-signals-toggle"
                checked={signalsEnabled}
                onCheckedChange={(checked) => setSignalsEnabled(checked === true)}
                className="size-3 rounded-[2px] data-[state=checked]:!bg-[#C59471] data-[state=checked]:!border-[#C59471] data-[state=checked]:!text-white [&_svg]:size-2.5"
              />
              <span className="text-[10px] text-gray-400">Signals</span>
            </label>
          )}
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
                transition-all duration-200 ease-out
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

      {/* Single 1H Chart with Navigator */}
      <div className="flex-1 flex flex-col bg-[#0a0a0a] min-h-0">
        {/* Chart */}
        <div className="flex-1 p-2 pb-0 min-h-0">
          <MemoizedCandlestickChart
            title="1H - Historical"
            timeframe="1h"
            data={data}
            isLoading={isLoading || signalsLoading}
            showBollingerSignals={indicatorProps.showBollinger && signalsEnabled}
            preCalculatedSignals={preCalculatedSignals}
            onVisibleRangeChange={handleVisibleRangeChange}
            visibleRangeIndices={visibleRange}
            {...indicatorProps}
          />
        </div>

        {/* Navigator */}
        <ChartNavigator
          data={data}
          visibleRange={navigatorRange}
          onRangeChange={handleNavigatorRangeChange}
        />
      </div>
    </div>
  );
}
