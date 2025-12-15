'use client';

import { createContext, useContext, useState, useEffect, useRef, useCallback, ReactNode } from 'react';
import { CandleData } from '@/types/market';

interface ChartData {
  '1h': CandleData[];
  '1day': CandleData[];
  '15min': CandleData[];
}

interface WebSocketMessage {
  type: string;
  symbol: string;
  market_open: boolean;
  standby: boolean;
  last_fetch: string | null;
  data: {
    '15min': CandleData[];
    '1h': CandleData[];
    '1day': CandleData[];
  };
}

interface RealtimeContextValue {
  data: ChartData;
  isLoading: boolean;
  error: string | null;
  lastFetchTime: string | null;
  marketOpen: boolean;
  standby: boolean;
  dataSource: string;
  countdown: number;
  isResetting: boolean;
  wsConnected: boolean;
}

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

const WS_URL = 'ws://localhost:8000/ws';
const FETCH_INTERVAL = 10;

export function useRealtimeData() {
  const context = useContext(RealtimeContext);
  if (!context) {
    throw new Error('useRealtimeData must be used within RealtimeProvider');
  }
  return context;
}

interface RealtimeProviderProps {
  children: ReactNode;
}

export function RealtimeProvider({ children }: RealtimeProviderProps) {
  const [data, setData] = useState<ChartData>({
    '1h': [],
    '1day': [],
    '15min': [],
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetchTime, setLastFetchTime] = useState<string | null>(null);
  const [marketOpen, setMarketOpen] = useState(false);
  const [standby, setStandby] = useState(false);
  const [dataSource, setDataSource] = useState<string>('');
  const [countdown, setCountdown] = useState(FETCH_INTERVAL);
  const [isResetting, setIsResetting] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastFetchRef = useRef<string | null>(null);
  const isClosingRef = useRef(false);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);

      if (message.type === 'data_update') {
        setData({
          '1h': message.data['1h'] || [],
          '1day': message.data['1day'] || [],
          '15min': message.data['15min'] || [],
        });
        setMarketOpen(message.market_open);
        setStandby(message.standby || false);
        setDataSource(message.symbol);
        setError(null);
        setLastFetchTime(message.last_fetch);
        setIsLoading(false);

        // Sync countdown with server's last_fetch time
        if (message.last_fetch) {
          lastFetchRef.current = message.last_fetch;

          // Parse last_fetch time (format: "HH:MM:SS")
          const [hours, minutes, seconds] = message.last_fetch.split(':').map(Number);
          const now = new Date();
          const lastFetchDate = new Date();
          lastFetchDate.setHours(hours, minutes, seconds, 0);

          // Calculate seconds elapsed since last fetch
          const elapsedSeconds = Math.floor((now.getTime() - lastFetchDate.getTime()) / 1000);
          const remaining = Math.max(0, FETCH_INTERVAL - elapsedSeconds);

          setIsResetting(true);
          setCountdown(remaining);
          setTimeout(() => setIsResetting(false), 50);
        }
      }
    } catch (err) {
      console.error('Error parsing WebSocket message:', err);
    }
  }, []);

  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    isClosingRef.current = false;
    console.log('[WS] Connecting...');
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log('[WS] Connected');
      setWsConnected(true);
      setError(null);
    };

    ws.onmessage = handleMessage;

    ws.onclose = () => {
      setWsConnected(false);
      wsRef.current = null;

      // Only reconnect if not intentionally closing
      if (!isClosingRef.current) {
        console.log('[WS] Disconnected, reconnecting...');
        reconnectTimeoutRef.current = setTimeout(() => {
          connectWebSocket();
        }, 2000);
      }
    };

    ws.onerror = () => {
      // Silent error - connection errors are handled by onclose with reconnect
    };

    wsRef.current = ws;
  }, [handleMessage]);

  useEffect(() => {
    connectWebSocket();

    // Countdown timer (every second)
    const countdownId = setInterval(() => {
      setCountdown((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);

    return () => {
      clearInterval(countdownId);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        isClosingRef.current = true;
        wsRef.current.close();
      }
    };
  }, [connectWebSocket]);

  const value: RealtimeContextValue = {
    data,
    isLoading,
    error,
    lastFetchTime,
    marketOpen,
    standby,
    dataSource,
    countdown,
    isResetting,
    wsConnected,
  };

  return (
    <RealtimeContext.Provider value={value}>
      {children}
    </RealtimeContext.Provider>
  );
}
