'use client';

import { useState, useMemo, useEffect } from 'react';
import { Loader2, Plus, Info, ChevronDown, Check } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
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
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
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

// All indicators in a single list
const INDICATORS = [
  { value: 'none', label: 'None', short: 'None', description: 'No indicator - use other constraints only' },
  { value: 'bollinger', label: 'Bollinger Bands', short: 'Boll', description: 'Buy when price touches lower band (oversold), sell when touches upper band (overbought).' },
  { value: 'macd-cross', label: 'MACD Cross', short: 'MACD-X', description: 'Buy when MACD line crosses above signal line, sell when crosses below.' },
  { value: 'macd-zero', label: 'MACD Zero', short: 'MACD-0', description: 'Buy when MACD crosses above zero, sell when crosses below. Fewer false signals.' },
  { value: 'macd-histogram', label: 'MACD Histogram', short: 'MACD-H', description: 'Buy when histogram starts rising, sell when starts falling. Faster signals.' },
  { value: 'ichimoku-kumo', label: 'Ichimoku Kumo', short: 'Ichi-K', description: 'Buy when price breaks above cloud, sell when breaks below.' },
  { value: 'ichimoku-tk', label: 'Ichimoku TK Cross', short: 'Ichi-TK', description: 'Buy when Tenkan crosses above Kijun, sell when crosses below.' },
  { value: 'rsi-trend', label: 'RSI Trend', short: 'RSI-T', description: 'Buy when RSI rises while below 20, sell when falls while above 80.' },
  { value: 'rsi-early', label: 'RSI Early', short: 'RSI-E', description: 'Buy when RSI enters <20 zone, sell when enters >80 zone. Anticipates reversal.' },
  { value: 'rsi-late', label: 'RSI Late', short: 'RSI-L', description: 'Buy when RSI exits <20 zone, sell when exits >80 zone. Waits for confirmation.' },
  { value: 'rsi-large', label: 'RSI Large', short: 'RSI-Lg', description: 'Buy on entry to <20, sell on exit from >80. Maximizes hold time.' },
  { value: 'rsi-small', label: 'RSI Small', short: 'RSI-Sm', description: 'Buy on exit from <20, sell on entry to >80. Minimizes hold time.' },
];

const STOP_LOSSES = [
  { value: 'none', label: 'None', description: 'No stop loss protection' },
  { value: '0.5', label: '0.5%', description: 'SELL if price drops 0.5% from entry' },
  { value: '0.8', label: '0.8%', description: 'SELL if price drops 0.8% from entry' },
  { value: '1', label: '1%', description: 'SELL if price drops 1% from entry' },
  { value: '1.5', label: '1.5%', description: 'SELL if price drops 1.5% from entry' },
  { value: '2', label: '2%', description: 'SELL if price drops 2% from entry' },
  { value: '2.5', label: '2.5%', description: 'SELL if price drops 2.5% from entry' },
  { value: '5', label: '5%', description: 'SELL if price drops 5% from entry' },
];

const MA_TREND_OPTIONS = [
  { value: 'none', label: 'None', description: 'No MA trend filter' },
  { value: '50', label: 'MA 50', description: 'BUY: MA50 rising. SELL: MA50 falling' },
  { value: '100', label: 'MA 100', description: 'BUY: MA100 rising. SELL: MA100 falling' },
  { value: '150', label: 'MA 150', description: 'BUY: MA150 rising. SELL: MA150 falling' },
  { value: '200', label: 'MA 200', description: 'BUY: MA200 rising. SELL: MA200 falling' },
];

const MA_ABOVE_OPTIONS = [
  { value: 'none', label: 'None', description: 'No price/MA filter' },
  { value: '50', label: 'MA 50', description: 'BUY: price > MA50. SELL: price < MA50' },
  { value: '100', label: 'MA 100', description: 'BUY: price > MA100. SELL: price < MA100' },
  { value: '150', label: 'MA 150', description: 'BUY: price > MA150. SELL: price < MA150' },
  { value: '200', label: 'MA 200', description: 'BUY: price > MA200. SELL: price < MA200' },
];

const INTRADAY_OPTIONS = [
  { value: 'none', label: 'None', description: 'No intraday constraint' },
  { value: 'daily', label: 'Single', description: 'BUY: max 1 per day. SELL: at end of day' },
  { value: 'multi-daily', label: 'Multi', description: 'BUY: unlimited per day. SELL: at end of day' },
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
    parts.push('intrad-single');
  } else if (config.intraday === 'multi-daily') {
    parts.push('intrad-multi');
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

export function StrategyCreationModal({
  open,
  onOpenChange,
  onCreated,
}: StrategyCreationModalProps) {
  // Form state
  const [indicator, setIndicator] = useState('none');
  const [indicatorOpen, setIndicatorOpen] = useState(false);
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
      setIndicatorOpen(false);
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
  const selectedIndicator = INDICATORS.find(i => i.value === indicator);
  const generatedDisplayName = useMemo(() => {
    const parts: string[] = [];
    if (config.indicator) {
      const ind = INDICATORS.find(i => i.value === config.indicator?.type);
      let indName = ind?.short || config.indicator.type;
      if (config.indicator.mode === 'buy') indName += '(B)';
      else if (config.indicator.mode === 'sell') indName += '(S)';
      parts.push(indName);
    }
    if (config.stop_loss) parts.push(`SL-${config.stop_loss}%`);
    if (config.ma_trend) parts.push(`Trend-${config.ma_trend}`);
    if (config.value_above_ma) parts.push(`Above-MA${config.value_above_ma}`);
    if (config.ma_cross) parts.push(`Cross-${config.ma_cross.fast}/${config.ma_cross.slow}`);
    if (config.intraday === 'daily') parts.push('IntraD-Single');
    else if (config.intraday === 'multi-daily') parts.push('IntraD-Multi');
    if (config.time_constraint) {
      parts.push(`H${config.time_constraint.open.split(':')[0]}-${config.time_constraint.close.split(':')[0]}`);
    }
    return parts.length ? parts.join(' ') : 'Default-Strategy';
  }, [config]);

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

  // Check if indicator mode is valid (at least one of buy/sell if indicator selected)
  const indicatorModeError = useMemo(() => {
    if (indicator !== 'none' && !indicatorBuy && !indicatorSell) {
      return 'Select at least Buy or Sell';
    }
    return null;
  }, [indicator, indicatorBuy, indicatorSell]);

  // Check if strategy has at least one meaningful entry/exit condition
  // Stop loss alone is NOT sufficient - it only defines exit on loss
  const isValidConfig = useMemo(() => {
    const hasEntryExitCondition = (
      config.indicator !== null ||
      config.ma_trend !== null ||
      config.value_above_ma !== null ||
      config.ma_cross !== null ||
      config.intraday !== 'none' ||
      config.time_constraint !== null
    );
    return hasEntryExitCondition;
  }, [config]);

  // Error message for invalid config
  const configError = useMemo(() => {
    if (!isValidConfig && config.stop_loss !== null) {
      return 'Stop loss alone is not sufficient. Add an indicator, MA condition, intraday, or time constraint.';
    }
    return null;
  }, [isValidConfig, config.stop_loss]);

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
      <DialogContent className="sm:max-w-[700px]">
        <DialogHeader>
          <DialogTitle>Create Strategy</DialogTitle>
          <DialogDescription>
            Configure your custom trading strategy parameters.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Preview Name */}
          <div className="p-3 bg-muted/50">
            <div className="text-xs text-muted-foreground mb-1">Generated Name</div>
            <div className="font-medium">{generatedDisplayName}</div>
          </div>

          {/* Indicator */}
          <div>
            <label className="text-xs text-muted-foreground mb-1.5 block">Indicator</label>
            <Popover open={indicatorOpen} onOpenChange={setIndicatorOpen}>
              <PopoverTrigger asChild>
                <button className="flex w-full items-center justify-between border border-input bg-background px-3 py-2 text-left text-sm shadow-xs hover:bg-accent/50 transition-colors">
                  <div>
                    <div className="font-medium text-xs">{selectedIndicator?.label || 'None'}</div>
                    {selectedIndicator && (
                      <div className="text-[10px] text-muted-foreground mt-0.5">{selectedIndicator.description}</div>
                    )}
                  </div>
                  <ChevronDown className="size-4 opacity-50 shrink-0" />
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-1 max-h-[300px] overflow-y-auto" align="start">
                {INDICATORS.map((ind) => (
                  <button
                    key={ind.value}
                    onClick={() => {
                      setIndicator(ind.value);
                      setIndicatorOpen(false);
                    }}
                    className={`flex w-full items-start gap-2 px-2 py-2 text-left hover:bg-accent transition-colors ${
                      indicator === ind.value ? 'bg-accent' : ''
                    }`}
                  >
                    <Check className={`size-4 mt-0.5 shrink-0 ${indicator === ind.value ? 'opacity-100' : 'opacity-0'}`} />
                    <div>
                      <div className="text-xs font-medium">{ind.label}</div>
                      <div className="text-[10px] text-muted-foreground">{ind.description}</div>
                    </div>
                  </button>
                ))}
              </PopoverContent>
            </Popover>
          </div>

          {/* Indicator Mode */}
          {indicator !== 'none' && (
            <div>
              <div className="flex items-center gap-1.5 mb-1.5">
                <label className="text-xs text-muted-foreground">Mode</label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info size={12} className="text-muted-foreground/50" />
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-[250px]">
                    Use indicator for Buy signals, Sell signals, or both
                  </TooltipContent>
                </Tooltip>
              </div>
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
                {indicatorModeError && (
                  <span className="text-xs text-destructive">{indicatorModeError}</span>
                )}
              </div>
            </div>
          )}

          {/* Stop Loss */}
          <div>
            <label className="text-xs text-muted-foreground mb-1.5 block">Stop Loss</label>
            <GroupButton options={STOP_LOSSES} value={stopLoss} onChange={setStopLoss} />
          </div>

          {/* MA Trend */}
          <div>
            <label className="text-xs text-muted-foreground mb-1.5 block">MA Trend</label>
            <GroupButton options={MA_TREND_OPTIONS} value={maTrend} onChange={setMaTrend} />
          </div>

          {/* Value Above MA */}
          <div>
            <label className="text-xs text-muted-foreground mb-1.5 block">Price Above MA</label>
            <GroupButton options={MA_ABOVE_OPTIONS} value={valueAboveMa} onChange={setValueAboveMa} />
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
                MA Cross
              </label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info size={12} className="text-muted-foreground/50" />
                </TooltipTrigger>
                <TooltipContent side="right" className="max-w-[250px]">
                  Buy when fast MA crosses above slow MA, sell when fast MA crosses below
                </TooltipContent>
              </Tooltip>
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
            <label className="text-xs text-muted-foreground mb-1.5 block">Intraday</label>
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
                Time Constraint
              </label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info size={12} className="text-muted-foreground/50" />
                </TooltipTrigger>
                <TooltipContent side="right" className="max-w-[250px]">
                  Only trade during specific hours (Paris time)
                </TooltipContent>
              </Tooltip>
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

          {/* Validation Error */}
          {configError && (
            <div className="p-2 bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-sm">
              {configError}
            </div>
          )}

          {/* API Error */}
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
            disabled={!isValidConfig || !!maCrossError || !!indicatorModeError || isCreating}
          >
            {isCreating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="h-4 w-4" />
                Create
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
