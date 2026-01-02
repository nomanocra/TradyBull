'use client';

import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { StrategyConfig } from '@/hooks/useStrategies';
import { NotificationSettings, NotificationSettingsInput } from '@/hooks/useNotifications';
import { Send } from 'lucide-react';

interface NotificationModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  strategies: StrategyConfig[];
  existingSettings?: NotificationSettings | null;
  defaultStrategy?: string | null;  // Pre-select strategy in add mode
  onSave: (strategyName: string, settings: NotificationSettingsInput) => Promise<boolean>;
  onTestTelegram: (botToken: string, chatId: string) => Promise<{ success: boolean; message: string }>;
}

export function NotificationModal({
  open,
  onOpenChange,
  strategies,
  existingSettings,
  defaultStrategy,
  onSave,
  onTestTelegram,
}: NotificationModalProps) {
  const [selectedStrategy, setSelectedStrategy] = useState<string>('');
  const [desktopEnabled, setDesktopEnabled] = useState(false);
  const [telegramEnabled, setTelegramEnabled] = useState(false);
  const [botToken, setBotToken] = useState('');
  const [chatId, setChatId] = useState('');
  const [notifyBuy, setNotifyBuy] = useState(true);
  const [notifySell, setNotifySell] = useState(true);
  const [useTimeWindow, setUseTimeWindow] = useState(false);
  const [timeStart, setTimeStart] = useState('09:00');
  const [timeEnd, setTimeEnd] = useState('22:00');
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  // Reset form when modal opens/closes or existingSettings changes
  useEffect(() => {
    if (open) {
      if (existingSettings) {
        setSelectedStrategy(existingSettings.strategy_name);
        setDesktopEnabled(existingSettings.desktop_enabled);
        setTelegramEnabled(existingSettings.telegram_enabled);
        setBotToken(existingSettings.telegram_bot_token || '');
        setChatId(existingSettings.telegram_chat_id || '');
        setNotifyBuy(existingSettings.notify_buy);
        setNotifySell(existingSettings.notify_sell);
        setUseTimeWindow(existingSettings.time_start !== '00:00' || existingSettings.time_end !== '23:59');
        setTimeStart(existingSettings.time_start);
        setTimeEnd(existingSettings.time_end);
      } else {
        setSelectedStrategy(defaultStrategy || '');
        setDesktopEnabled(false);
        setTelegramEnabled(false);
        setBotToken('');
        setChatId('');
        setNotifyBuy(true);
        setNotifySell(true);
        setUseTimeWindow(false);
        setTimeStart('09:00');
        setTimeEnd('22:00');
      }
      setTestResult(null);
    }
  }, [open, existingSettings, defaultStrategy]);

  const handleSave = async () => {
    if (!selectedStrategy) return;

    setIsSaving(true);
    const success = await onSave(selectedStrategy, {
      enabled: desktopEnabled || telegramEnabled,
      desktop_enabled: desktopEnabled,
      telegram_enabled: telegramEnabled,
      telegram_bot_token: telegramEnabled ? botToken : null,
      telegram_chat_id: telegramEnabled ? chatId : null,
      notify_buy: notifyBuy,
      notify_sell: notifySell,
      time_start: useTimeWindow ? timeStart : '00:00',
      time_end: useTimeWindow ? timeEnd : '23:59',
    });
    setIsSaving(false);

    if (success) {
      onOpenChange(false);
    }
  };

  const handleTestTelegram = async () => {
    if (!botToken || !chatId) return;

    setIsTesting(true);
    setTestResult(null);
    const result = await onTestTelegram(botToken, chatId);
    setTestResult(result);
    setIsTesting(false);
  };

  const isValid = selectedStrategy && (desktopEnabled || telegramEnabled) && (notifyBuy || notifySell);
  const telegramConfigValid = !telegramEnabled || (botToken && chatId);

  // Filter out strategies that already have notifications (unless editing)
  const availableStrategies = existingSettings
    ? strategies
    : strategies;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-sm">
            {existingSettings ? 'Edit Notification' : 'Add Notification'}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Strategy Selection */}
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Strategy</label>
            <Select
              value={selectedStrategy}
              onValueChange={setSelectedStrategy}
              disabled={!!existingSettings}
            >
              <SelectTrigger size="sm" className="text-xs">
                <SelectValue placeholder="Select a strategy" />
              </SelectTrigger>
              <SelectContent>
                {availableStrategies.map((strategy) => (
                  <SelectItem key={strategy.name} value={strategy.name} className="text-xs">
                    {strategy.display_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Notification Types */}
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Notification Type</label>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs">Desktop</span>
                <Switch checked={desktopEnabled} onCheckedChange={setDesktopEnabled} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs">Telegram</span>
                <Switch checked={telegramEnabled} onCheckedChange={setTelegramEnabled} />
              </div>
            </div>
          </div>

          {/* Telegram Config */}
          {telegramEnabled && (
            <div className="space-y-2 p-3 bg-muted/50 rounded">
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground">Bot Token</label>
                <Input
                  type="password"
                  value={botToken}
                  onChange={(e) => setBotToken(e.target.value)}
                  placeholder="123456:ABC-DEF..."
                  className="h-8 text-xs font-mono"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground">Chat ID</label>
                <Input
                  value={chatId}
                  onChange={(e) => setChatId(e.target.value)}
                  placeholder="-1001234567890"
                  className="h-8 text-xs font-mono"
                />
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleTestTelegram}
                disabled={!botToken || !chatId || isTesting}
                className="w-full h-7 text-xs"
              >
                <Send size={12} className="mr-1.5" />
                {isTesting ? 'Testing...' : 'Test Connection'}
              </Button>
              {testResult && (
                <p className={`text-xs ${testResult.success ? 'text-emerald-500' : 'text-red-500'}`}>
                  {testResult.message}
                </p>
              )}
            </div>
          )}

          {/* Signal Types */}
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Signal Types</label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-xs cursor-pointer">
                <Checkbox
                  checked={notifyBuy}
                  onCheckedChange={(checked) => setNotifyBuy(checked === true)}
                />
                Buy
              </label>
              <label className="flex items-center gap-2 text-xs cursor-pointer">
                <Checkbox
                  checked={notifySell}
                  onCheckedChange={(checked) => setNotifySell(checked === true)}
                />
                Sell
              </label>
            </div>
          </div>

          {/* Time Window */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Custom Time Window</span>
              <Switch checked={useTimeWindow} onCheckedChange={setUseTimeWindow} />
            </div>
            {useTimeWindow && (
              <div className="flex items-center gap-2">
                <Input
                  type="time"
                  value={timeStart}
                  onChange={(e) => setTimeStart(e.target.value)}
                  className="h-8 text-xs w-24"
                />
                <span className="text-xs text-muted-foreground">to</span>
                <Input
                  type="time"
                  value={timeEnd}
                  onChange={(e) => setTimeEnd(e.target.value)}
                  className="h-8 text-xs w-24"
                />
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)} className="h-8 text-xs">
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!isValid || !telegramConfigValid || isSaving}
            className="h-8 text-xs"
          >
            {isSaving ? 'Saving...' : existingSettings ? 'Update' : 'Add'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
