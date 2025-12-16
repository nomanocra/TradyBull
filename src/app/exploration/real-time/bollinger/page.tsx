import { RealtimeExplorationDashboard } from '@/components/dashboard/realtime-exploration-dashboard';

export default function BollingerRealTimePage() {
  return (
    <RealtimeExplorationDashboard
      pageName="Bollinger Bands"
      showBollinger={true}
    />
  );
}
