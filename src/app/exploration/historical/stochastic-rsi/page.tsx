import { HistoricalDashboard } from '@/components/dashboard/historical-dashboard';

export default function StochasticRSIHistoricalPage() {
  return (
    <HistoricalDashboard
      pageName="Stochastic RSI"
      showRSI={true}
    />
  );
}
