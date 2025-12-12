import { TradingDashboard } from '@/components/dashboard/trading-dashboard';

export default function MovingAveragesPage() {
  return (
    <TradingDashboard
      pageName="Moving Averages"
      showMovingAverages={true}
    />
  );
}
