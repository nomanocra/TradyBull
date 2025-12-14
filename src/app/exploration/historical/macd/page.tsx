import { HistoricalDashboard } from '@/components/dashboard/historical-dashboard';

export default function MACDHistoricalPage() {
  return (
    <HistoricalDashboard
      pageName="MACD"
      showMACD={true}
    />
  );
}
