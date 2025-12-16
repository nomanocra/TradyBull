'use client';

import { StrategyBacktestingDashboard } from '@/components/dashboard/strategy-backtesting-dashboard';
import { useHistoricalData } from '@/app/exploration/historical/historical-context';
import { useSignals } from '@/hooks/useSignals';

export default function BollingerNoSLBacktestingPage() {
  const { data, startDate, endDate } = useHistoricalData();

  // Convert dates to timestamps for API call
  const startTs = startDate ? Math.floor(startDate.getTime() / 1000) : undefined;
  const endTs = endDate ? Math.floor(new Date(endDate).setHours(23, 59, 59, 999) / 1000) : undefined;

  // Fetch signals from backend instead of calculating on the fly
  const { signals, isLoading: signalsLoading, error: signalsError } = useSignals({
    strategy: 'bollinger-nosl',
    startTs,
    endTs,
    enabled: data.length > 0,
  });

  return (
    <StrategyBacktestingDashboard
      strategyName="Bollinger NoSL"
      showBollinger={true}
      signals={signals}
    />
  );
}
