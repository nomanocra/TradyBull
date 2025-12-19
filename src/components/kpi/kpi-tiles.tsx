'use client';

import { KPIs } from '@/hooks/useKPIs';

interface KPITilesProps {
  kpis: KPIs | null;
  isLoading?: boolean;
}

interface KPITileProps {
  label: string;
  value: string;
  isPositive?: boolean | null; // null = neutral
  isLoading?: boolean;
}

function KPITile({ label, value, isPositive, isLoading }: KPITileProps) {
  const colorClass =
    isPositive === null
      ? 'text-foreground'
      : isPositive
        ? 'text-emerald-500'
        : 'text-red-500';

  return (
    <div className="bg-card border border-border rounded px-2.5 py-1.5 min-w-0">
      <div className="text-[9px] text-muted-foreground uppercase tracking-wide truncate">
        {label}
      </div>
      <div className={`text-sm font-mono font-semibold ${isLoading ? 'text-muted-foreground' : colorClass}`}>
        {isLoading ? '...' : value}
      </div>
    </div>
  );
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

export function KPITiles({ kpis, isLoading }: KPITilesProps) {
  const tiles = [
    {
      label: 'Total Return',
      value: kpis ? `${kpis.total_return_pct >= 0 ? '+' : ''}${kpis.total_return_pct.toFixed(2)}%` : '-',
      isPositive: kpis ? (kpis.total_return_pct >= 0 ? true : false) : null,
    },
    {
      label: 'Win Rate',
      value: kpis ? `${kpis.win_rate_pct.toFixed(1)}%` : '-',
      isPositive: kpis ? (kpis.win_rate_pct >= 50 ? true : false) : null,
    },
    {
      label: 'Profit Factor',
      value: kpis ? (kpis.profit_factor >= 999 ? '∞' : kpis.profit_factor.toFixed(2)) : '-',
      isPositive: kpis ? (kpis.profit_factor >= 1 ? true : false) : null,
    },
    {
      label: 'Max Drawdown',
      value: kpis ? `-${kpis.max_drawdown_pct.toFixed(2)}%` : '-',
      isPositive: kpis ? (kpis.max_drawdown_pct <= 5 ? true : false) : null,
    },
    {
      label: 'Trades',
      value: kpis ? `${kpis.num_trades}` : '-',
      isPositive: null, // Neutral
    },
    {
      label: 'Avg Return',
      value: kpis ? `${kpis.avg_return_per_trade_pct >= 0 ? '+' : ''}${kpis.avg_return_per_trade_pct.toFixed(2)}%` : '-',
      isPositive: kpis ? (kpis.avg_return_per_trade_pct >= 0 ? true : false) : null,
    },
    {
      label: 'Avg Duration',
      value: kpis ? formatDuration(kpis.avg_trade_duration_hours) : '-',
      isPositive: null, // Neutral
    },
  ];

  return (
    <div className="flex gap-2 flex-wrap">
      {tiles.map((tile) => (
        <KPITile
          key={tile.label}
          label={tile.label}
          value={tile.value}
          isPositive={tile.isPositive}
          isLoading={isLoading}
        />
      ))}
    </div>
  );
}
