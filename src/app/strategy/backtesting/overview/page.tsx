'use client';

import { useState, useEffect, useCallback } from 'react';
import { Search } from 'lucide-react';
import { DatePicker } from '@/components/ui/date-picker';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { KPIOverviewTable } from '@/components/kpi/kpi-overview-table';
import { useHistoricalData } from '@/app/exploration/historical/historical-context';
import { useAllKPIs } from '@/hooks/useKPIs';
import { strategyEvents } from '@/lib/strategy-events';

export default function BacktestingOverviewPage() {
  const [showArchived, setShowArchived] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const {
    isLoading: dataLoading,
    error,
    dataInfo,
    dateBounds,
    startDate,
    endDate,
    setStartDate,
    setEndDate,
  } = useHistoricalData();

  // Convert dates to timestamps for API call
  const startTs = startDate ? Math.floor(startDate.getTime() / 1000) : undefined;
  const endTs = endDate ? Math.floor(new Date(endDate).setHours(23, 59, 59, 999) / 1000) : undefined;

  // Fetch KPIs for all strategies
  const { data: kpisData, isLoading: kpisLoading, refetch } = useAllKPIs({
    startTs,
    endTs,
    enabled: !dataLoading,
  });

  // Listen for strategy archive/unarchive events
  useEffect(() => {
    return strategyEvents.subscribe(() => {
      refetch();
    });
  }, [refetch]);

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
        {/* Title - Left */}
        <div className="flex-1 flex items-center gap-2">
          <span className="text-xs font-semibold text-brand">Strategies Overview</span>
        </div>

        {/* Symbol - Center */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">{dataInfo?.symbol || 'NQ=F'}</span>
        </div>

        {/* Date pickers - Right */}
        <div className="flex-1 flex items-center justify-end gap-3">
          {error && (
            <span className="text-xs text-red-500">{error}</span>
          )}
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
          <div
            className={`w-1.5 h-1.5 rounded-full ${
              error ? 'bg-red-500' :
              dataLoading || kpisLoading ? 'bg-yellow-500 animate-pulse' :
              'bg-emerald-500'
            }`}
            title={error ? 'Error' : (dataLoading || kpisLoading) ? 'Loading...' : 'Data loaded'}
          />
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 p-4 overflow-auto">
        {/* Filters */}
        <div className="flex items-center justify-between mb-4">
          {/* Show Archived Switch */}
          <div className="flex items-center gap-2">
            <Switch
              id="show-archived"
              checked={showArchived}
              onCheckedChange={setShowArchived}
            />
            <label
              htmlFor="show-archived"
              className="text-xs text-muted-foreground cursor-pointer select-none"
            >
              Show Archived
            </label>
          </div>

          {/* Search */}
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search strategies..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-8 w-48"
            />
          </div>
        </div>

        <KPIOverviewTable data={kpisData} isLoading={kpisLoading} showArchived={showArchived} searchQuery={searchQuery} />
      </div>
    </div>
  );
}
