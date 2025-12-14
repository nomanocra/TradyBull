import { TradingDashboard } from '@/components/dashboard/trading-dashboard';

export default function StochasticRSIRealTimePage() {
  return (
    <TradingDashboard
      pageName="Stochastic RSI"
      showRSI={true}
    />
  );
}
