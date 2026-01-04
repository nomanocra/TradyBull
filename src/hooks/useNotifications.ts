import { useState, useEffect, useCallback } from 'react';

const API_URL = 'http://localhost:8000/api';

export interface NotificationSettings {
  strategy_name: string;
  enabled: boolean;
  desktop_enabled: boolean;
  telegram_enabled: boolean;
  telegram_bot_token: string | null;
  telegram_chat_id: string | null;
  notify_buy: boolean;
  notify_sell: boolean;
  time_start: string;
  time_end: string;
  created_at?: number;
  updated_at?: number;
}

export interface NotificationSettingsInput {
  enabled?: boolean;
  desktop_enabled?: boolean;
  telegram_enabled?: boolean;
  telegram_bot_token?: string | null;
  telegram_chat_id?: string | null;
  notify_buy?: boolean;
  notify_sell?: boolean;
  time_start?: string;
  time_end?: string;
}

interface UseNotificationsResult {
  settings: NotificationSettings[];
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  saveSettings: (strategyName: string, settings: NotificationSettingsInput) => Promise<boolean>;
  deleteSettings: (strategyName: string) => Promise<boolean>;
  testTelegram: (botToken: string, chatId: string) => Promise<{ success: boolean; message: string }>;
  testDesktop: () => Promise<{ success: boolean; message: string }>;
}

export function useNotifications(): UseNotificationsResult {
  const [settings, setSettings] = useState<NotificationSettings[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSettings = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${API_URL}/notifications/settings`);
      if (!response.ok) {
        throw new Error('Failed to fetch notification settings');
      }

      const data = await response.json();
      // Convert SQLite integers (0/1) to booleans
      const normalizedSettings = (data.settings || []).map((s: NotificationSettings) => ({
        ...s,
        enabled: Boolean(s.enabled),
        desktop_enabled: Boolean(s.desktop_enabled),
        telegram_enabled: Boolean(s.telegram_enabled),
        notify_buy: Boolean(s.notify_buy),
        notify_sell: Boolean(s.notify_sell),
      }));
      setSettings(normalizedSettings);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings');
      setSettings([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const saveSettings = useCallback(async (strategyName: string, newSettings: NotificationSettingsInput): Promise<boolean> => {
    try {
      const response = await fetch(`${API_URL}/notifications/settings/${encodeURIComponent(strategyName)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings),
      });

      if (!response.ok) {
        throw new Error('Failed to save settings');
      }

      await fetchSettings();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings');
      return false;
    }
  }, [fetchSettings]);

  const deleteSettings = useCallback(async (strategyName: string): Promise<boolean> => {
    try {
      const response = await fetch(`${API_URL}/notifications/settings/${encodeURIComponent(strategyName)}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete settings');
      }

      await fetchSettings();
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete settings');
      return false;
    }
  }, [fetchSettings]);

  const testTelegram = useCallback(async (botToken: string, chatId: string): Promise<{ success: boolean; message: string }> => {
    try {
      const response = await fetch(`${API_URL}/notifications/test/telegram`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot_token: botToken, chat_id: chatId }),
      });

      const data = await response.json();
      return { success: data.success, message: data.message };
    } catch (err) {
      return { success: false, message: err instanceof Error ? err.message : 'Test failed' };
    }
  }, []);

  const testDesktop = useCallback(async (): Promise<{ success: boolean; message: string }> => {
    // Check if browser supports notifications
    if (!('Notification' in window)) {
      return { success: false, message: 'Desktop notifications are not supported in this browser' };
    }

    // Check/request permission
    let permission = Notification.permission;

    if (permission === 'denied') {
      return { success: false, message: 'Notifications are blocked. Please enable them in your browser settings.' };
    }

    if (permission === 'default') {
      permission = await Notification.requestPermission();
    }

    if (permission !== 'granted') {
      return { success: false, message: 'Notification permission was not granted' };
    }

    // Show test notification
    try {
      const notification = new Notification('TradyBull Test', {
        body: '✅ Desktop notifications are working correctly!',
        icon: '/logo.svg',
        tag: 'tradybull-test',
      });

      // Auto-close after 5 seconds
      setTimeout(() => notification.close(), 5000);

      return { success: true, message: 'Test notification sent!' };
    } catch (err) {
      return { success: false, message: err instanceof Error ? err.message : 'Failed to show notification' };
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  return {
    settings,
    isLoading,
    error,
    refetch: fetchSettings,
    saveSettings,
    deleteSettings,
    testTelegram,
    testDesktop,
  };
}
