'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Bot,
  Plus,
  Trash2,
  Play,
  Square,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Activity,
  AlertTriangle,
  Wallet,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { GroupButton } from '@/components/ui/group-button';
import { useBots, TradingBot, BotTrade } from '@/hooks/useBots';
import { useStrategies } from '@/hooks/useStrategies';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export default function TradyBotsPage() {
  const { bots, isLoading, createBot, deleteBot, startBot, stopBot, getBotTrades } = useBots();
  const { strategies } = useStrategies();
  // Account balance state
  const [balances, setBalances] = useState<Record<string, { available: number; total_equity: number; error?: string }>>({});

  const fetchBalances = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/etoro/balance`);
      if (res.ok) {
        const data = await res.json();
        setBalances(data.balances || {});
      }
    } catch {
      // Silent fail - balances are supplementary info
    }
  }, []);

  useEffect(() => {
    fetchBalances();
  }, [fetchBalances]);

  // Create modal state
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newBotName, setNewBotName] = useState('');
  const [newBotStrategy, setNewBotStrategy] = useState('');
  const [newBotAmount, setNewBotAmount] = useState('100');
  const [newBotLeverage, setNewBotLeverage] = useState('1');
  const [newBotAccount, setNewBotAccount] = useState('demo');
  const [newBotSignalSource, setNewBotSignalSource] = useState('yfinance');
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Delete confirmation state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingBotId, setDeletingBotId] = useState<number | null>(null);

  // Trade history state
  const [tradesModalOpen, setTradesModalOpen] = useState(false);
  const [tradesBot, setTradesBot] = useState<TradingBot | null>(null);
  const [trades, setTrades] = useState<BotTrade[]>([]);
  const [tradesLoading, setTradesLoading] = useState(false);

  const handleCreate = async () => {
    if (!newBotName || !newBotStrategy || !newBotAmount) return;
    setIsCreating(true);
    setCreateError(null);
    try {
      await createBot({
        name: newBotName,
        strategy_name: newBotStrategy,
        amount: parseFloat(newBotAmount),
        leverage: parseInt(newBotLeverage),
        account_type: newBotAccount,
        signal_source: newBotSignalSource,
      });
      setCreateModalOpen(false);
      setNewBotName('');
      setNewBotStrategy('');
      setNewBotAmount('100');
      setNewBotLeverage('1');
      setNewBotAccount('demo');
      setNewBotSignalSource('yfinance');
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create bot');
    } finally {
      setIsCreating(false);
    }
  };

  const handleToggle = async (bot: TradingBot) => {
    if (bot.enabled) {
      await stopBot(bot.id);
    } else {
      await startBot(bot.id);
    }
  };

  const handleDeleteClick = (botId: number) => {
    setDeletingBotId(botId);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (deletingBotId !== null) {
      await deleteBot(deletingBotId);
    }
    setDeleteDialogOpen(false);
    setDeletingBotId(null);
  };

  const handleViewTrades = async (bot: TradingBot) => {
    setTradesBot(bot);
    setTradesLoading(true);
    setTradesModalOpen(true);
    try {
      const botTrades = await getBotTrades(bot.id);
      setTrades(botTrades);
    } catch {
      setTrades([]);
    } finally {
      setTradesLoading(false);
    }
  };

  const getStrategyDisplayName = (strategyName: string) => {
    const strategy = strategies.find((s) => s.name === strategyName);
    return strategy?.display_name || strategyName;
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString('en-GB', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="h-full w-full bg-background flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-card">
        <div className="flex items-center gap-2">
          <Bot size={14} className="text-brand" />
          <span className="text-xs font-semibold text-brand">TradyBots</span>
        </div>
        <div className="flex items-center gap-4">
          {balances.demo && !balances.demo.error && (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] px-1.5 py-0.5 bg-blue-500/10 text-blue-500">DEMO</span>
              <Wallet size={10} className="text-muted-foreground" />
              <span className="text-[10px] text-blue-500">
                ${balances.demo.available.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
          )}
          {balances.real && !balances.real.error && (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] px-1.5 py-0.5 bg-amber-500/10 text-amber-500">REAL</span>
              <Wallet size={10} className="text-muted-foreground" />
              <span className="text-[10px] text-amber-500">
                ${balances.real.available.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
          )}
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 p-4 overflow-auto">
        {isLoading ? (
          <div className="text-center text-muted-foreground text-sm py-8">Loading...</div>
        ) : bots.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full">
            <Bot size={48} className="text-muted-foreground/30 mb-4" />
            <p className="text-sm text-muted-foreground mb-4">No trading bots configured</p>
            <Button size="sm" onClick={() => setCreateModalOpen(true)} className="h-8 text-xs">
              <Plus size={12} />
              Create your first bot
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex justify-end">
              <Button size="sm" onClick={() => setCreateModalOpen(true)} className="h-8 text-xs">
                <Plus size={12} />
                New Bot
              </Button>
            </div>

            <div className="space-y-2">
              {bots.map((bot) => (
                <div
                  key={bot.id}
                  className="flex items-center justify-between p-3 bg-card border border-border hover:border-muted-foreground/30 transition-colors"
                >
                  {/* Bot Icon */}
                  <Bot size={20} className={`mr-4 ${bot.enabled ? 'text-brand' : 'text-muted-foreground'}`} />

                  {/* Toggle (Kill Switch) */}
                  <div className="flex flex-col items-center gap-1 mr-4">
                    <span className="text-[10px] text-muted-foreground">Active</span>
                    <Switch
                      checked={!!bot.enabled}
                      onCheckedChange={() => handleToggle(bot)}
                      className="scale-75"
                    />
                  </div>

                  {/* Bot Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate">{bot.name}</span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 ${
                          bot.account_type === 'demo'
                            ? 'bg-blue-500/10 text-blue-500'
                            : 'bg-amber-500/10 text-amber-500'
                        }`}
                      >
                        {bot.account_type.toUpperCase()}
                      </span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 ${
                          bot.signal_source === 'etoro'
                            ? 'bg-emerald-500/10 text-emerald-500'
                            : 'bg-violet-500/10 text-violet-500'
                        }`}
                      >
                        {bot.signal_source === 'etoro' ? 'eToro' : 'yFinance'}
                      </span>
                      {bot.status === 'active' && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-green-500/10 text-green-500 flex items-center gap-0.5">
                          <Activity size={8} /> Running
                        </span>
                      )}
                      {bot.status === 'error' && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-red-500/10 text-red-500 flex items-center gap-0.5">
                          <AlertTriangle size={8} /> Error
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-[10px] text-muted-foreground">
                        Strategy: {getStrategyDisplayName(bot.strategy_name)}
                      </span>
                      <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
                        <DollarSign size={9} />{bot.amount}{bot.leverage > 1 && ` x${bot.leverage}`}
                      </span>
                      {bot.stats && (
                        <>
                          <span className="text-[10px] text-muted-foreground">
                            Trades: {bot.stats.total_trades}
                          </span>
                          <span
                            className={`text-[10px] font-medium ${
                              bot.stats.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'
                            }`}
                          >
                            P&L: {bot.stats.total_pnl >= 0 ? '+' : ''}$
                            {Math.abs(bot.stats.total_pnl).toFixed(2)}
                          </span>
                          {bot.stats.open_positions > 0 && (
                            <>
                              <span className="text-[10px] text-brand">
                                {bot.stats.open_positions} open
                              </span>
                              {bot.stats.live_pnl !== null && (
                                <span className={`text-[10px] italic ${bot.stats.live_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                  {bot.stats.live_pnl >= 0 ? '+' : '-'}${Math.abs(bot.stats.live_pnl).toFixed(2)} live
                                </span>
                              )}
                            </>
                          )}
                        </>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 ml-3">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleViewTrades(bot)}
                      className="h-7 w-7 p-0"
                      title="View trades"
                    >
                      <Activity size={12} />
                    </Button>
                    {bot.enabled ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => stopBot(bot.id)}
                        className="h-7 w-7 p-0 text-red-500 hover:text-red-600 hover:bg-red-500/10"
                        title="Stop bot"
                      >
                        <Square size={12} />
                      </Button>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => startBot(bot.id)}
                        className="h-7 w-7 p-0 text-green-500 hover:text-green-600 hover:bg-green-500/10"
                        title="Start bot"
                      >
                        <Play size={12} />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteClick(bot.id)}
                      className="h-7 w-7 p-0 text-red-500 hover:text-red-600 hover:bg-red-500/10"
                      title="Delete bot"
                    >
                      <Trash2 size={12} />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Create Bot Modal */}
      <Dialog open={createModalOpen} onOpenChange={(open) => { setCreateModalOpen(open); if (!open) setCreateError(null); }}>
        <DialogContent className="sm:max-w-[420px]">
          <DialogHeader>
            <DialogTitle className="text-sm">Create Trading Bot</DialogTitle>
            <DialogDescription className="text-xs">
              Configure a new bot that will automatically trade based on strategy signals.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">Bot Name</label>
              <Input
                value={newBotName}
                onChange={(e) => setNewBotName(e.target.value)}
                placeholder="My Trading Bot"
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">Strategy</label>
              <Select value={newBotStrategy} onValueChange={setNewBotStrategy}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Select a strategy" />
                </SelectTrigger>
                <SelectContent>
                  {strategies.map((s) => (
                    <SelectItem key={s.name} value={s.name} className="text-xs">
                      {s.display_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground block">Account Type</label>
              <GroupButton
                options={[
                  { value: 'demo', label: 'Demo' },
                  { value: 'real', label: 'Real' },
                ]}
                value={newBotAccount}
                onChange={setNewBotAccount}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground block">Signal Source</label>
              <GroupButton
                options={[
                  { value: 'yfinance', label: 'yFinance' },
                  { value: 'etoro', label: 'eToro' },
                ]}
                value={newBotSignalSource}
                onChange={setNewBotSignalSource}
              />
              <p className="text-[10px] text-muted-foreground">
                {newBotSignalSource === 'yfinance'
                  ? 'Signals based on yFinance data (slight delay, backtested)'
                  : 'Signals based on eToro real-time data (no delay)'}
              </p>
            </div>
            <div className="space-y-1.5">
              <div className="flex gap-3">
                <div className="flex-1 space-y-1.5">
                  <label className="text-xs text-muted-foreground">Amount per trade ($)</label>
                  <Input
                    type="number"
                    value={newBotAmount}
                    onChange={(e) => setNewBotAmount(e.target.value)}
                    placeholder="100"
                    min="10"
                    className="h-8 text-xs"
                  />
                </div>
                <div className="w-24 space-y-1.5">
                  <label className="text-xs text-muted-foreground">Leverage</label>
                  <Select value={newBotLeverage} onValueChange={setNewBotLeverage}>
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1" className="text-xs">x1</SelectItem>
                      <SelectItem value="2" className="text-xs">x2</SelectItem>
                      <SelectItem value="5" className="text-xs">x5</SelectItem>
                      <SelectItem value="10" className="text-xs">x10</SelectItem>
                      <SelectItem value="20" className="text-xs">x20</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              {balances[newBotAccount] && !balances[newBotAccount].error && (
                <div className="flex items-center gap-1.5 pt-0.5">
                  <Wallet size={10} className="text-muted-foreground" />
                  <span className="text-[10px] text-muted-foreground">Available:</span>
                  <span className={`text-[10px] ${newBotAccount === 'demo' ? 'text-blue-500' : 'text-amber-500'}`}>
                    ${balances[newBotAccount].available.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>
              )}
            </div>
          </div>
          {createError && (
            <p className="text-xs text-red-500 px-1">{createError}</p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateModalOpen(false)} className="h-8 text-xs">
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={isCreating || !newBotName || !newBotStrategy || !newBotAmount}
              className="h-8 text-xs"
            >
              {isCreating ? 'Creating...' : 'Create Bot'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Trade History Modal */}
      <Dialog open={tradesModalOpen} onOpenChange={setTradesModalOpen}>
        <DialogContent className="sm:max-w-[600px] max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="text-sm">
              Trade History - {tradesBot?.name}
            </DialogTitle>
            <DialogDescription className="text-xs">
              {tradesBot && `Strategy: ${getStrategyDisplayName(tradesBot.strategy_name)} | Account: ${tradesBot.account_type.toUpperCase()}`}
            </DialogDescription>
          </DialogHeader>
          <div className="overflow-auto max-h-[50vh]">
            {tradesLoading ? (
              <div className="text-center text-muted-foreground text-sm py-8">Loading...</div>
            ) : trades.length === 0 ? (
              <div className="text-center text-muted-foreground text-sm py-8">No trades yet</div>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-2 text-muted-foreground font-medium">Type</th>
                    <th className="text-left py-2 px-2 text-muted-foreground font-medium">Price</th>
                    <th className="text-left py-2 px-2 text-muted-foreground font-medium">Amount</th>
                    <th className="text-left py-2 px-2 text-muted-foreground font-medium">P&L</th>
                    <th className="text-left py-2 px-2 text-muted-foreground font-medium">Status</th>
                    <th className="text-left py-2 px-2 text-muted-foreground font-medium">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((trade) => (
                    <tr key={trade.id} className="border-b border-border/50 hover:bg-muted/30">
                      <td className="py-1.5 px-2">
                        <span className={`flex items-center gap-1 ${trade.signal_type === 'buy' ? 'text-green-500' : 'text-red-500'}`}>
                          {trade.signal_type === 'buy' ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                          {trade.signal_type.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-1.5 px-2">{trade.price.toFixed(2)}</td>
                      <td className="py-1.5 px-2">${trade.amount}</td>
                      <td className="py-1.5 px-2">
                        {trade.status === 'open' && trade.live_pnl !== null ? (
                          <span className={`italic ${trade.live_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {trade.live_pnl >= 0 ? '+' : '-'}${Math.abs(trade.live_pnl).toFixed(2)}
                            <span className="text-[9px] ml-1 opacity-60">live</span>
                          </span>
                        ) : trade.pnl !== null ? (
                          <span className={trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                            {trade.pnl >= 0 ? '+' : '-'}${Math.abs(trade.pnl).toFixed(2)}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </td>
                      <td className="py-1.5 px-2">
                        <span
                          className={`text-[10px] px-1 py-0.5 ${
                            trade.status === 'open'
                              ? 'bg-blue-500/10 text-blue-500'
                              : trade.status === 'closed'
                              ? 'bg-muted text-muted-foreground'
                              : 'bg-red-500/10 text-red-500'
                          }`}
                        >
                          {trade.status}
                        </span>
                      </td>
                      <td className="py-1.5 px-2 text-muted-foreground">{formatDate(trade.opened_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="text-sm">Delete Bot</AlertDialogTitle>
            <AlertDialogDescription className="text-xs">
              Are you sure you want to delete this bot? All trade history will be lost. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="h-8 text-xs">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className="h-8 text-xs bg-red-500 hover:bg-red-600"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
