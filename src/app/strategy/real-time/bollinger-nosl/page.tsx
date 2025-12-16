'use client';

import { StrategyRealtimeDashboard } from '@/components/dashboard/strategy-realtime-dashboard';
import { useRealtimeData } from '@/app/exploration/real-time/realtime-context';

export default function BollingerNoSLRealtimePage() {
  const { signals } = useRealtimeData();

  // Get signals for bollinger-nosl strategy from WebSocket
  const strategySignals = signals['bollinger-nosl'] || [];

  return (
    <StrategyRealtimeDashboard
      strategyName="Bollinger NoSL"
      showBollinger={true}
      signals={strategySignals}
    />
  );
}
