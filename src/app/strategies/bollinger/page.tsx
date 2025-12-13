import { TradingDashboard } from '@/components/dashboard/trading-dashboard';

export default function BollingerPage() {
  return (
    <TradingDashboard
      pageName="Bollinger Bands"
      showBollinger={true}
      enableSignalsToggle={true}
      defaultSignalsEnabled={true}
    />
  );
}
