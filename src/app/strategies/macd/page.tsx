import { TradingDashboard } from '@/components/dashboard/trading-dashboard';

export default function MACDPage() {
  return (
    <TradingDashboard
      pageName="MACD"
      showBollinger={false}
      showMACD={true}
    />
  );
}
