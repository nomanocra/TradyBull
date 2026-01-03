'use client';

import { KPIs } from '@/hooks/useKPIs';
import { Skeleton } from '@/components/ui/skeleton';

interface KPITilesProps {
  kpis: KPIs | null;
  isLoading?: boolean;
}

type ColorState = 'positive' | 'caution' | 'warning' | 'negative' | 'neutral';

interface KPITileProps {
  label: string;
  value: string;
  colorState?: ColorState;
  isLoading?: boolean;
}

function KPITile({ label, value, colorState = 'neutral', isLoading }: KPITileProps) {
  const colorClass = {
    positive: 'text-emerald-500',
    caution: 'text-yellow-500',
    warning: 'text-orange-500',
    negative: 'text-red-500',
    neutral: 'text-foreground',
  }[colorState];

  return (
    <div className="bg-card rounded px-2.5 py-1.5 min-w-0">
      <div className="text-[9px] text-muted-foreground uppercase tracking-wide truncate">
        {label}
      </div>
      {isLoading ? (
        <Skeleton className="h-5 w-12 mt-0.5" />
      ) : (
        <div className={`text-sm font-mono font-semibold ${colorClass}`}>
          {value}
        </div>
      )}
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

function getDrawdownColor(drawdown: number): ColorState {
  if (drawdown <= 3) return 'positive';
  if (drawdown <= 5) return 'caution';
  if (drawdown <= 10) return 'warning';
  return 'negative';
}

export function KPITiles({ kpis, isLoading }: KPITilesProps) {
  const tiles: { label: string; value: string; colorState: ColorState }[] = [
    {
      label: 'Total Return',
      value: kpis ? `${kpis.total_return_pct >= 0 ? '+' : ''}${kpis.total_return_pct.toFixed(2)}%` : '-',
      colorState: kpis ? (kpis.total_return_pct >= 0 ? 'positive' : 'negative') : 'neutral',
    },
    {
      label: 'Yearly Return',
      value: kpis?.avg_yearly_return_pct !== undefined ? `${kpis.avg_yearly_return_pct >= 0 ? '+' : ''}${kpis.avg_yearly_return_pct.toFixed(2)}%` : '-',
      colorState: kpis?.avg_yearly_return_pct !== undefined ? (kpis.avg_yearly_return_pct >= 0 ? 'positive' : 'negative') : 'neutral',
    },
    {
      label: 'Win Rate',
      value: kpis ? `${kpis.win_rate_pct.toFixed(1)}%` : '-',
      colorState: kpis ? (kpis.win_rate_pct >= 50 ? 'positive' : 'negative') : 'neutral',
    },
    {
      label: 'Profit Factor',
      value: kpis ? (kpis.profit_factor >= 999 ? '∞' : kpis.profit_factor.toFixed(2)) : '-',
      colorState: kpis ? (kpis.profit_factor >= 1 ? 'positive' : 'negative') : 'neutral',
    },
    {
      label: 'Max Drawdown',
      value: kpis ? `-${kpis.max_drawdown_pct.toFixed(2)}%` : '-',
      colorState: kpis ? getDrawdownColor(kpis.max_drawdown_pct) : 'neutral',
    },
    {
      label: 'Trades',
      value: kpis ? `${kpis.num_trades}` : '-',
      colorState: 'neutral',
    },
    {
      label: 'Avg Return',
      value: kpis ? `${kpis.avg_return_per_trade_pct >= 0 ? '+' : ''}${kpis.avg_return_per_trade_pct.toFixed(2)}%` : '-',
      colorState: kpis ? (kpis.avg_return_per_trade_pct >= 0 ? 'positive' : 'negative') : 'neutral',
    },
    {
      label: 'Avg Duration',
      value: kpis ? formatDuration(kpis.avg_trade_duration_hours) : '-',
      colorState: 'neutral',
    },
  ];

  return (
    <div className="flex gap-2 flex-wrap">
      {tiles.map((tile) => (
        <KPITile
          key={tile.label}
          label={tile.label}
          value={tile.value}
          colorState={tile.colorState}
          isLoading={isLoading}
        />
      ))}
    </div>
  );
}
