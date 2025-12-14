import { TradingDashboard } from '@/components/dashboard/trading-dashboard';

export default function MACDRealTimePage() {
  return (
    <TradingDashboard
      pageName="MACD"
      showMACD={true}
    />
  );
}
