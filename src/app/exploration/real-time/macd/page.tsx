import { RealtimeExplorationDashboard } from '@/components/dashboard/realtime-exploration-dashboard';

export default function MACDRealTimePage() {
  return (
    <RealtimeExplorationDashboard
      pageName="MACD"
      showMACD={true}
    />
  );
}
