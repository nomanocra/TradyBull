import { TradingDashboard } from '@/components/dashboard/trading-dashboard';

export default function StochasticRSIPage() {
  return (
    <TradingDashboard
      pageName="Stochastic RSI"
      showRSI={true}
    />
  );
}
