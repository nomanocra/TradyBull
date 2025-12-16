import { RealtimeExplorationDashboard } from '@/components/dashboard/realtime-exploration-dashboard';

export default function MovingAveragesRealTimePage() {
  return (
    <RealtimeExplorationDashboard
      pageName="Moving Averages"
      showMovingAverages={true}
    />
  );
}
