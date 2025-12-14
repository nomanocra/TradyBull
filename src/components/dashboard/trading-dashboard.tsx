'use client';

import { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { MemoizedCandlestickChart } from '@/components/chart/candlestick-chart';
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

interface TradingDashboardProps {
  pageName?: string;
  showBollinger?: boolean;
  showMACD?: boolean;
  showIchimoku?: boolean;
  showMovingAverages?: boolean;
  showRSI?: boolean;
  topBar?: React.ReactNode;
}

const WS_URL = 'ws://localhost:8000/ws';
const FETCH_INTERVAL = 10; // Must match backend FETCH_INTERVAL

export function TradingDashboard({
  pageName = 'MACD & Bollinger',
  showBollinger = false,
  showMACD = false,
  showIchimoku = false,
  showMovingAverages = false,
  showRSI = false,
  topBar,
}: TradingDashboardProps) {
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

  // Memoize price calculations to avoid recalculations on every render
  const { lastPrice, priceChange } = useMemo(() => {
    const last = data['1h'].length > 0 ? data['1h'][data['1h'].length - 1].close : null;
    const prev = data['1h'].length > 1 ? data['1h'][data['1h'].length - 2].close : null;
    const change = last && prev ? ((last - prev) / prev) * 100 : null;
    return { lastPrice: last, priceChange: change };
  }, [data]);

  // Get display time: use lastFetchTime from server, or fallback to last candle timestamp
  // In standby mode (weekend), also show the date
  const { displayTime, displayDate } = useMemo(() => {
    if (data['1h'].length > 0) {
      const lastCandle = data['1h'][data['1h'].length - 1];
      const date = new Date(lastCandle.time * 1000);
      const time = date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

      if (standby) {
        // Weekend: show date below time
        const dateStr = date.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
        return { displayTime: time, displayDate: dateStr };
      }

      // Normal mode: use server lastFetchTime or fallback to candle time
      return { displayTime: lastFetchTime || time, displayDate: null };
    }
    return { displayTime: lastFetchTime, displayDate: null };
  }, [lastFetchTime, data, standby]);

  return (
    <div className="h-full w-full bg-[#0a0a0a] flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-3 py-1.5 border-b border-[#1a1a1a] bg-[#0d0d0d]">
        {/* Page name - Left */}
        <div className="flex-1 flex items-center gap-3">
          <span className="text-xs font-semibold text-[#C59471]">{pageName}</span>
        </div>

        {/* Symbol and price - Center */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-400">{dataSource || 'NASDAQ'}</span>
          {lastPrice && (
            <>
              <span className="text-sm font-mono font-semibold text-white">
                {lastPrice.toFixed(2)}
              </span>
              {priceChange !== null && (
                <span className={`text-xs font-mono ${priceChange >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                  {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}%
                </span>
              )}
            </>
          )}
        </div>

        {/* Status indicators - Right */}
        <div className="flex-1 flex items-center justify-end gap-3">
          {error && (
            <span className="text-xs text-red-500">{error}</span>
          )}
          {/* Circular countdown spinner - hidden in standby mode */}
          {!standby && (
            <div className="relative w-4 h-4" title={`${countdown}s`}>
              <svg className="w-4 h-4 -rotate-90" viewBox="0 0 16 16">
                <circle
                  cx="8"
                  cy="8"
                  r="6"
                  fill="none"
                  stroke="#27272a"
                  strokeWidth="2"
                />
                <circle
                  cx="8"
                  cy="8"
                  r="6"
                  fill="none"
                  stroke="#71717a"
                  strokeWidth="2"
                  strokeDasharray={2 * Math.PI * 6}
                  strokeDashoffset={2 * Math.PI * 6 * (countdown / FETCH_INTERVAL)}
                  strokeLinecap="round"
                  className={isResetting ? '' : 'transition-all duration-1000 ease-linear'}
                />
              </svg>
            </div>
          )}
          {displayTime && (
            <div className="flex flex-col items-end leading-tight">
              <span className="text-[10px] text-gray-600 font-mono">
                {displayTime}
              </span>
              {displayDate && (
                <span className="text-[9px] text-gray-700 font-mono">
                  {displayDate}
                </span>
              )}
            </div>
          )}
          <span className={`text-[10px] font-medium ${marketOpen ? 'text-emerald-500' : 'text-gray-600'}`}>
            {marketOpen ? 'MARKET OPEN' : 'MARKET CLOSED'}
          </span>
          {/* WebSocket status indicator */}
          <div
            className={`w-1.5 h-1.5 rounded-full ${
              error ? 'bg-red-500' :
              !wsConnected ? 'bg-yellow-500 animate-pulse' :
              standby ? 'bg-gray-500' :
              marketOpen ? 'bg-emerald-500 animate-pulse' : 'bg-emerald-500'
            }`}
            title={
              error ? 'Error' :
              !wsConnected ? 'Connecting...' :
              standby ? 'Standby (Weekend)' :
              marketOpen ? 'Market Open' : 'Market Closed'
            }
          />
        </div>
      </header>

      {/* Optional top bar (e.g., indicator toggles) */}
      {topBar}

      {/* Charts Grid */}
      <div className="flex-1 flex flex-col gap-2 p-2 bg-[#0a0a0a] min-h-0">
        {/* Main Chart - 1 Hour */}
        <div className="flex-[1.2] min-h-0">
          <MemoizedCandlestickChart
            title="1H"
            timeframe="1h"
            data={data['1h']}
            isLoading={isLoading}
            showBollinger={showBollinger}
            showMACD={showMACD}
            showIchimoku={showIchimoku}
            showMovingAverages={showMovingAverages}
            showRSI={showRSI}
          />
        </div>

        {/* Bottom Row */}
        <div className="flex-1 flex gap-2 min-h-0">
          <div className="flex-1 min-w-0">
            <MemoizedCandlestickChart
              title="1D"
              timeframe="1day"
              data={data['1day']}
              isLoading={isLoading}
              showBollinger={showBollinger}
              showMACD={showMACD}
              showIchimoku={showIchimoku}
              showMovingAverages={showMovingAverages}
              showRSI={showRSI}
            />
          </div>
          <div className="flex-1 min-w-0">
            <MemoizedCandlestickChart
              title="15M"
              timeframe="15min"
              data={data['15min']}
              isLoading={isLoading}
              showBollinger={showBollinger}
              showMACD={showMACD}
              showIchimoku={showIchimoku}
              showMovingAverages={showMovingAverages}
              showRSI={showRSI}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
