import { useState, useEffect, useCallback } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export interface BotStats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  total_pnl: number;
  avg_pnl: number;
  best_trade: number;
  worst_trade: number;
  open_positions: number;
  live_pnl: number | null;
}

export interface TradingBot {
  id: number;
  name: string;
  strategy_name: string;
  etoro_instrument_id: number;
  amount: number;
  leverage: number;
  account_type: 'demo' | 'real';
  signal_source: 'yfinance' | 'etoro';
  enabled: number;
  status: 'active' | 'stopped' | 'error';
  created_at: number;
  updated_at: number;
  stats: BotStats;
}

export interface BotTrade {
  id: number;
  bot_id: number;
  position_id: number | null;
  signal_type: 'buy' | 'sell';
  price: number;
  amount: number;
  status: 'open' | 'closed' | 'error';
  opened_at: number;
  closed_at: number | null;
  pnl: number | null;
  live_pnl: number | null;
  error_message: string | null;
  bot_name?: string;
  strategy_name?: string;
}

interface CreateBotParams {
  name: string;
  strategy_name: string;
  amount: number;
  leverage: number;
  account_type: string;
  signal_source: string;
}

export function useBots() {
  const [bots, setBots] = useState<TradingBot[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBots = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/bots`);
      if (!response.ok) throw new Error('Failed to fetch bots');
      const data = await response.json();
      setBots(data.bots || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch bots');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBots();
    // Poll every 10 seconds for status updates
    const interval = setInterval(fetchBots, 10000);
    return () => clearInterval(interval);
  }, [fetchBots]);

  const createBot = useCallback(async (params: CreateBotParams) => {
    const response = await fetch(`${API_URL}/bots`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Failed to create bot');
    }
    const data = await response.json();
    await fetchBots();
    return data.bot;
  }, [fetchBots]);

  const deleteBot = useCallback(async (botId: number) => {
    const response = await fetch(`${API_URL}/bots/${botId}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete bot');
    await fetchBots();
  }, [fetchBots]);

  const startBot = useCallback(async (botId: number) => {
    const response = await fetch(`${API_URL}/bots/${botId}/start`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to start bot');
    await fetchBots();
  }, [fetchBots]);

  const stopBot = useCallback(async (botId: number) => {
    const response = await fetch(`${API_URL}/bots/${botId}/stop`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to stop bot');
    await fetchBots();
  }, [fetchBots]);

  const getBotTrades = useCallback(async (botId: number, limit = 50): Promise<BotTrade[]> => {
    const response = await fetch(`${API_URL}/bots/${botId}/trades?limit=${limit}`);
    if (!response.ok) throw new Error('Failed to fetch trades');
    const data = await response.json();
    return data.trades || [];
  }, []);

  return {
    bots,
    isLoading,
    error,
    refetch: fetchBots,
    createBot,
    deleteBot,
    startBot,
    stopBot,
    getBotTrades,
  };
}
