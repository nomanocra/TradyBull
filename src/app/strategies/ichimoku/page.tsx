import { TradingDashboard } from '@/components/dashboard/trading-dashboard';

export default function IchimokuPage() {
  return (
    <TradingDashboard
      pageName="Ichimoku Cloud"
      showIchimoku={true}
    />
  );
}
