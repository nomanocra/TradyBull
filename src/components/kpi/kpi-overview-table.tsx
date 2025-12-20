'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { StrategyKPIData } from '@/hooks/useKPIs';

type SortKey =
  | 'display_name'
  | 'total_return_pct'
  | 'win_rate_pct'
  | 'profit_factor'
  | 'max_drawdown_pct'
  | 'num_trades'
  | 'avg_return_per_trade_pct'
  | 'avg_trade_duration_hours';

type SortDirection = 'asc' | 'desc';

interface KPIOverviewTableProps {
  data: StrategyKPIData[];
  isLoading?: boolean;
  showArchived?: boolean;
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

function formatValue(value: number, type: SortKey): string {
  switch (type) {
    case 'total_return_pct':
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
      return formatDuration(value);
    default:
      return value.toString();
  }
}

function getColorClass(value: number, type: SortKey): string {
  switch (type) {
    case 'total_return_pct':
    case 'avg_return_per_trade_pct':
      return value >= 0 ? 'text-emerald-500' : 'text-red-500';
    case 'win_rate_pct':
      return value >= 50 ? 'text-emerald-500' : 'text-red-500';
    case 'profit_factor':
      return value >= 1 ? 'text-emerald-500' : 'text-red-500';
    case 'max_drawdown_pct':
      if (value === 0) return 'text-emerald-500';
      if (value <= 5) return 'text-yellow-500';
      return 'text-red-500';
    default:
      return 'text-foreground';
  }
}

const columns: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: 'display_name', label: 'Strategy', numeric: false },
  { key: 'total_return_pct', label: 'Total Return', numeric: true },
  { key: 'win_rate_pct', label: 'Win Rate', numeric: true },
  { key: 'profit_factor', label: 'Profit Factor', numeric: true },
  { key: 'max_drawdown_pct', label: 'Max Drawdown', numeric: true },
  { key: 'num_trades', label: 'Trades', numeric: true },
  { key: 'avg_return_per_trade_pct', label: 'Avg Return', numeric: true },
  { key: 'avg_trade_duration_hours', label: 'Avg Duration', numeric: true },
];

export function KPIOverviewTable({ data, isLoading, showArchived = false }: KPIOverviewTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('total_return_pct');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const sortedData = useMemo(() => {
    if (!data.length) return [];

    // Filter out archived strategies unless showArchived is true
    const filteredData = showArchived
      ? data
      : data.filter((item) => !item.is_archived);

    return [...filteredData].sort((a, b) => {
      let aVal: number | string;
      let bVal: number | string;

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

      const numA = aVal as number;
      const numB = bVal as number;
      return sortDirection === 'asc' ? numA - numB : numB - numA;
    });
  }, [data, sortKey, sortDirection, showArchived]);

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
        <div className="p-8 text-center text-muted-foreground">
          Loading KPIs...
        </div>
      </div>
    );
  }

  if (!data.length) {
    return (
      <div className="border border-border rounded-lg overflow-hidden">
        <div className="p-8 text-center text-muted-foreground">
          No strategy data available
        </div>
      </div>
    );
  }

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/50 border-b border-border">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-3 py-2.5 font-medium text-muted-foreground cursor-pointer hover:text-foreground transition-colors ${
                    col.numeric ? 'text-right' : 'text-left'
                  }`}
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
            </tr>
          </thead>
          <tbody>
            {sortedData.map((item, index) => (
              <tr
                key={item.strategy}
                className={`border-b border-border last:border-b-0 hover:bg-muted/30 transition-colors ${
                  index % 2 === 0 ? 'bg-card' : 'bg-card/50'
                }`}
              >
                <td className="px-3 py-2.5">
                  <Link
                    href={`/strategy/backtesting/${item.strategy}`}
                    className="text-foreground hover:text-brand transition-colors font-medium"
                  >
                    {item.display_name}
                  </Link>
                </td>
                {columns.slice(1).map((col) => {
                  const value = item.kpis[col.key as keyof typeof item.kpis] as number;
                  return (
                    <td
                      key={col.key}
                      className={`px-3 py-2.5 text-right font-mono ${getColorClass(
                        value,
                        col.key
                      )}`}
                    >
                      {formatValue(value, col.key)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
