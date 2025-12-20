'use client';

import { useParams } from 'next/navigation';
import { StrategyBacktestingDashboard } from '@/components/dashboard/strategy-backtesting-dashboard';
import { useHistoricalData } from '@/app/exploration/historical/historical-context';
import { useSignals } from '@/hooks/useSignals';
import { useStrategies } from '@/hooks/useStrategies';
import { useKPIs } from '@/hooks/useKPIs';

export default function StrategyBacktestingPage() {
  const params = useParams();
  const strategySlug = params.strategy as string;
  const { data, startDate, endDate } = useHistoricalData();
  const { allStrategies, isLoading: strategiesLoading } = useStrategies();

  // Find the strategy config (including archived strategies)
  const strategyConfig = allStrategies.find((s) => s.name === strategySlug);

  // Convert dates to timestamps for API call
  const startTs = startDate ? Math.floor(startDate.getTime() / 1000) : undefined;
  const endTs = endDate ? Math.floor(new Date(endDate).setHours(23, 59, 59, 999) / 1000) : undefined;

  // Fetch signals from backend
  const { signals, isLoading: signalsLoading } = useSignals({
    strategy: strategySlug,
    startTs,
    endTs,
    enabled: data.length > 0 && !!strategyConfig,
  });

  // Fetch KPIs from backend
  const { kpis, isLoading: kpisLoading } = useKPIs({
    strategy: strategySlug,
    startTs,
    endTs,
    enabled: data.length > 0 && !!strategyConfig,
  });

  // Loading state
  if (strategiesLoading || !strategyConfig) {
    return (
      <div className="h-full w-full flex items-center justify-center bg-background">
        <div className="text-muted-foreground text-sm">
          {strategiesLoading ? 'Loading...' : `Strategy "${strategySlug}" not found`}
        </div>
      </div>
    );
  }

  return (
    <StrategyBacktestingDashboard
      strategyName={strategyConfig.display_name}
      strategyDescription={strategyConfig.description}
      showBollinger={strategyConfig.show_bollinger}
      showMACD={strategyConfig.show_macd}
      showIchimoku={strategyConfig.show_ichimoku}
      showMovingAverages={strategyConfig.show_moving_averages}
      showRSI={strategyConfig.show_rsi}
      signals={signals}
      kpis={kpis}
      kpisLoading={kpisLoading}
    />
  );
}
