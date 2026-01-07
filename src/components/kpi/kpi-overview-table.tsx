'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { ArrowUpDown, ArrowUp, ArrowDown, Plus, LineChart, Archive, ArchiveRestore } from 'lucide-react';
import { StrategyKPIData } from '@/hooks/useKPIs';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

type SortKey =
  | 'display_name'
  | 'score'
  | 'total_return_pct'
  | 'avg_yearly_return_pct'
  | 'win_rate_pct'
  | 'profit_factor'
  | 'max_drawdown_pct'
  | 'num_trades'
  | 'avg_return_per_trade_pct'
  | 'avg_trade_duration_hours'
  | 'max_trade_duration_hours';

type SortDirection = 'asc' | 'desc';

interface KPIOverviewTableProps {
  data: StrategyKPIData[];
  isLoading?: boolean;
  showArchived?: boolean;
  searchQuery?: string;
  onAddStrategy?: () => void;
  onArchive?: (strategyName: string) => void;
  onUnarchive?: (strategyName: string) => void;
}

function formatDuration(hours: number): string {
  if (hours < 1) {
    return `${Math.round(hours * 60)}m`;
  }
  if (hours < 24) {
    return `${hours.toFixed(1)}h`;
  }
  const days = hours / 24;
  return `${days.toFixed(1)}d`;
}

function formatValue(value: number | undefined, type: SortKey): string {
  if (value === undefined || value === null) return '-';
  switch (type) {
    case 'score':
      return `${value.toFixed(1)}/10`;
    case 'total_return_pct':
    case 'avg_yearly_return_pct':
    case 'avg_return_per_trade_pct':
      return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
    case 'win_rate_pct':
      return `${value.toFixed(1)}%`;
    case 'profit_factor':
      return value >= 999 ? '∞' : value.toFixed(2);
    case 'max_drawdown_pct':
      return `-${value.toFixed(2)}%`;
    case 'num_trades':
      return value.toString();
    case 'avg_trade_duration_hours':
    case 'max_trade_duration_hours':
      return formatDuration(value);
    default:
      return value.toString();
  }
}

function getColorClass(value: number | undefined, type: SortKey): string {
  if (value === undefined || value === null) return 'text-muted-foreground';
  switch (type) {
    case 'score':
      if (value >= 7) return 'text-emerald-500';
      if (value >= 5) return 'text-yellow-500';
      if (value >= 3) return 'text-orange-500';
      return 'text-red-500';
    case 'total_return_pct':
    case 'avg_yearly_return_pct':
    case 'avg_return_per_trade_pct':
      return value >= 0 ? 'text-emerald-500' : 'text-red-500';
    case 'win_rate_pct':
      return value >= 50 ? 'text-emerald-500' : 'text-red-500';
    case 'profit_factor':
      return value >= 1 ? 'text-emerald-500' : 'text-red-500';
    case 'max_drawdown_pct':
      if (value <= 3) return 'text-emerald-500';
      if (value <= 5) return 'text-yellow-500';
      if (value <= 10) return 'text-orange-500';
      return 'text-red-500';
    default:
      return 'text-foreground';
  }
}

const columns: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: 'display_name', label: 'Strategy', numeric: false },
  { key: 'score', label: 'Score', numeric: true },
  { key: 'total_return_pct', label: 'Total Return', numeric: true },
  { key: 'avg_yearly_return_pct', label: 'Yearly Return', numeric: true },
  { key: 'win_rate_pct', label: 'Win Rate', numeric: true },
  { key: 'profit_factor', label: 'Profit Factor', numeric: true },
  { key: 'max_drawdown_pct', label: 'Max Drawdown', numeric: true },
  { key: 'num_trades', label: 'Trades', numeric: true },
  { key: 'avg_return_per_trade_pct', label: 'Avg Return', numeric: true },
  { key: 'avg_trade_duration_hours', label: 'Avg Duration', numeric: true },
  { key: 'max_trade_duration_hours', label: 'Max Duration', numeric: true },
];

export function KPIOverviewTable({ data, isLoading, showArchived = false, searchQuery = '', onAddStrategy, onArchive, onUnarchive }: KPIOverviewTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const sortedData = useMemo(() => {
    if (!data.length) return [];

    // Filter out archived strategies unless showArchived is true
    let filteredData = showArchived
      ? data
      : data.filter((item) => !item.is_archived);

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      filteredData = filteredData.filter((item) =>
        item.display_name.toLowerCase().includes(query)
      );
    }

    return [...filteredData].sort((a, b) => {
      let aVal: number | string | undefined;
      let bVal: number | string | undefined;

      if (sortKey === 'display_name') {
        aVal = a.display_name;
        bVal = b.display_name;
      } else {
        aVal = a.kpis[sortKey];
        bVal = b.kpis[sortKey];
      }

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      const numA = (aVal as number) ?? 0;
      const numB = (bVal as number) ?? 0;
      return sortDirection === 'asc' ? numA - numB : numB - numA;
    });
  }, [data, sortKey, sortDirection, showArchived, searchQuery]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDirection('desc');
    }
  };

  const SortIcon = ({ columnKey }: { columnKey: SortKey }) => {
    if (sortKey !== columnKey) {
      return <ArrowUpDown size={12} className="text-muted-foreground" />;
    }
    return sortDirection === 'asc' ? (
      <ArrowUp size={12} className="text-brand" />
    ) : (
      <ArrowDown size={12} className="text-brand" />
    );
  };

  if (isLoading) {
    return (
      <div className="border border-border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted/50 border-b border-border">
                {columns.map((col) => (
                  <th
                    key={col.key}
                    className={`px-3 py-2.5 font-medium text-muted-foreground ${
                      col.numeric ? 'text-right' : 'text-left'
                    }`}
                  >
                    <div
                      className={`flex items-center gap-1.5 ${
                        col.numeric ? 'justify-end' : 'justify-start'
                      }`}
                    >
                      <span className="text-[11px] uppercase tracking-wide">
                        {col.label}
                      </span>
                      <ArrowUpDown size={12} className="text-muted-foreground" />
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 8 }).map((_, rowIndex) => (
                <tr
                  key={rowIndex}
                  className={`border-b border-border last:border-b-0 ${
                    rowIndex % 2 === 0 ? 'bg-card' : 'bg-card/50'
                  }`}
                >
                  <td className="px-3 py-2.5">
                    <Skeleton className="h-4 w-32" />
                  </td>
                  {columns.slice(1).map((col) => (
                    <td key={col.key} className="px-3 py-2.5">
                      <div className="flex justify-end">
                        <Skeleton className="h-4 w-14" />
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // Only show empty state if we have no data at all (not just filtered out)
  if (!sortedData.length && data.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center flex flex-col items-center">
          <LineChart size={48} className="text-muted-foreground/30 mb-4" />
          <p className="text-sm font-medium mb-1">Create your first strategy</p>
          <p className="text-xs text-muted-foreground mb-5">Build and backtest custom trading strategies</p>
          {onAddStrategy && (
            <Button onClick={onAddStrategy} size="sm" className="h-8 text-xs">
              <Plus size={12} />
              Add Strategy
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="border border-border overflow-auto h-full">
      <table className="w-full text-sm">
          <thead className="sticky top-0 z-20">
            <tr className="bg-neutral-100 dark:bg-neutral-900">
              {columns.map((col, colIndex) => (
                <th
                  key={col.key}
                  className={`px-3 py-2.5 font-medium text-muted-foreground cursor-pointer hover:text-foreground transition-colors bg-neutral-100 dark:bg-neutral-900 ${
                    col.numeric ? 'text-right' : 'text-left'
                  } ${colIndex === 0 ? 'sticky left-0 z-30 min-w-[280px]' : ''}`}
                  onClick={() => handleSort(col.key)}
                >
                  <div
                    className={`flex items-center gap-1.5 ${
                      col.numeric ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    <span className="text-[11px] uppercase tracking-wide">
                      {col.label}
                    </span>
                    <SortIcon columnKey={col.key} />
                  </div>
                </th>
              ))}
              <th className="px-3 py-2.5 bg-neutral-100 dark:bg-neutral-900 w-10 sticky right-0 z-30" />
            </tr>
            <tr className="sticky top-[37px] z-20">
              <td colSpan={columns.length + 1} className="h-px bg-border p-0" />
            </tr>
          </thead>
          <tbody>
            {sortedData.map((item, index) => (
              <tr
                key={item.strategy}
                className="group transition-colors"
              >
                <td className={`px-3 py-2.5 sticky left-0 z-10 transition-colors min-w-[280px] border-b border-[#e5e5e5] dark:border-[#1a1a1a] ${
                  index % 2 === 0
                    ? 'bg-white dark:bg-[#0a0a0a] group-hover:bg-neutral-100 dark:group-hover:bg-neutral-800'
                    : 'bg-[#fafafa] dark:bg-[#0d0d0d] group-hover:bg-neutral-100 dark:group-hover:bg-neutral-800'
                }`}>
                  <Link
                    href={`/strategy/backtesting/${item.strategy}`}
                    className={`hover:text-brand transition-colors font-medium ${
                      item.is_archived ? 'text-muted-foreground/50' : 'text-foreground'
                    }`}
                  >
                    {item.display_name}
                  </Link>
                </td>
                {columns.slice(1).map((col) => {
                  const value = item.kpis[col.key as keyof typeof item.kpis] as number;
                  return (
                    <td
                      key={col.key}
                      className={`px-3 py-2.5 text-right font-mono transition-colors border-b border-[#e5e5e5] dark:border-[#1a1a1a] ${getColorClass(
                        value,
                        col.key
                      )} ${
                        index % 2 === 0
                          ? 'bg-white dark:bg-[#0a0a0a] group-hover:bg-neutral-100 dark:group-hover:bg-neutral-800'
                          : 'bg-[#fafafa] dark:bg-[#0d0d0d] group-hover:bg-neutral-100 dark:group-hover:bg-neutral-800'
                      }`}
                    >
                      {formatValue(value, col.key)}
                    </td>
                  );
                })}
                <td className={`px-2 py-2.5 text-center sticky right-0 z-10 transition-colors border-b border-[#e5e5e5] dark:border-[#1a1a1a] ${
                  index % 2 === 0
                    ? 'bg-white dark:bg-[#0a0a0a] group-hover:bg-neutral-100 dark:group-hover:bg-neutral-800'
                    : 'bg-[#fafafa] dark:bg-[#0d0d0d] group-hover:bg-neutral-100 dark:group-hover:bg-neutral-800'
                }`}>
                  {item.is_archived ? (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          onClick={() => onUnarchive?.(item.strategy)}
                          className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-all opacity-0 group-hover:opacity-100"
                        >
                          <ArchiveRestore size={14} />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="bottom">Unarchive</TooltipContent>
                    </Tooltip>
                  ) : (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          onClick={() => onArchive?.(item.strategy)}
                          className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-all opacity-0 group-hover:opacity-100"
                        >
                          <Archive size={14} />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="bottom">Archive</TooltipContent>
                    </Tooltip>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
    </div>
  );
}
