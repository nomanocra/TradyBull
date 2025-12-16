'use client';

import { useMemo } from 'react';
import { StrategyRealtimeDashboard } from '@/components/dashboard/strategy-realtime-dashboard';
import { useRealtimeData } from '@/app/exploration/real-time/realtime-context';
import { calculateBollingerNoSLSignals } from '@/lib/strategies/bollinger-nosl';

export default function BollingerNoSLRealtimePage() {
  const { data } = useRealtimeData();

  // Calculate signals from 1H data
  const signals = useMemo(() => {
    if (data['1h'].length === 0) return [];
    return calculateBollingerNoSLSignals(data['1h']);
  }, [data]);

  return (
    <StrategyRealtimeDashboard
      strategyName="Bollinger NoSL"
      showBollinger={true}
      signals={signals}
    />
  );
}
