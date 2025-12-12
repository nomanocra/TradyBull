'use client';

import { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface NavItem {
  name: string;
  href: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const navigation: NavSection[] = [
  {
    title: 'Real Time Strat.',
    items: [
      { name: 'Bollinger', href: '/strategies/bollinger' },
      { name: 'MACD', href: '/strategies/macd' },
      { name: 'Ichimoku', href: '/strategies/ichimoku' },
      { name: 'Moving Averages', href: '/strategies/moving-averages' },
      { name: 'RSI', href: '/strategies/rsi' },
    ],
  },
  {
    title: 'Backtesting',
    items: [],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    'Real Time Strat.': true,
    'Backtesting': false,
  });

  const toggleSection = (title: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [title]: !prev[title],
    }));
  };

  const isExplorationActive = pathname === '/';

  return (
    <div className="w-52 h-screen bg-[#0d0d0d] border-r border-[#1a1a1a] flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-3">
        <Image src="/logo-icon.svg" alt="TradyBull" width={24} height={24} />
        <span className="text-sm font-bold text-white tracking-tight">TRADYBULL</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-2">
        {/* Exploration - Standalone link */}
        <Link
          href="/"
          className={`block mx-2 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
            isExplorationActive
              ? 'text-[#C59471] bg-[#C59471]/10'
              : 'text-gray-300 hover:text-white hover:bg-[#141414]'
          }`}
        >
          Exploration
        </Link>

        <div className="my-3 mx-3 border-t border-[#1a1a1a]" />

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
                    const isActive = pathname === item.href;
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
                    No strategies yet
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
