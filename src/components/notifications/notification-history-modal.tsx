'use client';

import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Monitor, MessageCircle, CheckCircle, XCircle } from 'lucide-react';

interface NotificationHistoryItem {
  id: number;
  strategy_name: string;
  sent_at: number;
  signal_type: string;
  price: number;
  channel: string;
  message: string;
  success: number;
  error_message: string | null;
}

interface NotificationHistoryModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  strategyName: string | null;
  strategyDisplayName: string;
}

export function NotificationHistoryModal({
  open,
  onOpenChange,
  strategyName,
  strategyDisplayName,
}: NotificationHistoryModalProps) {
  const [history, setHistory] = useState<NotificationHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (open && strategyName) {
      fetchHistory();
    }
  }, [open, strategyName]);

  const fetchHistory = async () => {
    if (!strategyName) return;

    setIsLoading(true);
    try {
      const response = await fetch(`http://localhost:8000/api/notifications/history/${strategyName}`);
      if (response.ok) {
        const data = await response.json();
        setHistory(data.history || []);
      }
    } catch (error) {
      console.error('Failed to fetch notification history:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getChannelIcon = (channel: string) => {
    switch (channel) {
      case 'telegram':
        return <MessageCircle size={12} />;
      case 'desktop':
        return <Monitor size={12} />;
      default:
        return null;
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-sm">
            Notification History - {strategyDisplayName}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-auto py-2">
          {isLoading ? (
            <div className="text-center text-muted-foreground text-sm py-8">
              Loading...
            </div>
          ) : history.length === 0 ? (
            <div className="text-center text-muted-foreground text-sm py-8">
              No notifications sent yet
            </div>
          ) : (
            <div className="space-y-2">
              {history.map((item) => (
                <div
                  key={item.id}
                  className="p-3 bg-card border border-border rounded-lg"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        {/* Signal type badge */}
                        <span
                          className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                            item.signal_type === 'buy'
                              ? 'bg-emerald-500/20 text-emerald-500'
                              : 'bg-red-500/20 text-red-500'
                          }`}
                        >
                          {item.signal_type.toUpperCase()}
                        </span>

                        {/* Channel */}
                        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                          {getChannelIcon(item.channel)}
                          {item.channel}
                        </span>

                        {/* Success/Error indicator */}
                        {item.success ? (
                          <CheckCircle size={12} className="text-emerald-500" />
                        ) : (
                          <XCircle size={12} className="text-red-500" />
                        )}
                      </div>

                      {/* Price */}
                      <div className="text-xs mt-1">
                        Price: <span className="font-mono">{item.price.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                      </div>

                      {/* Error message if any */}
                      {!item.success && item.error_message && (
                        <div className="text-[10px] text-red-500 mt-1">
                          Error: {item.error_message}
                        </div>
                      )}
                    </div>

                    {/* Timestamp */}
                    <div className="text-[10px] text-muted-foreground whitespace-nowrap">
                      {formatDate(item.sent_at)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
