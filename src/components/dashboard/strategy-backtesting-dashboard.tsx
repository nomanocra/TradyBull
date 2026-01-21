'use client';

import { useMemo, useCallback, useState } from 'react';
import { Info, RefreshCw } from 'lucide-react';
import { MemoizedCandlestickChart } from '@/components/chart/candlestick-chart';
import { DatePicker } from '@/components/ui/date-picker';
import { DataSourceSelector } from '@/components/ui/data-source-selector';
import { KPITiles } from '@/components/kpi/kpi-tiles';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import { useHistoricalData } from '@/app/exploration/historical/historical-context';
import { Signal } from '@/types/market';
import { KPIs } from '@/hooks/useKPIs';

interface StrategyBacktestingDashboardProps {
  strategyName: string;
  strategySlug: string;
  strategyDescription?: string;
  showBollinger?: boolean;
  showMACD?: boolean;
  showIchimoku?: boolean;
  showMovingAverages?: boolean;
  showRSI?: boolean;
  maPeriods?: number[];
  signals: Signal[];
  signalsLoading?: boolean;
  kpis?: KPIs | null;
  kpisLoading?: boolean;
  onRefresh?: () => void;
}

export function StrategyBacktestingDashboard({
  strategyName,
  strategySlug,
  strategyDescription,
  showBollinger = false,
  showMACD = false,
  showIchimoku = false,
  showMovingAverages = false,
  showRSI = false,
  maPeriods = [],
  signals,
  signalsLoading = false,
  kpis,
  kpisLoading = false,
  onRefresh,
}: StrategyBacktestingDashboardProps) {
  const [isUpdating, setIsUpdating] = useState(false);

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
    zoomState,
    setZoomState,
    dataSource,
    setDataSource,
  } = useHistoricalData();

  const handleUpdate = useCallback(async () => {
    setIsUpdating(true);
    try {
      const response = await fetch(
        `http://localhost:8000/api/signals/recalculate?strategy=${encodeURIComponent(strategySlug)}&data_source=${encodeURIComponent(dataSource)}`,
        { method: 'POST' }
      );
      if (!response.ok) {
        throw new Error('Failed to recalculate signals');
      }
      // Refresh signals and KPIs
      onRefresh?.();
    } catch (error) {
      console.error('Error updating signals:', error);
    } finally {
      setIsUpdating(false);
    }
  }, [strategySlug, onRefresh, dataSource]);

  // Price info - performance over entire period
  const { lastPrice, priceChange } = useMemo(() => {
    const last = data.length > 0 ? data[data.length - 1].close : null;
    const first = data.length > 0 ? data[0].close : null;
    const change = last && first ? ((last - first) / first) * 100 : null;
    return { lastPrice: last, priceChange: change };
  }, [data]);

  // Handle year range selection (year=0 means "All")
  const handleYearRangeSelect = useCallback((year: number) => {
    if (year === 0 && dateBounds) {
      // "All" - reset to full data bounds
      setStartDate(dateBounds.minDate);
      setEndDate(dateBounds.maxDate);
      return;
    }

    const startOfYear = new Date(year, 0, 1);
    const endOfYear = new Date(year, 11, 31);

    // Clamp to available data bounds
    if (dateBounds) {
      const clampedStart = startOfYear < dateBounds.minDate ? dateBounds.minDate : startOfYear;
      const clampedEnd = endOfYear > dateBounds.maxDate ? dateBounds.maxDate : endOfYear;
      setStartDate(clampedStart);
      setEndDate(clampedEnd);
    } else {
      setStartDate(startOfYear);
      setEndDate(endOfYear);
    }
  }, [dateBounds, setStartDate, setEndDate]);

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
                  <Info className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground cursor-pointer transition-colors" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-xs text-xs">
                {strategyDescription}
              </TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* Data source + Symbol and price - Center */}
        <div className="flex items-center gap-3">
          <DataSourceSelector
            value={dataSource}
            onChange={setDataSource}
          />
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
                  onYearRangeSelect={handleYearRangeSelect}
                  yearRangeBounds={dateBounds}
                />
              </div>
              <div className="flex items-center gap-1">
                <span className="text-[9px] text-muted-foreground">End</span>
                <DatePicker
                  date={endDate}
                  onDateChange={setEndDate}
                  minDate={startDate || dateBounds.minDate}
                  maxDate={dateBounds.maxDate}
                  onYearRangeSelect={handleYearRangeSelect}
                  yearRangeBounds={dateBounds}
                />
              </div>
            </div>
          )}
          {dataInfo && (
            <span className="text-[10px] text-muted-foreground">
              {dataInfo.count.toLocaleString()} candles
            </span>
          )}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleUpdate}
                disabled={isUpdating || isLoading}
                className="h-6 w-6 p-0"
              >
                <RefreshCw
                  size={12}
                  className={isUpdating ? 'animate-spin' : ''}
                />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              Recalculate signals with latest data
            </TooltipContent>
          </Tooltip>
        </div>
      </header>

      {/* KPI Tiles */}
      <div className="px-2 pt-2">
        <KPITiles kpis={kpis ?? null} isLoading={kpisLoading} />
      </div>

      {/* Single 1H Chart with signals and navigator */}
      <div className="flex-1 p-2 bg-background min-h-0">
        <MemoizedCandlestickChart
          title="1H - Backtesting"
          timeframe="1h"
          data={data}
          isLoading={isLoading || signalsLoading}
          showBollinger={showBollinger}
          showMACD={showMACD}
          showIchimoku={showIchimoku}
          showMovingAverages={showMovingAverages}
          showRSI={showRSI}
          maPeriods={maPeriods}
          showNavigator={true}
          signals={signals}
          initialZoom={zoomState}
          onZoomChange={setZoomState}
        />
      </div>
    </div>
  );
}
