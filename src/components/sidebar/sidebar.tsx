'use client';

import { useState, useEffect, useTransition, useMemo, useRef, useCallback } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { ChevronDown, ChevronRight, Compass, Play, History, Sun, Moon, Archive, ArchiveRestore, Search, X, Bell, Table, Plus } from 'lucide-react';
import { ModeSelector, ModeOption } from '@/components/ui/mode-selector';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useStrategies, StrategyConfig } from '@/hooks/useStrategies';
import { useNotifications } from '@/hooks/useNotifications';
import { NotificationModal } from '@/components/notifications/notification-modal';
import { StrategyCreationModal } from '@/components/strategy/strategy-creation-modal';
import packageJson from '../../../package.json';

const STORAGE_KEY = 'tradybull-sidebar-sections';
const MODE_STORAGE_KEY = 'tradybull-sidebar-mode';
const THEME_STORAGE_KEY = 'tradybull-theme';
const WIDTH_STORAGE_KEY = 'tradybull-sidebar-width';
const LAST_PATH_KEY = 'tradybull-last-path';

const MIN_WIDTH = 208; // w-52
const MAX_WIDTH = 460;

type Mode = 'exploration' | 'backtesting' | 'realtime';

interface NavItem {
  name: string;
  href: string;
  strategySlug?: string; // For archive functionality
}

interface NavSection {
  title: string;
  storageKey?: string; // Key for localStorage (defaults to title)
  items: NavItem[];
  isArchive?: boolean;
  isStandalone?: boolean; // Items rendered at root level without collapsible header
}

const explorationNavigation: NavSection[] = [
  {
    title: 'Real Time',
    items: [
      { name: 'Multi Indicator', href: '/exploration/real-time' },
      { name: 'Bollinger', href: '/exploration/real-time/bollinger' },
      { name: 'MACD', href: '/exploration/real-time/macd' },
      { name: 'Ichimoku', href: '/exploration/real-time/ichimoku' },
      { name: 'Moving Averages', href: '/exploration/real-time/moving-averages' },
      { name: 'Stochastic RSI', href: '/exploration/real-time/stochastic-rsi' },
    ],
  },
  {
    title: 'Historical Data',
    items: [
      { name: 'Multi Indicator', href: '/exploration/historical' },
      { name: 'Bollinger', href: '/exploration/historical/bollinger' },
      { name: 'MACD', href: '/exploration/historical/macd' },
      { name: 'Ichimoku', href: '/exploration/historical/ichimoku' },
      { name: 'Moving Averages', href: '/exploration/historical/moving-averages' },
      { name: 'Stochastic RSI', href: '/exploration/historical/stochastic-rsi' },
    ],
  },
];

// Backtesting navigation generated dynamically from the API
function generateBacktestingNavigation(
  strategies: StrategyConfig[],
  archivedStrategies: StrategyConfig[]
): NavSection[] {
  const sections: NavSection[] = [
    {
      title: 'Overview',
      isStandalone: true,
      items: [
        { name: 'Overview', href: '/strategy/backtesting/overview' },
      ],
    },
    {
      title: 'Strategies',
      storageKey: 'Strategies-Backtesting',
      items: strategies.map((s) => ({
        name: s.display_name,
        href: `/strategy/backtesting/${s.name}`,
        strategySlug: s.name,
      })),
    },
  ];

  // Add Archive section if there are archived strategies
  if (archivedStrategies.length > 0) {
    sections.push({
      title: 'Archive',
      isArchive: true,
      items: archivedStrategies.map((s) => ({
        name: s.display_name,
        href: `/strategy/backtesting/${s.name}`,
        strategySlug: s.name,
      })),
    });
  }

  return sections;
}

// Real Time navigation generated dynamically from the API
function generateRealtimeNavigation(strategies: StrategyConfig[]): NavSection[] {
  return [
    {
      title: 'Notifications',
      isStandalone: true,
      items: [
        { name: 'Notifications', href: '/strategy/real-time/notifications' },
      ],
    },
    {
      title: 'Strategies',
      storageKey: 'Strategies-RealTime',
      items: strategies.map((s) => ({
        name: s.display_name,
        href: `/strategy/real-time/${s.name}`,
        strategySlug: s.name,
      })),
    },
  ];
}

const modeOptions: ModeOption[] = [
  { value: 'exploration', label: 'Exploration', description: 'Explore indicators', icon: Compass },
  { value: 'backtesting', label: 'Backtesting', description: 'Test strategies', icon: History },
  { value: 'realtime', label: 'Real Time', description: 'Live trading signals', icon: Play },
];

const defaultSections: Record<string, boolean> = {
  'Real Time': true,
  'Historical Data': true,
  'Backtesting': true,
  'Archive': false, // Collapsed by default
  'Notifications': true,
  'Strategies-Backtesting': true,
  'Strategies-RealTime': true,
};

type Theme = 'dark' | 'light';

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [pendingPath, setPendingPath] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>('exploration');
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>(defaultSections);
  const [theme, setTheme] = useState<Theme>('dark');
  const [isHydrated, setIsHydrated] = useState(false);
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [width, setWidth] = useState(MIN_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);

  // Fetch strategies from API
  const { strategies, archivedStrategies, allStrategies, archiveStrategy, unarchiveStrategy, refetch: refetchStrategies } = useStrategies();

  // Fetch notification settings
  const { settings: notificationSettings, saveSettings, testTelegram, testDesktop } = useNotifications();

  // Notification modal state
  const [notificationModalOpen, setNotificationModalOpen] = useState(false);
  const [notificationModalStrategy, setNotificationModalStrategy] = useState<string | null>(null);

  // Strategy creation modal state
  const [strategyCreationModalOpen, setStrategyCreationModalOpen] = useState(false);


  // Generate backtesting navigation dynamically
  const backtestingNavigation = useMemo(
    () => generateBacktestingNavigation(strategies, archivedStrategies),
    [strategies, archivedStrategies]
  );

  // Generate realtime navigation dynamically
  const realtimeNavigation = useMemo(
    () => generateRealtimeNavigation(strategies),
    [strategies]
  );

  // Clear pending path when navigation completes
  useEffect(() => {
    if (pendingPath && pathname === pendingPath) {
      setPendingPath(null);
    }
  }, [pathname, pendingPath]);

  // Sync mode with current URL path
  useEffect(() => {
    if (pathname.startsWith('/strategy/backtesting')) {
      setMode('backtesting');
    } else if (pathname.startsWith('/strategy/real-time')) {
      setMode('realtime');
    } else if (pathname.startsWith('/exploration')) {
      setMode('exploration');
    }
  }, [pathname]);

  // Save current path to localStorage for persistence
  useEffect(() => {
    if (pathname && pathname !== '/') {
      localStorage.setItem(LAST_PATH_KEY, pathname);
    }
  }, [pathname]);

  // Load from localStorage after hydration
  useEffect(() => {
    const savedSections = localStorage.getItem(STORAGE_KEY);
    if (savedSections) {
      try {
        setExpandedSections({ ...defaultSections, ...JSON.parse(savedSections) });
      } catch {
        // Invalid JSON, use defaults
      }
    }
    // Sync mode with current URL path (takes priority over localStorage)
    if (pathname.startsWith('/strategy/backtesting')) {
      setMode('backtesting');
    } else if (pathname.startsWith('/strategy/real-time')) {
      setMode('realtime');
    } else if (pathname.startsWith('/exploration')) {
      setMode('exploration');
    }
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY) as Theme | null;
    if (savedTheme === 'dark' || savedTheme === 'light') {
      setTheme(savedTheme);
      document.documentElement.classList.toggle('dark', savedTheme === 'dark');
    }
    setIsHydrated(true);
  }, [pathname]);

  // Save to localStorage when sections change
  useEffect(() => {
    if (isHydrated) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(expandedSections));
    }
  }, [expandedSections, isHydrated]);

  // Save mode to localStorage
  useEffect(() => {
    if (isHydrated) {
      localStorage.setItem(MODE_STORAGE_KEY, mode);
    }
  }, [mode, isHydrated]);

  // Toggle theme
  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem(THEME_STORAGE_KEY, newTheme);
    document.documentElement.classList.toggle('dark', newTheme === 'dark');
  };

  const toggleSection = (title: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [title]: !prev[title],
    }));
  };

  const baseNavigation = useMemo(() => {
    switch (mode) {
      case 'exploration':
        return explorationNavigation;
      case 'backtesting':
        return backtestingNavigation;
      case 'realtime':
        return realtimeNavigation;
      default:
        return explorationNavigation;
    }
  }, [mode, backtestingNavigation, realtimeNavigation]);

  // Filter navigation by search query
  const navigation = useMemo(() => {
    if (!searchQuery.trim()) return baseNavigation;

    const query = searchQuery.toLowerCase().trim();
    return baseNavigation.map((section) => ({
      ...section,
      items: section.items.filter((item) =>
        item.name.toLowerCase().includes(query)
      ),
    })).filter((section) => section.items.length > 0);
  }, [baseNavigation, searchQuery]);

  // Check if a path is active (exact match or pending navigation)
  const isPathActive = (href: string) => {
    // Optimistic: show as active immediately when clicked
    if (pendingPath === href) return true;
    // If navigating to another page, deselect current page
    if (pendingPath && pendingPath !== href) return false;
    // Already on this page
    if (href === pathname) return true;
    // For base paths, only match exact
    if (href === '/exploration/real-time' || href === '/exploration/historical' ||
        href === '/strategy/real-time' || href === '/strategy/backtesting') {
      return pathname === href;
    }
    return false;
  };

  // Handle navigation with optimistic UI
  const handleNavClick = (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    e.preventDefault();
    if (href === pathname) return; // Already on this page
    setPendingPath(href);
    startTransition(() => {
      router.push(href);
    });
  };

  // Handle archive click
  const handleArchiveClick = async (e: React.MouseEvent, strategySlug: string) => {
    e.preventDefault();
    e.stopPropagation();
    await archiveStrategy(strategySlug);
  };

  // Handle unarchive click
  const handleUnarchiveClick = async (e: React.MouseEvent, strategySlug: string) => {
    e.preventDefault();
    e.stopPropagation();
    await unarchiveStrategy(strategySlug);
  };

  // Check if strategy has notifications configured
  const hasNotifications = useCallback((strategySlug: string) => {
    return notificationSettings.some(s => s.strategy_name === strategySlug && s.enabled);
  }, [notificationSettings]);

  // Get notification settings for a strategy
  const getNotificationSettings = useCallback((strategySlug: string) => {
    return notificationSettings.find(s => s.strategy_name === strategySlug) || null;
  }, [notificationSettings]);

  // Handle notification icon click
  const handleNotificationClick = (e: React.MouseEvent, strategySlug: string) => {
    e.preventDefault();
    e.stopPropagation();
    setNotificationModalStrategy(strategySlug);
    setNotificationModalOpen(true);
  };

  // Handle resize
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing) return;
    const newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, e.clientX));
    setWidth(newWidth);
  }, [isResizing]);

  const handleMouseUp = useCallback(() => {
    if (isResizing) {
      setIsResizing(false);
      localStorage.setItem(WIDTH_STORAGE_KEY, width.toString());
    }
  }, [isResizing, width]);

  // Load width from localStorage
  useEffect(() => {
    const savedWidth = localStorage.getItem(WIDTH_STORAGE_KEY);
    if (savedWidth) {
      const parsed = parseInt(savedWidth, 10);
      if (parsed >= MIN_WIDTH && parsed <= MAX_WIDTH) {
        setWidth(parsed);
      }
    }
  }, []);

  // Resize event listeners
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none';
    }
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing, handleMouseMove, handleMouseUp]);

  return (
    <div className="flex h-screen">
      <div
        ref={sidebarRef}
        className="h-screen bg-card flex flex-col"
        style={{ width: `${width}px` }}
      >

      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-3">
        <Image src="/logo-icon.svg" alt="TradyBull" width={24} height={24} />
        <span className="text-sm font-bold text-foreground tracking-tight">TRADYBULL</span>
      </div>

      {/* Mode Switch */}
      <div className="p-3">
        <ModeSelector
          options={modeOptions}
          value={mode}
          onChange={(value) => {
            const newMode = value as Mode;
            setMode(newMode);
            // Navigate to default page for the new mode
            let targetPath = '/exploration/real-time';
            if (newMode === 'backtesting') {
              targetPath = '/strategy/backtesting/overview';
            } else if (newMode === 'realtime') {
              targetPath = '/strategy/real-time/notifications';
            }
            if (pathname !== targetPath) {
              setPendingPath(targetPath);
              startTransition(() => {
                router.push(targetPath);
              });
            }
          }}
        />
      </div>

      {/* Search */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-7 pr-7 h-6 text-xs"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted-foreground/20 transition-colors"
            >
              <X size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-2">
        {/* Sections */}
        {navigation.map((section) => (
          <div key={section.title} className="mb-1">
            {/* Standalone items (no collapsible header) */}
            {section.isStandalone ? (
              <div>
                {section.items.map((item) => {
                  const isActive = isPathActive(item.href);
                  const isLoading = pendingPath === item.href && isPending;
                  const isNotificationsItem = item.href === '/strategy/real-time/notifications';
                  const isOverviewItem = item.href === '/strategy/backtesting/overview';

                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={(e) => handleNavClick(e, item.href)}
                      title={item.name}
                      className={`h-8 flex items-center gap-2 px-3 text-xs transition-colors ${
                        isActive
                          ? 'text-brand bg-brand/10'
                          : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                      } ${isLoading ? 'opacity-70' : ''}`}
                    >
                      {isNotificationsItem && <Bell size={14} />}
                      {isOverviewItem && <Table size={14} />}
                      {item.name}
                    </Link>
                  );
                })}
              </div>
            ) : (
              <>
                {/* Section Header */}
                <div
                  className="h-8 flex items-center gap-2 pl-3 pr-2 text-[10px] font-semibold text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
                  onClick={() => toggleSection(section.storageKey || section.title)}
                >
                  {expandedSections[section.storageKey || section.title] ? (
                    <ChevronDown size={14} className="text-muted-foreground" />
                  ) : (
                    <ChevronRight size={14} className="text-muted-foreground" />
                  )}
                  <span className="uppercase tracking-wider">{section.title}</span>
                  {section.isArchive && (
                    <span className="ml-auto text-[9px] text-muted-foreground/60">
                      {section.items.length}
                    </span>
                  )}
                  {/* Add Strategy button (Backtesting mode only) */}
                  {section.title === 'Strategies' && mode === 'backtesting' && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setStrategyCreationModalOpen(true);
                          }}
                          className="ml-auto p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted-foreground/20 transition-colors"
                        >
                          <Plus size={14} />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="right">Add Strategy</TooltipContent>
                    </Tooltip>
                  )}
                </div>

                {/* Section Items */}
                {expandedSections[section.storageKey || section.title] && (
                  <div className="ml-4">
                    {section.items.length > 0 ? (
                      section.items.map((item) => {
                        const isActive = isPathActive(item.href);
                        const isLoading = pendingPath === item.href && isPending;
                        const isHovered = hoveredItem === item.href;
                        const showArchiveIcon = item.strategySlug && isHovered && !section.isArchive && mode === 'backtesting';
                        const showRestoreIcon = item.strategySlug && section.isArchive && isHovered;
                        const strategyHasNotifications = item.strategySlug && hasNotifications(item.strategySlug);
                        const showNotificationIcon = item.strategySlug && mode === 'realtime' && (isHovered || strategyHasNotifications);

                        return (
                          <div
                            key={item.href}
                            className="relative group"
                            onMouseEnter={() => setHoveredItem(item.href)}
                            onMouseLeave={() => setHoveredItem(null)}
                          >
                            <Link
                              href={item.href}
                              onClick={(e) => handleNavClick(e, item.href)}
                              title={item.name}
                              className={`block px-4 py-1.5 text-xs transition-colors pr-8 truncate ${
                                isActive
                                  ? 'text-brand bg-brand/10 border-l-2 border-brand'
                                  : 'text-muted-foreground hover:text-foreground hover:bg-muted border-l-2 border-transparent'
                              } ${isLoading ? 'opacity-70' : ''}`}
                            >
                              {item.name}
                            </Link>

                            {/* Archive button */}
                            {showArchiveIcon && (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <button
                                    onClick={(e) => handleArchiveClick(e, item.strategySlug!)}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted-foreground/20 transition-colors"
                                  >
                                    <Archive size={12} />
                                  </button>
                                </TooltipTrigger>
                                <TooltipContent side="right">Archive</TooltipContent>
                              </Tooltip>
                            )}

                            {/* Restore button */}
                            {showRestoreIcon && (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <button
                                    onClick={(e) => handleUnarchiveClick(e, item.strategySlug!)}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted-foreground/20 transition-colors"
                                  >
                                    <ArchiveRestore size={12} />
                                  </button>
                                </TooltipTrigger>
                                <TooltipContent side="right">Restore</TooltipContent>
                              </Tooltip>
                            )}

                            {/* Notification button (Real Time only) */}
                            {showNotificationIcon && (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <button
                                    onClick={(e) => handleNotificationClick(e, item.strategySlug!)}
                                    className={`absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md transition-colors hover:bg-muted-foreground/20 ${
                                      strategyHasNotifications
                                        ? 'text-brand hover:text-brand'
                                        : 'text-muted-foreground hover:text-foreground'
                                    }`}
                                  >
                                    <Bell size={12} />
                                  </button>
                                </TooltipTrigger>
                                <TooltipContent side="right">
                                  {strategyHasNotifications ? 'Edit Notification' : 'Add Notification'}
                                </TooltipContent>
                              </Tooltip>
                            )}
                          </div>
                        );
                      })
                    ) : (
                      <div className="px-4 py-4 text-center">
                        {section.title === 'Strategies' ? (
                          mode === 'backtesting' ? (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setStrategyCreationModalOpen(true)}
                              className="w-full h-8 text-xs border-dashed border-muted-foreground/30 hover:border-brand/50 hover:bg-brand/5 text-muted-foreground hover:text-brand"
                            >
                              <Plus size={12} />
                              Add Strategy
                            </Button>
                          ) : (
                            <p className="text-xs text-muted-foreground/60">
                              Create strategies in Backtesting mode
                            </p>
                          )
                        ) : (
                          <span className="text-xs text-muted-foreground/60">No items</span>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        ))}
      </nav>

      {/* Footer */}
        <div className="px-3 py-2 border-t border-border flex items-center justify-between">
          <div className="text-[10px] text-muted-foreground">v{packageJson.version}</div>
          <button
            onClick={toggleTheme}
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
          </button>
        </div>
      </div>

      {/* Resize handle (acts as border) */}
      <div
        onMouseDown={handleMouseDown}
        className={`h-screen cursor-ew-resize transition-all ${
          isResizing ? 'w-1 bg-muted-foreground/50' : 'w-px bg-border hover:w-1 hover:bg-muted-foreground/30'
        }`}
      />

      {/* Notification Modal */}
      <NotificationModal
        open={notificationModalOpen}
        onOpenChange={setNotificationModalOpen}
        strategies={allStrategies}
        existingSettings={notificationModalStrategy ? getNotificationSettings(notificationModalStrategy) : null}
        defaultStrategy={notificationModalStrategy}
        onSave={saveSettings}
        onTestTelegram={testTelegram}
        onTestDesktop={testDesktop}
      />

      {/* Strategy Creation Modal */}
      <StrategyCreationModal
        open={strategyCreationModalOpen}
        onOpenChange={setStrategyCreationModalOpen}
        onCreated={() => {
          // Refresh strategies list
          refetchStrategies();
        }}
      />

    </div>
  );
}
