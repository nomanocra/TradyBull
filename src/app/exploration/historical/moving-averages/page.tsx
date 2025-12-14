import { HistoricalDashboard } from '@/components/dashboard/historical-dashboard';

export default function MovingAveragesHistoricalPage() {
  return (
    <HistoricalDashboard
      pageName="Moving Averages"
      showMovingAverages={true}
    />
  );
}
