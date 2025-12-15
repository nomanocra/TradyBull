import { RealtimeProvider } from './realtime-context';

export default function RealtimeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <RealtimeProvider>{children}</RealtimeProvider>;
}
