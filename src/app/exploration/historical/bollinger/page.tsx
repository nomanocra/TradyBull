import { HistoricalDashboard } from '@/components/dashboard/historical-dashboard';

export default function BollingerHistoricalPage() {
  return (
    <HistoricalDashboard
      pageName="Bollinger Bands"
      showBollinger={true}
    />
  );
}
