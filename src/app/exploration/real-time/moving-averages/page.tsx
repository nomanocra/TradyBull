import { TradingDashboard } from '@/components/dashboard/trading-dashboard';

export default function MovingAveragesRealTimePage() {
  return (
    <TradingDashboard
      pageName="Moving Averages"
      showMovingAverages={true}
    />
  );
}
