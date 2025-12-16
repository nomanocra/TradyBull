'use client';

import { useMemo } from 'react';
import { StrategyBacktestingDashboard } from '@/components/dashboard/strategy-backtesting-dashboard';
import { useHistoricalData } from '@/app/exploration/historical/historical-context';
import { calculateBollingerNoSLSignals } from '@/lib/strategies/bollinger-nosl';

export default function BollingerNoSLBacktestingPage() {
  const { data } = useHistoricalData();

  // Calculate signals from historical 1H data
  const signals = useMemo(() => {
    if (data.length === 0) return [];
    return calculateBollingerNoSLSignals(data);
  }, [data]);

  return (
    <StrategyBacktestingDashboard
      strategyName="Bollinger NoSL"
      showBollinger={true}
      signals={signals}
    />
  );
}
