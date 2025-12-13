'use client';

import { useState, useCallback, useMemo, useEffect } from 'react';
import { TradingDashboard } from './trading-dashboard';

const STORAGE_KEY = 'tradybull-exploration-indicators';

interface IndicatorToggle {
  id: string;
  label: string;
  shortLabel: string;
  color: string;
  prop: 'showBollinger' | 'showMACD' | 'showIchimoku' | 'showMovingAverages' | 'showRSI';
}

const indicators: IndicatorToggle[] = [
  { id: 'bollinger', label: 'Bollinger Bands', shortLabel: 'BB', color: '#3b82f6', prop: 'showBollinger' },
  { id: 'macd', label: 'MACD', shortLabel: 'MACD', color: '#f97316', prop: 'showMACD' },
  { id: 'ichimoku', label: 'Ichimoku Cloud', shortLabel: 'Ichimoku', color: '#8b5cf6', prop: 'showIchimoku' },
  { id: 'ma', label: 'Moving Averages', shortLabel: 'MA', color: '#eab308', prop: 'showMovingAverages' },
  { id: 'rsi', label: 'Stochastic RSI', shortLabel: 'Stoch', color: '#10b981', prop: 'showRSI' },
];

export function ExplorationDashboard() {
  const [activeIndicators, setActiveIndicators] = useState<Set<string>>(() => {
    // Load from localStorage on initial render (client-side only)
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        try {
          return new Set(JSON.parse(saved));
        } catch {
          return new Set();
        }
      }
    }
    return new Set();
  });

  // Save to localStorage when indicators change
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...activeIndicators]));
  }, [activeIndicators]);

  // Memoize toggle function to prevent re-renders
  const toggleIndicator = useCallback((id: string) => {
    setActiveIndicators(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  // Memoize props object for TradingDashboard
  const indicatorProps = useMemo(() => {
    return indicators.reduce((acc, indicator) => {
      acc[indicator.prop] = activeIndicators.has(indicator.id);
      return acc;
    }, {} as Record<string, boolean>);
  }, [activeIndicators]);

  const indicatorBar = (
    <div className="flex items-center gap-1.5 px-2 py-1 bg-[#0d0d0d] border-b border-[#1a1a1a]">
      <span className="text-[9px] text-gray-500 uppercase tracking-wider mr-1">Indicateurs</span>
      {indicators.map((indicator) => {
        const isActive = activeIndicators.has(indicator.id);
        return (
          <button
            key={indicator.id}
            onClick={() => toggleIndicator(indicator.id)}
            className={`
              px-1.5 py-0.5 rounded-full text-[9px] font-medium
              transition-all duration-200 ease-out
              border
              ${isActive
                ? 'text-white border-transparent'
                : 'text-gray-500 border-[#2a2a2a] hover:border-[#3a3a3a] hover:text-gray-400'
              }
            `}
            style={{
              backgroundColor: isActive ? indicator.color : 'transparent',
              boxShadow: isActive ? `0 0 8px ${indicator.color}40` : 'none',
            }}
            title={indicator.label}
          >
            {indicator.shortLabel}
          </button>
        );
      })}
      {activeIndicators.size === 0 && (
        <span className="text-[9px] text-gray-600 italic ml-1">
          Sélectionnez un indicateur
        </span>
      )}
    </div>
  );

  return (
    <TradingDashboard
      pageName="Exploration"
      topBar={indicatorBar}
      {...indicatorProps}
    />
  );
}
