'use client';

import { createContext, useContext, useState, useEffect, useRef, useCallback, ReactNode } from 'react';
import { CandleData, Signal } from '@/types/market';

const API_URL = 'http://localhost:8000/api';

interface NotificationSettings {
  strategy_name: string;
  enabled: boolean;
  desktop_enabled: boolean;
  notify_buy: boolean;
  notify_sell: boolean;
  time_start: string;
  time_end: string;
}

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
  signals?: Record<string, Signal[]>;
}

// Type for signals organized by strategy
type SignalsByStrategy = Record<string, Signal[]>;

interface RealtimeContextValue {
  data: ChartData;
  signals: SignalsByStrategy;
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
  const [signals, setSignals] = useState<SignalsByStrategy>({});
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

  // Notification tracking
  const notifiedSignalsRef = useRef<Set<string>>(new Set());
  const notificationSettingsRef = useRef<NotificationSettings[]>([]);
  const previousSignalsRef = useRef<SignalsByStrategy>({});

  // Check if current time is within notification window
  const isWithinTimeWindow = useCallback((timeStart: string, timeEnd: string): boolean => {
    const now = new Date();
    const currentTime = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false });

    if (timeStart <= timeEnd) {
      return currentTime >= timeStart && currentTime <= timeEnd;
    } else {
      // Overnight window (e.g., 22:00 - 06:00)
      return currentTime >= timeStart || currentTime <= timeEnd;
    }
  }, []);

  // Show desktop notification for a signal
  const showDesktopNotification = useCallback((strategyName: string, signal: Signal) => {
    if (!('Notification' in window) || Notification.permission !== 'granted') {
      return;
    }

    const emoji = signal.type === 'buy' ? '🟢' : '🔴';
    const action = signal.type === 'buy' ? 'BUY' : 'SELL';
    const price = signal.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    // Format strategy name for display
    const displayName = strategyName
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');

    try {
      const notification = new Notification(`${emoji} ${action} Signal - TradyBull`, {
        body: `${displayName}\nPrice: ${price}`,
        icon: '/logo.svg',
        tag: `tradybull-${strategyName}-${signal.time}`,
        requireInteraction: false,
      });

      // Auto-close after 10 seconds
      setTimeout(() => notification.close(), 10000);
    } catch (err) {
      console.error('Failed to show notification:', err);
    }
  }, []);

  // Check for new signals and trigger notifications
  const checkAndNotifyNewSignals = useCallback((newSignals: SignalsByStrategy) => {
    const settings = notificationSettingsRef.current;

    for (const [strategyName, signals] of Object.entries(newSignals)) {
      // Find settings for this strategy
      const strategySettings = settings.find(s => s.strategy_name === strategyName);
      if (!strategySettings || !strategySettings.enabled || !strategySettings.desktop_enabled) {
        continue;
      }

      // Check time window
      if (!isWithinTimeWindow(strategySettings.time_start, strategySettings.time_end)) {
        continue;
      }

      // Get previous signals for this strategy
      const previousStrategySignals = previousSignalsRef.current[strategyName] || [];
      const previousTimestamps = new Set(previousStrategySignals.map(s => `${s.time}-${s.type}`));

      // Find new signals
      for (const signal of signals) {
        const signalKey = `${strategyName}-${signal.time}-${signal.type}`;
        const isNew = !previousTimestamps.has(`${signal.time}-${signal.type}`);
        const alreadyNotified = notifiedSignalsRef.current.has(signalKey);

        if (isNew && !alreadyNotified) {
          // Check signal type filter
          if (signal.type === 'buy' && !strategySettings.notify_buy) continue;
          if (signal.type === 'sell' && !strategySettings.notify_sell) continue;

          // Show notification
          showDesktopNotification(strategyName, signal);
          notifiedSignalsRef.current.add(signalKey);
        }
      }
    }

    // Update previous signals ref
    previousSignalsRef.current = newSignals;
  }, [isWithinTimeWindow, showDesktopNotification]);

  // Fetch notification settings
  const fetchNotificationSettings = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/notifications/settings`);
      if (response.ok) {
        const data = await response.json();
        notificationSettingsRef.current = (data.settings || []).map((s: NotificationSettings) => ({
          ...s,
          enabled: Boolean(s.enabled),
          desktop_enabled: Boolean(s.desktop_enabled),
          notify_buy: Boolean(s.notify_buy),
          notify_sell: Boolean(s.notify_sell),
        }));
      }
    } catch (err) {
      console.error('Failed to fetch notification settings:', err);
    }
  }, []);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);

      if (message.type === 'data_update') {
        setData({
          '1h': message.data['1h'] || [],
          '1day': message.data['1day'] || [],
          '15min': message.data['15min'] || [],
        });
        // Update signals from WebSocket
        if (message.signals) {
          // Check for new signals and trigger desktop notifications
          checkAndNotifyNewSignals(message.signals);
          setSignals(message.signals);
        }
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
  }, [checkAndNotifyNewSignals]);

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

  // Fetch notification settings on mount and periodically
  useEffect(() => {
    fetchNotificationSettings();

    // Refresh settings every 30 seconds to pick up changes
    const intervalId = setInterval(fetchNotificationSettings, 30000);

    return () => clearInterval(intervalId);
  }, [fetchNotificationSettings]);

  const value: RealtimeContextValue = {
    data,
    signals,
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
