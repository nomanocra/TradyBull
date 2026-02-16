'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Wallet } from 'lucide-react';
import { Button } from '@/components/ui/button';
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
import { GroupButton } from '@/components/ui/group-button';
import { useBots } from '@/hooks/useBots';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

interface Strategy {
  name: string;
  display_name: string;
}

interface BotCreateModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  strategies: Strategy[];
  defaultStrategy?: string | null;
  onCreated?: () => void;
}

export function BotCreateModal({ open, onOpenChange, strategies, defaultStrategy, onCreated }: BotCreateModalProps) {
  const { createBot } = useBots();
  const router = useRouter();

  const [name, setName] = useState('');
  const [strategy, setStrategy] = useState('');
  const [amount, setAmount] = useState('100');
  const [leverage, setLeverage] = useState('1');
  const [account, setAccount] = useState('demo');
  const [signalSource, setSignalSource] = useState('yfinance');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [balances, setBalances] = useState<Record<string, { available: number; total_equity: number; error?: string }>>({});

  const fetchBalances = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/etoro/balance`);
      if (res.ok) {
        const data = await res.json();
        setBalances(data.balances || {});
      }
    } catch {
      // Silent fail
    }
  }, []);

  // Fetch balances when modal opens
  useEffect(() => {
    if (open) fetchBalances();
  }, [open, fetchBalances]);

  // Set default strategy when modal opens
  useEffect(() => {
    if (open && defaultStrategy) {
      setStrategy(defaultStrategy);
    }
  }, [open, defaultStrategy]);

  // Reset form when modal closes
  useEffect(() => {
    if (!open) {
      setName('');
      setStrategy('');
      setAmount('100');
      setLeverage('1');
      setAccount('demo');
      setSignalSource('yfinance');
      setError(null);
    }
  }, [open]);

  const handleCreate = async () => {
    if (!name || !strategy || !amount) return;
    setIsCreating(true);
    setError(null);
    try {
      await createBot({
        name,
        strategy_name: strategy,
        amount: parseFloat(amount),
        leverage: parseInt(leverage),
        account_type: account,
        signal_source: signalSource,
      });
      onOpenChange(false);
      onCreated?.();
      router.push('/strategy/real-time/tradybots');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create bot');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) setError(null); }}>
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
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Trading Bot"
              className="h-8 text-xs"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Strategy</label>
            <Select value={strategy} onValueChange={setStrategy}>
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
              value={account}
              onChange={setAccount}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground block">Signal Source</label>
            <GroupButton
              options={[
                { value: 'yfinance', label: 'yFinance' },
                { value: 'etoro', label: 'eToro' },
              ]}
              value={signalSource}
              onChange={setSignalSource}
            />
            <p className="text-[10px] text-muted-foreground">
              {signalSource === 'yfinance'
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
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="100"
                  min="10"
                  className="h-8 text-xs"
                />
              </div>
              <div className="w-24 space-y-1.5">
                <label className="text-xs text-muted-foreground">Leverage</label>
                <Select value={leverage} onValueChange={setLeverage}>
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
            {balances[account] && !balances[account].error && (
              <div className="flex items-center gap-1.5 pt-0.5">
                <Wallet size={10} className="text-muted-foreground" />
                <span className="text-[10px] text-muted-foreground">Available:</span>
                <span className={`text-[10px] ${account === 'demo' ? 'text-blue-500' : 'text-amber-500'}`}>
                  ${balances[account].available.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
            )}
          </div>
        </div>
        {error && (
          <p className="text-xs text-red-500 px-1">{error}</p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} className="h-8 text-xs">
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={isCreating || !name || !strategy || !amount}
            className="h-8 text-xs"
          >
            {isCreating ? 'Creating...' : 'Create Bot'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
