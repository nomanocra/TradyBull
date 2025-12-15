import { HistoricalProvider } from './historical-context';

export default function HistoricalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <HistoricalProvider>{children}</HistoricalProvider>;
}
