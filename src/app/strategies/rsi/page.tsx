import { TradingDashboard } from '@/components/dashboard/trading-dashboard';

export default function RSIPage() {
  return (
    <TradingDashboard
      pageName="RSI"
      showRSI={true}
    />
  );
}
