'use client';

import { useState, useMemo, useEffect } from 'react';
import { Plus, Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { GroupButton } from '@/components/ui/group-button';

interface StrategyConfig {
  indicator?: {
    type: string;
    mode: 'both' | 'buy' | 'sell';
  } | null;
  stop_loss?: number | null;
  ma_trend?: number | null;
  value_above_ma?: number | null;
  ma_cross?: {
    fast: number;
    slow: number;
  } | null;
  intraday: string;
  time_constraint?: {
    open: string;
    close: string;
  } | null;
}

interface StrategyCreationModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: () => void;
}

const INDICATORS = [
  { value: 'none', label: 'None' },
  { value: 'bollinger', label: 'Bollinger' },
  { value: 'macd-cross', label: 'MACD Cross' },
  { value: 'macd-zero', label: 'MACD Zero' },
  { value: 'macd-histogram', label: 'MACD Hist' },
  { value: 'ichimoku-kumo', label: 'Ichi Kumo' },
  { value: 'ichimoku-tk', label: 'Ichi TK' },
];


const STOP_LOSSES = [
  { value: 'none', label: 'None' },
  { value: '0.5', label: '0.5%' },
  { value: '0.8', label: '0.8%' },
  { value: '1', label: '1%' },
  { value: '1.5', label: '1.5%' },
  { value: '2', label: '2%' },
  { value: '2.5', label: '2.5%' },
  { value: '5', label: '5%' },
];

const MA_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: '50', label: '50' },
  { value: '100', label: '100' },
  { value: '150', label: '150' },
  { value: '200', label: '200' },
];

const INTRADAY_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'daily', label: 'Daily' },
  { value: 'multi-daily', label: 'Multi-D' },
];

function generateStrategyName(config: StrategyConfig): string {
  const parts: string[] = [];

  // Indicator
  if (config.indicator) {
    const indType = config.indicator.type;
    const mode = config.indicator.mode;
    const modeSuffix = mode === 'both' ? '' : `-${mode[0].toUpperCase()}`;
    parts.push(`${indType}${modeSuffix}`);
  }

  // Stop loss
  if (config.stop_loss) {
    parts.push(`sl${config.stop_loss}`.replace('.', ''));
  }

  // MA Trend
  if (config.ma_trend) {
    parts.push(`trend${config.ma_trend}`);
  }

  // Value above MA
  if (config.value_above_ma) {
    parts.push(`above${config.value_above_ma}`);
  }

  // MA Cross
  if (config.ma_cross) {
    parts.push(`cross${config.ma_cross.fast}-${config.ma_cross.slow}`);
  }

  // Intraday
  if (config.intraday === 'daily') {
    parts.push('daily');
  } else if (config.intraday === 'multi-daily') {
    parts.push('multid');
  }

  // Time constraint
  if (config.time_constraint) {
    const openH = config.time_constraint.open.split(':')[0];
    const closeH = config.time_constraint.close.split(':')[0];
    parts.push(`h${openH}-${closeH}`);
  }

  if (!parts.length) {
    parts.push('default');
  }

  return parts.join('-').toLowerCase();
}

function generateDisplayName(config: StrategyConfig): string {
  const parts: string[] = [];

  // Indicator
  if (config.indicator) {
    let indType = config.indicator.type.replace(/-/g, ' ');
    indType = indType.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    const mode = config.indicator.mode;
    if (mode === 'buy') {
      indType += ' (B)';
    } else if (mode === 'sell') {
      indType += ' (S)';
    }
    parts.push(indType);
  }

  // Stop loss
  if (config.stop_loss) {
    parts.push(`SL${config.stop_loss}%`);
  }

  // MA Trend
  if (config.ma_trend) {
    parts.push(`Trend${config.ma_trend}`);
  }

  // Value above MA
  if (config.value_above_ma) {
    parts.push(`>MA${config.value_above_ma}`);
  }

  // MA Cross
  if (config.ma_cross) {
    parts.push(`X${config.ma_cross.fast}/${config.ma_cross.slow}`);
  }

  // Intraday
  if (config.intraday === 'daily') {
    parts.push('Daily');
  } else if (config.intraday === 'multi-daily') {
    parts.push('MultiD');
  }

  // Time constraint
  if (config.time_constraint) {
    parts.push(`${config.time_constraint.open}-${config.time_constraint.close}`);
  }

  if (!parts.length) {
    return 'Default Strategy';
  }

  return parts.join(' ');
}

export function StrategyCreationModal({
  open,
  onOpenChange,
  onCreated,
}: StrategyCreationModalProps) {
  // Form state
  const [indicator, setIndicator] = useState('none');
  const [indicatorBuy, setIndicatorBuy] = useState(true);
  const [indicatorSell, setIndicatorSell] = useState(true);
  const [stopLoss, setStopLoss] = useState('none');
  const [maTrend, setMaTrend] = useState('none');
  const [valueAboveMa, setValueAboveMa] = useState('none');
  const [maCrossEnabled, setMaCrossEnabled] = useState(false);
  const [maCrossFast, setMaCrossFast] = useState('50');
  const [maCrossSlow, setMaCrossSlow] = useState('200');
  const [intraday, setIntraday] = useState('none');
  const [timeConstraintEnabled, setTimeConstraintEnabled] = useState(false);
  const [timeOpen, setTimeOpen] = useState('07');
  const [timeClose, setTimeClose] = useState('22');

  // Loading state
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form when modal opens
  useEffect(() => {
    if (open) {
      setIndicator('none');
      setIndicatorBuy(true);
      setIndicatorSell(true);
      setStopLoss('none');
      setMaTrend('none');
      setValueAboveMa('none');
      setMaCrossEnabled(false);
      setMaCrossFast('50');
      setMaCrossSlow('200');
      setIntraday('none');
      setTimeConstraintEnabled(false);
      setTimeOpen('07');
      setTimeClose('22');
      setError(null);
    }
  }, [open]);

  // Derive indicator mode from checkboxes
  const indicatorMode = useMemo<'both' | 'buy' | 'sell'>(() => {
    if (indicatorBuy && indicatorSell) return 'both';
    if (indicatorBuy) return 'buy';
    return 'sell';
  }, [indicatorBuy, indicatorSell]);

  // Build config from form state
  const config = useMemo<StrategyConfig>(() => {
    return {
      indicator: indicator !== 'none' && (indicatorBuy || indicatorSell) ? { type: indicator, mode: indicatorMode } : null,
      stop_loss: stopLoss !== 'none' ? parseFloat(stopLoss) : null,
      ma_trend: maTrend !== 'none' ? parseInt(maTrend) : null,
      value_above_ma: valueAboveMa !== 'none' ? parseInt(valueAboveMa) : null,
      ma_cross: maCrossEnabled ? { fast: parseInt(maCrossFast), slow: parseInt(maCrossSlow) } : null,
      intraday,
      time_constraint: timeConstraintEnabled
        ? { open: `${timeOpen}:00`, close: `${timeClose}:00` }
        : null,
    };
  }, [indicator, indicatorBuy, indicatorSell, indicatorMode, stopLoss, maTrend, valueAboveMa, maCrossEnabled, maCrossFast, maCrossSlow, intraday, timeConstraintEnabled, timeOpen, timeClose]);

  const generatedName = useMemo(() => generateStrategyName(config), [config]);
  const generatedDisplayName = useMemo(() => generateDisplayName(config), [config]);

  // Validate MA cross
  const maCrossError = useMemo(() => {
    if (!maCrossEnabled) return null;
    const fast = parseInt(maCrossFast);
    const slow = parseInt(maCrossSlow);
    if (fast >= slow) {
      return 'Fast MA must be less than Slow MA';
    }
    return null;
  }, [maCrossEnabled, maCrossFast, maCrossSlow]);

  // Check if strategy has at least one meaningful config
  const isValidConfig = useMemo(() => {
    return (
      config.indicator !== null ||
      config.stop_loss !== null ||
      config.ma_trend !== null ||
      config.value_above_ma !== null ||
      config.ma_cross !== null ||
      config.intraday !== 'none' ||
      config.time_constraint !== null
    );
  }, [config]);

  const handleCreate = async () => {
    if (!isValidConfig || maCrossError) return;

    setIsCreating(true);
    setError(null);

    try {
      // Build API payload
      const payload: Record<string, unknown> = {};

      if (config.indicator) {
        payload.indicator = config.indicator;
      }
      if (config.stop_loss !== null) {
        payload.stop_loss = config.stop_loss;
      }
      if (config.ma_trend !== null) {
        payload.ma_trend = config.ma_trend;
      }
      if (config.value_above_ma !== null) {
        payload.value_above_ma = config.value_above_ma;
      }
      if (config.ma_cross) {
        payload.ma_cross = config.ma_cross;
      }
      if (config.intraday !== 'none') {
        payload.intraday = config.intraday;
      }
      if (config.time_constraint) {
        payload.time_constraint = config.time_constraint;
      }

      const response = await fetch('http://localhost:8000/api/strategies/dynamic', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create strategy');
      }

      onOpenChange(false);
      onCreated?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create strategy');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[550px]">
        <DialogHeader>
          <DialogTitle>Create Strategy</DialogTitle>
          <DialogDescription>
            Configure your custom trading strategy parameters.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Preview Name */}
          <div className="p-3 bg-muted/50 border">
            <div className="text-xs text-muted-foreground mb-1">Generated Name</div>
            <div className="font-medium">{generatedDisplayName}</div>
            <div className="text-xs text-muted-foreground mt-1">ID: {generatedName}</div>
          </div>

          {/* Indicator */}
          <div>
            <label className="text-xs text-muted-foreground mb-1.5 block">Indicator</label>
            <GroupButton options={INDICATORS} value={indicator} onChange={setIndicator} />
          </div>

          {/* Indicator Mode */}
          {indicator !== 'none' && (
            <div>
              <label className="text-xs text-muted-foreground mb-1.5 block">Mode</label>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="indicator-buy"
                    checked={indicatorBuy}
                    onCheckedChange={(checked) => setIndicatorBuy(checked === true)}
                  />
                  <label htmlFor="indicator-buy" className="text-xs cursor-pointer">Buy</label>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="indicator-sell"
                    checked={indicatorSell}
                    onCheckedChange={(checked) => setIndicatorSell(checked === true)}
                  />
                  <label htmlFor="indicator-sell" className="text-xs cursor-pointer">Sell</label>
                </div>
              </div>
            </div>
          )}

          {/* Stop Loss */}
          <div>
            <label className="text-xs text-muted-foreground mb-1.5 block">Stop Loss (sell constraint)</label>
            <GroupButton options={STOP_LOSSES} value={stopLoss} onChange={setStopLoss} />
          </div>

          {/* MA Trend */}
          <div>
            <label className="text-xs text-muted-foreground mb-1.5 block">MA Trend (symmetric)</label>
            <GroupButton options={MA_OPTIONS} value={maTrend} onChange={setMaTrend} />
          </div>

          {/* Value Above MA */}
          <div>
            <label className="text-xs text-muted-foreground mb-1.5 block">Price Above MA (symmetric)</label>
            <GroupButton options={MA_OPTIONS} value={valueAboveMa} onChange={setValueAboveMa} />
          </div>

          {/* MA Cross */}
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <Checkbox
                id="ma-cross"
                checked={maCrossEnabled}
                onCheckedChange={(checked) => setMaCrossEnabled(checked === true)}
              />
              <label htmlFor="ma-cross" className="text-xs text-muted-foreground cursor-pointer">
                MA Cross (symmetric)
              </label>
            </div>
            {maCrossEnabled && (
              <div className="grid grid-cols-2 gap-3 mt-2">
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Fast MA</label>
                  <Input
                    type="number"
                    value={maCrossFast}
                    onChange={(e) => setMaCrossFast(e.target.value)}
                    className="h-8"
                  />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Slow MA</label>
                  <Input
                    type="number"
                    value={maCrossSlow}
                    onChange={(e) => setMaCrossSlow(e.target.value)}
                    className="h-8"
                  />
                </div>
              </div>
            )}
            {maCrossError && (
              <div className="text-xs text-destructive mt-1">{maCrossError}</div>
            )}
          </div>

          {/* Intraday */}
          <div>
            <label className="text-xs text-muted-foreground mb-1.5 block">Intraday (sell constraint)</label>
            <GroupButton options={INTRADAY_OPTIONS} value={intraday} onChange={setIntraday} />
          </div>

          {/* Time Constraint */}
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <Checkbox
                id="time-constraint"
                checked={timeConstraintEnabled}
                onCheckedChange={(checked) => setTimeConstraintEnabled(checked === true)}
              />
              <label htmlFor="time-constraint" className="text-xs text-muted-foreground cursor-pointer">
                Time Constraint (buy + sell)
              </label>
            </div>
            {timeConstraintEnabled && (
              <div className="grid grid-cols-2 gap-3 mt-2">
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Open Hour</label>
                  <Select value={timeOpen} onValueChange={setTimeOpen}>
                    <SelectTrigger size="sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 24 }, (_, i) => (
                        <SelectItem key={i} value={i.toString().padStart(2, '0')}>
                          {i.toString().padStart(2, '0')}:00
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground mb-1 block">Close Hour</label>
                  <Select value={timeClose} onValueChange={setTimeClose}>
                    <SelectTrigger size="sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 24 }, (_, i) => (
                        <SelectItem key={i} value={i.toString().padStart(2, '0')}>
                          {i.toString().padStart(2, '0')}:00
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="p-2 bg-destructive/10 border border-destructive/30 text-destructive text-sm">
              {error}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isCreating}
          >
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={!isValidConfig || !!maCrossError || isCreating}
          >
            {isCreating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="mr-2 h-4 w-4" />
                Create & Backtest
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
