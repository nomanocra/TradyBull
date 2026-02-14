import { RealtimeProvider } from '@/contexts/realtime-context';

export default function StrategyRealtimeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <RealtimeProvider>{children}</RealtimeProvider>;
}
