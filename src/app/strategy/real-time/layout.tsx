import { RealtimeProvider } from '@/app/exploration/real-time/realtime-context';

export default function StrategyRealtimeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <RealtimeProvider>{children}</RealtimeProvider>;
}
