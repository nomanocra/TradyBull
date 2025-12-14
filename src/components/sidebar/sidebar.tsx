'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronDown, ChevronRight, Compass, Play } from 'lucide-react';
import { GroupButton } from '@/components/ui/group-button';

const STORAGE_KEY = 'tradybull-sidebar-sections';
const MODE_STORAGE_KEY = 'tradybull-sidebar-mode';

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

const strategyNavigation: NavSection[] = [
  {
    title: 'Real Time',
    items: [],
  },
  {
    title: 'Backtesting',
    items: [],
  },
];

const modeOptions = [
  { value: 'exploration', label: 'Exploration', icon: <Compass size={12} /> },
  { value: 'strategy', label: 'Strategy', icon: <Play size={12} /> },
];

const defaultSections: Record<string, boolean> = {
  'Real Time': true,
  'Historical Data': true,
  'Backtesting': true,
};

export function Sidebar() {
  const pathname = usePathname();
  const [mode, setMode] = useState<Mode>('exploration');
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>(defaultSections);
  const [isHydrated, setIsHydrated] = useState(false);

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

  const toggleSection = (title: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [title]: !prev[title],
    }));
  };

  const navigation = mode === 'exploration' ? explorationNavigation : strategyNavigation;

  // Check if a path is active (exact match or starts with for nested routes)
  const isPathActive = (href: string) => {
    if (href === pathname) return true;
    // For real-time and historical base paths, only match exact
    if (href === '/exploration/real-time' || href === '/exploration/historical') {
      return pathname === href;
    }
    return false;
  };

  return (
    <div className="w-52 h-screen bg-[#0d0d0d] border-r border-[#1a1a1a] flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-3">
        <Image src="/logo-icon.svg" alt="TradyBull" width={24} height={24} />
        <span className="text-sm font-bold text-white tracking-tight">TRADYBULL</span>
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
              className="w-full flex items-center gap-2 px-3 py-2 text-[10px] font-semibold text-gray-400 hover:text-gray-300 hover:bg-[#141414] transition-colors"
            >
              {expandedSections[section.title] ? (
                <ChevronDown size={14} className="text-gray-500" />
              ) : (
                <ChevronRight size={14} className="text-gray-500" />
              )}
              <span className="uppercase tracking-wider">{section.title}</span>
            </button>

            {/* Section Items */}
            {expandedSections[section.title] && (
              <div className="ml-4">
                {section.items.length > 0 ? (
                  section.items.map((item) => {
                    const isActive = isPathActive(item.href);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        className={`block px-4 py-1.5 text-xs transition-colors ${
                          isActive
                            ? 'text-[#C59471] bg-[#C59471]/10 border-l-2 border-[#C59471]'
                            : 'text-gray-300 hover:text-white hover:bg-[#141414] border-l-2 border-transparent'
                        }`}
                      >
                        {item.name}
                      </Link>
                    );
                  })
                ) : (
                  <div className="px-4 py-1.5 text-xs text-gray-600 italic">
                    Coming soon
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-3 py-2 border-t border-[#1a1a1a]">
        <div className="text-[10px] text-gray-600">v0.1.0</div>
      </div>
    </div>
  );
}
