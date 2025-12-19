'use client';

import { useState, useEffect, useTransition, useMemo } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { ChevronDown, ChevronRight, Compass, Play, Sun, Moon } from 'lucide-react';
import { GroupButton } from '@/components/ui/group-button';
import { useStrategies, StrategyConfig } from '@/hooks/useStrategies';

const STORAGE_KEY = 'tradybull-sidebar-sections';
const MODE_STORAGE_KEY = 'tradybull-sidebar-mode';
const THEME_STORAGE_KEY = 'tradybull-theme';

type Mode = 'exploration' | 'strategy';

interface NavItem {
  name: string;
  href: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
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
function generateStrategyNavigation(strategies: StrategyConfig[]): NavSection[] {
  return [
    {
      title: 'Real Time',
      items: strategies.map((s) => ({
        name: s.display_name,
        href: `/strategy/real-time/${s.name}`,
      })),
    },
    {
      title: 'Backtesting',
      items: strategies.map((s) => ({
        name: s.display_name,
        href: `/strategy/backtesting/${s.name}`,
      })),
    },
  ];
}

const modeOptions = [
  { value: 'exploration', label: 'Exploration', icon: <Compass size={12} /> },
  { value: 'strategy', label: 'Strategy', icon: <Play size={12} /> },
];

const defaultSections: Record<string, boolean> = {
  'Real Time': true,
  'Historical Data': true,
  'Backtesting': true,
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

  // Fetch strategies from API
  const { strategies } = useStrategies();

  // Generate strategy navigation dynamically
  const strategyNavigation = useMemo(
    () => generateStrategyNavigation(strategies),
    [strategies]
  );

  // Clear pending path when navigation completes
  useEffect(() => {
    if (pendingPath && pathname === pendingPath) {
      setPendingPath(null);
    }
  }, [pathname, pendingPath]);

  // Load from localStorage after hydration
  useEffect(() => {
    const savedSections = localStorage.getItem(STORAGE_KEY);
    if (savedSections) {
      try {
        setExpandedSections(JSON.parse(savedSections));
      } catch {
        // Invalid JSON, use defaults
      }
    }
    const savedMode = localStorage.getItem(MODE_STORAGE_KEY) as Mode | null;
    if (savedMode === 'exploration' || savedMode === 'strategy') {
      setMode(savedMode);
    }
    const savedTheme = localStorage.getItem(THEME_STORAGE_KEY) as Theme | null;
    if (savedTheme === 'dark' || savedTheme === 'light') {
      setTheme(savedTheme);
      document.documentElement.classList.toggle('dark', savedTheme === 'dark');
    }
    setIsHydrated(true);
  }, []);

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
            </button>

            {/* Section Items */}
            {expandedSections[section.title] && (
              <div className="ml-4">
                {section.items.length > 0 ? (
                  section.items.map((item) => {
                    const isActive = isPathActive(item.href);
                    const isLoading = pendingPath === item.href && isPending;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={(e) => handleNavClick(e, item.href)}
                        className={`block px-4 py-1.5 text-xs transition-colors ${
                          isActive
                            ? 'text-brand bg-brand/10 border-l-2 border-brand'
                            : 'text-muted-foreground hover:text-foreground hover:bg-muted border-l-2 border-transparent'
                        } ${isLoading ? 'opacity-70' : ''}`}
                      >
                        {item.name}
                      </Link>
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
        <div className="text-[10px] text-muted-foreground">v0.1.0</div>
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
