import { HistoricalProvider } from '@/app/exploration/historical/historical-context';

export default function StrategyBacktestingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <HistoricalProvider>{children}</HistoricalProvider>;
}
