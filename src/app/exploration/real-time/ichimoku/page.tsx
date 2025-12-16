import { RealtimeExplorationDashboard } from '@/components/dashboard/realtime-exploration-dashboard';

export default function IchimokuRealTimePage() {
  return (
    <RealtimeExplorationDashboard
      pageName="Ichimoku Cloud"
      showIchimoku={true}
    />
  );
}
