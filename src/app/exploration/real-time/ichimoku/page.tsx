import { TradingDashboard } from '@/components/dashboard/trading-dashboard';

export default function IchimokuRealTimePage() {
  return (
    <TradingDashboard
      pageName="Ichimoku Cloud"
      showIchimoku={true}
    />
  );
}
