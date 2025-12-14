import { TradingDashboard } from '@/components/dashboard/trading-dashboard';

export default function BollingerRealTimePage() {
  return (
    <TradingDashboard
      pageName="Bollinger Bands"
      showBollinger={true}
    />
  );
}
