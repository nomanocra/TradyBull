import { RealtimeExplorationDashboard } from '@/components/dashboard/realtime-exploration-dashboard';

export default function StochasticRSIRealTimePage() {
  return (
    <RealtimeExplorationDashboard
      pageName="Stochastic RSI"
      showRSI={true}
    />
  );
}
