'use client';

import { useState, useEffect, useTransition, useMemo } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { ChevronDown, ChevronRight, Compass, Play, Sun, Moon, Archive, ArchiveRestore } from 'lucide-react';
import { GroupButton } from '@/components/ui/group-button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useStrategies, StrategyConfig } from '@/hooks/useStrategies';
import packageJson from '../../../package.json';

const STORAGE_KEY = 'tradybull-sidebar-sections';
const MODE_STORAGE_KEY = 'tradybull-sidebar-mode';
const THEME_STORAGE_KEY = 'tradybull-theme';

type Mode = 'exploration' | 'strategy';

interface NavItem {
  name: string;
  href: string;
  strategySlug?: string; // For archive functionality
}

interface NavSection {
  title: string;
  items: NavItem[];
  isArchive?: boolean;
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

// Strategy navigation is now generated dynamically from the API
function generateStrategyNavigation(
  strategies: StrategyConfig[],
  archivedStrategies: StrategyConfig[]
): NavSection[] {
  const sections: NavSection[] = [
    {
      title: 'Real Time',
      items: strategies.map((s) => ({
        name: s.display_name,
        href: `/strategy/real-time/${s.name}`,
        strategySlug: s.name,
      })),
    },
    {
      title: 'Backtesting',
      items: [
        { name: 'Overview', href: '/strategy/backtesting/overview' },
        ...strategies.map((s) => ({
          name: s.display_name,
          href: `/strategy/backtesting/${s.name}`,
          strategySlug: s.name,
        })),
      ],
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

const modeOptions = [
  { value: 'exploration', label: 'Exploration', icon: <Compass size={12} /> },
  { value: 'strategy', label: 'Strategy', icon: <Play size={12} /> },
];

const defaultSections: Record<string, boolean> = {
  'Real Time': true,
  'Historical Data': true,
  'Backtesting': true,
  'Archive': false, // Collapsed by default
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

  // Fetch strategies from API
  const { strategies, archivedStrategies, archiveStrategy, unarchiveStrategy } = useStrategies();

  // Generate strategy navigation dynamically
  const strategyNavigation = useMemo(
    () => generateStrategyNavigation(strategies, archivedStrategies),
    [strategies, archivedStrategies]
  );

  // Clear pending path when navigation completes
  useEffect(() => {
    if (pendingPath && pathname === pendingPath) {
      setPendingPath(null);
    }
  }, [pathname, pendingPath]);

  // Sync mode with current URL path
  useEffect(() => {
    if (pathname.startsWith('/strategy')) {
      setMode('strategy');
    } else if (pathname.startsWith('/exploration')) {
      setMode('exploration');
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
    if (pathname.startsWith('/strategy')) {
      setMode('strategy');
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

  const navigation = mode === 'exploration' ? explorationNavigation : strategyNavigation;

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

  return (
    <div className="w-52 h-screen bg-card border-r border-border flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-3">
        <Image src="/logo-icon.svg" alt="TradyBull" width={24} height={24} />
        <span className="text-sm font-bold text-foreground tracking-tight">TRADYBULL</span>
      </div>

      {/* Mode Switch */}
      <div className="p-3">
        <GroupButton
          options={modeOptions}
          value={mode}
          onChange={(value) => setMode(value as Mode)}
        />
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-2">
        {/* Sections */}
        {navigation.map((section) => (
          <div key={section.title} className="mb-1">
            {/* Section Header */}
            <button
              onClick={() => toggleSection(section.title)}
              className="w-full flex items-center gap-2 px-3 py-2 text-[10px] font-semibold text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              {expandedSections[section.title] ? (
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
            </button>

            {/* Section Items */}
            {expandedSections[section.title] && (
              <div className="ml-4">
                {section.items.length > 0 ? (
                  section.items.map((item) => {
                    const isActive = isPathActive(item.href);
                    const isLoading = pendingPath === item.href && isPending;
                    const isHovered = hoveredItem === item.href;
                    const showArchiveIcon = item.strategySlug && isHovered && !section.isArchive && section.title !== 'Real Time';
                    const showRestoreIcon = item.strategySlug && isHovered && section.isArchive;

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
                          className={`block px-4 py-1.5 text-xs transition-colors pr-8 ${
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
                                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground hover:bg-muted-foreground/20 transition-colors"
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
                                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-muted-foreground hover:text-foreground hover:bg-muted-foreground/20 transition-colors"
                              >
                                <ArchiveRestore size={12} />
                              </button>
                            </TooltipTrigger>
                            <TooltipContent side="right">Restore</TooltipContent>
                          </Tooltip>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div className="px-4 py-1.5 text-xs text-muted-foreground italic">
                    Coming soon
                  </div>
                )}
              </div>
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
  );
}
