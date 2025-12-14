import { HistoricalDashboard } from '@/components/dashboard/historical-dashboard';

export default function IchimokuHistoricalPage() {
  return (
    <HistoricalDashboard
      pageName="Ichimoku Cloud"
      showIchimoku={true}
    />
  );
}
