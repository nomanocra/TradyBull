'use client';

import { useParams } from 'next/navigation';
import { StrategyRealtimeDashboard } from '@/components/dashboard/strategy-realtime-dashboard';
import { useRealtimeData } from '@/app/exploration/real-time/realtime-context';
import { useStrategies } from '@/hooks/useStrategies';

export default function StrategyRealtimePage() {
  const params = useParams();
  const strategySlug = params.strategy as string;
  const { signals } = useRealtimeData();
  const { strategies, isLoading: strategiesLoading } = useStrategies();

  // Find the strategy config
  const strategyConfig = strategies.find((s) => s.name === strategySlug);

  // Get signals for this strategy from WebSocket
  const strategySignals = signals[strategySlug] || [];

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
    <StrategyRealtimeDashboard
      strategyName={strategyConfig.display_name}
      strategyDescription={strategyConfig.description}
      showBollinger={strategyConfig.show_bollinger}
      showMACD={strategyConfig.show_macd}
      showIchimoku={strategyConfig.show_ichimoku}
      showMovingAverages={strategyConfig.show_moving_averages}
      showRSI={strategyConfig.show_rsi}
      maPeriods={strategyConfig.ma_periods}
      signals={strategySignals}
    />
  );
}
