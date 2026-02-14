import { HistoricalProvider } from '@/contexts/historical-context';

export default function StrategyBacktestingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <HistoricalProvider>{children}</HistoricalProvider>;
}
