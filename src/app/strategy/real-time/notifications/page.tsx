'use client';

import { useState } from 'react';
import { Plus, Bell, Trash2, Edit2, Monitor, MessageCircle, List } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
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
import { NotificationModal } from '@/components/notifications/notification-modal';
import { NotificationHistoryModal } from '@/components/notifications/notification-history-modal';
import { useNotifications, NotificationSettings } from '@/hooks/useNotifications';
import { useStrategies } from '@/hooks/useStrategies';

export default function NotificationsPage() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingSettings, setEditingSettings] = useState<NotificationSettings | null>(null);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [historyStrategyName, setHistoryStrategyName] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingStrategyName, setDeletingStrategyName] = useState<string | null>(null);

  const { settings, isLoading, saveSettings, deleteSettings, testTelegram, testDesktop } = useNotifications();
  const { strategies, archivedStrategies } = useStrategies();

  // Only use non-archived strategies that don't already have notifications
  const configuredStrategyNames = new Set(settings.map((s) => s.strategy_name));
  const availableStrategies = strategies.filter((s) => !configuredStrategyNames.has(s.name));
  // All strategies for displaying names of existing notifications
  const allStrategies = [...strategies, ...archivedStrategies];

  const handleAddClick = () => {
    setEditingSettings(null);
    setIsModalOpen(true);
  };

  const handleEditClick = (setting: NotificationSettings) => {
    setEditingSettings(setting);
    setIsModalOpen(true);
  };

  const handleDeleteClick = (strategyName: string) => {
    setDeletingStrategyName(strategyName);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (deletingStrategyName) {
      await deleteSettings(deletingStrategyName);
    }
    setDeleteDialogOpen(false);
    setDeletingStrategyName(null);
  };

  const handleHistoryClick = (strategyName: string) => {
    setHistoryStrategyName(strategyName);
    setHistoryModalOpen(true);
  };

  const handleToggleEnabled = async (setting: NotificationSettings) => {
    await saveSettings(setting.strategy_name, { enabled: !setting.enabled });
  };

  const getStrategyDisplayName = (strategyName: string) => {
    const strategy = allStrategies.find((s) => s.name === strategyName);
    return strategy?.display_name || strategyName;
  };

  const formatTimeWindow = (start: string, end: string) => {
    if (start === '00:00' && end === '23:59') return 'All day';
    return `${start} - ${end}`;
  };

  return (
    <div className="h-full w-full bg-background flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex items-center px-3 py-1.5 border-b border-border bg-card">
        <div className="flex items-center gap-2">
          <Bell size={14} className="text-brand" />
          <span className="text-xs font-semibold text-brand">Notifications</span>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 p-4 overflow-auto">
        {isLoading ? (
          <div className="text-center text-muted-foreground text-sm py-8">Loading...</div>
        ) : settings.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full">
            <Bell size={48} className="text-muted-foreground/30 mb-4" />
            <p className="text-sm text-muted-foreground mb-4">No notifications configured</p>
            <Button size="sm" onClick={handleAddClick} className="h-8 text-xs">
              <Plus size={12} />
              Add your first notification
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex justify-end">
              <Button size="sm" onClick={handleAddClick} className="h-8 text-xs">
                <Plus size={12} />
                Add Notification
              </Button>
            </div>
            <div className="space-y-2">
            {settings.map((setting) => (
              <div
                key={setting.strategy_name}
                className="flex items-center justify-between p-3 bg-card border border-border hover:border-muted-foreground/30 transition-colors"
              >
                {/* Bell Icon */}
                <Bell size={20} className={`mr-4 ${setting.enabled ? 'text-brand' : 'text-muted-foreground'}`} />

                {/* Toggle */}
                <div className="flex flex-col items-center gap-1 mr-4">
                  <span className="text-[10px] text-muted-foreground">Active</span>
                  <Switch
                    checked={setting.enabled}
                    onCheckedChange={() => handleToggleEnabled(setting)}
                    className="scale-75"
                  />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">
                      {getStrategyDisplayName(setting.strategy_name)}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    {/* Notification types */}
                    <div className="flex items-center gap-1.5">
                      {setting.desktop_enabled && (
                        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                          <Monitor size={10} /> Desktop
                        </span>
                      )}
                      {setting.telegram_enabled && (
                        <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                          <MessageCircle size={10} /> Telegram
                        </span>
                      )}
                    </div>
                    {/* Signal types */}
                    <span className="text-[10px] text-muted-foreground">
                      {setting.notify_buy && setting.notify_sell
                        ? 'Buy & Sell'
                        : setting.notify_buy
                        ? 'Buy only'
                        : 'Sell only'}
                    </span>
                    {/* Time window */}
                    <span className="text-[10px] text-muted-foreground">
                      {formatTimeWindow(setting.time_start, setting.time_end)}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1 ml-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleHistoryClick(setting.strategy_name)}
                    className="h-7 w-7 p-0"
                    title="View history"
                  >
                    <List size={12} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleEditClick(setting)}
                    className="h-7 w-7 p-0"
                  >
                    <Edit2 size={12} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteClick(setting.strategy_name)}
                    className="h-7 w-7 p-0 text-red-500 hover:text-red-600 hover:bg-red-500/10"
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

      {/* Modal */}
      <NotificationModal
        open={isModalOpen}
        onOpenChange={setIsModalOpen}
        strategies={editingSettings ? strategies : availableStrategies}
        existingSettings={editingSettings}
        onSave={saveSettings}
        onTestTelegram={testTelegram}
        onTestDesktop={testDesktop}
      />

      {/* History Modal */}
      <NotificationHistoryModal
        open={historyModalOpen}
        onOpenChange={setHistoryModalOpen}
        strategyName={historyStrategyName}
        strategyDisplayName={historyStrategyName ? getStrategyDisplayName(historyStrategyName) : ''}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="text-sm">Delete Notification</AlertDialogTitle>
            <AlertDialogDescription className="text-xs">
              Are you sure you want to delete the notification for{' '}
              <span className="font-medium text-foreground">
                {deletingStrategyName ? getStrategyDisplayName(deletingStrategyName) : ''}
              </span>
              ? This action cannot be undone.
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
