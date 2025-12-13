'use client';

import { useEffect, useRef, useMemo, useState, useCallback, memo } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickSeries, LineSeries, HistogramSeries, CandlestickData, LineData, HistogramData, Time, BusinessDay, createSeriesMarkers, SeriesMarker, ISeriesMarkersPluginApi } from 'lightweight-charts';
import { CandleData, TimeFrame } from '@/types/market';

interface CandlestickChartProps {
  title: string;
  timeframe: TimeFrame;
  data: CandleData[];
  isLoading?: boolean;
  showBollinger?: boolean;
  showBollingerSignals?: boolean;
  showMACD?: boolean;
  showIchimoku?: boolean;
  showMovingAverages?: boolean;
  showRSI?: boolean;
}

type BuySignal = SeriesMarker<Time>;

// Cache for timezone offsets to avoid repeated calculations
const timezoneOffsetCache = new Map<number, number>();

// Bollinger Bands settings
const BB_PERIOD = 20;
const BB_STD_DEV = 2;

// MACD settings
const MACD_FAST = 12;
const MACD_SLOW = 26;
const MACD_SIGNAL = 9;

// Ichimoku settings
const ICHIMOKU_TENKAN = 9;
const ICHIMOKU_KIJUN = 26;
const ICHIMOKU_SENKOU_B = 52;
const ICHIMOKU_DISPLACEMENT = 26;

// Moving Averages settings
const MA_SHORT = 20;
const MA_MEDIUM = 50;
const MA_LONG = 200;

// Stochastic RSI settings
const STOCH_RSI_PERIOD = 14;
const STOCH_RSI_K_SMOOTH = 3;
const STOCH_RSI_D_SMOOTH = 3;

// Calculate SMA
function calculateSMA(data: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else {
      const sum = data.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
      result.push(sum / period);
    }
  }
  return result;
}

// Calculate EMA
function calculateEMA(data: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  const multiplier = 2 / (period + 1);

  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else if (i === period - 1) {
      const sum = data.slice(0, period).reduce((a, b) => a + b, 0);
      result.push(sum / period);
    } else {
      const prevEMA = result[i - 1];
      if (prevEMA !== null) {
        result.push((data[i] - prevEMA) * multiplier + prevEMA);
      } else {
        result.push(null);
      }
    }
  }
  return result;
}

// Calculate Standard Deviation
function calculateStdDev(data: number[], period: number, sma: (number | null)[]): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1 || sma[i] === null) {
      result.push(null);
    } else {
      const slice = data.slice(i - period + 1, i + 1);
      const mean = sma[i]!;
      const squaredDiffs = slice.map(val => Math.pow(val - mean, 2));
      const variance = squaredDiffs.reduce((a, b) => a + b, 0) / period;
      result.push(Math.sqrt(variance));
    }
  }
  return result;
}

// Calculate Bollinger Bands
function calculateBollingerBands(closes: number[]) {
  const sma = calculateSMA(closes, BB_PERIOD);
  const stdDev = calculateStdDev(closes, BB_PERIOD, sma);

  const upper: (number | null)[] = [];
  const lower: (number | null)[] = [];

  for (let i = 0; i < closes.length; i++) {
    if (sma[i] !== null && stdDev[i] !== null) {
      upper.push(sma[i]! + BB_STD_DEV * stdDev[i]!);
      lower.push(sma[i]! - BB_STD_DEV * stdDev[i]!);
    } else {
      upper.push(null);
      lower.push(null);
    }
  }

  return { middle: sma, upper, lower };
}

// Calculate MACD
function calculateMACD(closes: number[]) {
  const emaFast = calculateEMA(closes, MACD_FAST);
  const emaSlow = calculateEMA(closes, MACD_SLOW);

  const macdLine: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (emaFast[i] !== null && emaSlow[i] !== null) {
      macdLine.push(emaFast[i]! - emaSlow[i]!);
    } else {
      macdLine.push(null);
    }
  }

  // Filter out nulls for signal calculation
  const macdValues = macdLine.filter(v => v !== null) as number[];
  const signalValues = calculateEMA(macdValues, MACD_SIGNAL);

  // Map signal back to original indices
  const signal: (number | null)[] = [];
  let signalIdx = 0;
  for (let i = 0; i < macdLine.length; i++) {
    if (macdLine[i] !== null) {
      signal.push(signalValues[signalIdx]);
      signalIdx++;
    } else {
      signal.push(null);
    }
  }

  // Calculate histogram
  const histogram: (number | null)[] = [];
  for (let i = 0; i < macdLine.length; i++) {
    if (macdLine[i] !== null && signal[i] !== null) {
      histogram.push(macdLine[i]! - signal[i]!);
    } else {
      histogram.push(null);
    }
  }

  return { macdLine, signal, histogram };
}

// Calculate Ichimoku Cloud
function calculateIchimoku(highs: number[], lows: number[], closes: number[]) {
  const length = highs.length;

  // Helper to calculate (highest high + lowest low) / 2 over a period
  const calcMidpoint = (h: number[], l: number[], period: number, index: number): number | null => {
    if (index < period - 1) return null;
    let highestHigh = -Infinity;
    let lowestLow = Infinity;
    for (let i = index - period + 1; i <= index; i++) {
      if (h[i] > highestHigh) highestHigh = h[i];
      if (l[i] < lowestLow) lowestLow = l[i];
    }
    return (highestHigh + lowestLow) / 2;
  };

  // Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
  const tenkan: (number | null)[] = [];
  for (let i = 0; i < length; i++) {
    tenkan.push(calcMidpoint(highs, lows, ICHIMOKU_TENKAN, i));
  }

  // Kijun-sen (Base Line): (26-period high + 26-period low) / 2
  const kijun: (number | null)[] = [];
  for (let i = 0; i < length; i++) {
    kijun.push(calcMidpoint(highs, lows, ICHIMOKU_KIJUN, i));
  }

  // Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2, plotted 26 periods ahead
  const senkouA: (number | null)[] = [];
  for (let i = 0; i < length; i++) {
    if (tenkan[i] !== null && kijun[i] !== null) {
      senkouA.push((tenkan[i]! + kijun[i]!) / 2);
    } else {
      senkouA.push(null);
    }
  }

  // Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2, plotted 26 periods ahead
  const senkouB: (number | null)[] = [];
  for (let i = 0; i < length; i++) {
    senkouB.push(calcMidpoint(highs, lows, ICHIMOKU_SENKOU_B, i));
  }

  // Chikou Span (Lagging Span): Close plotted 26 periods back
  const chikou: (number | null)[] = closes.slice();

  return { tenkan, kijun, senkouA, senkouB, chikou };
}

// Calculate Stochastic RSI
// Returns { k: %K line, d: %D line (signal) }
function calculateStochRSI(closes: number[]): { k: (number | null)[], d: (number | null)[] } {
  const period = STOCH_RSI_PERIOD;
  const kSmooth = STOCH_RSI_K_SMOOTH;
  const dSmooth = STOCH_RSI_D_SMOOTH;

  // First calculate RSI
  const rsi: (number | null)[] = [];

  if (closes.length < period + 1) {
    return {
      k: closes.map(() => null),
      d: closes.map(() => null)
    };
  }

  // Calculate price changes
  const changes: number[] = [];
  for (let i = 1; i < closes.length; i++) {
    changes.push(closes[i] - closes[i - 1]);
  }

  // First period values are null
  for (let i = 0; i < period; i++) {
    rsi.push(null);
  }

  // Calculate initial average gain and loss
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 0; i < period; i++) {
    if (changes[i] > 0) {
      avgGain += changes[i];
    } else {
      avgLoss += Math.abs(changes[i]);
    }
  }
  avgGain /= period;
  avgLoss /= period;

  // Calculate first RSI
  let rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
  rsi.push(100 - (100 / (1 + rs)));

  // Calculate subsequent RSI values
  for (let i = period; i < changes.length; i++) {
    const change = changes[i];
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? Math.abs(change) : 0;

    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;

    rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsi.push(100 - (100 / (1 + rs)));
  }

  // Now apply stochastic formula to RSI values
  const stochRsi: (number | null)[] = [];
  const minPeriod = period + period - 1; // Need enough RSI values

  for (let i = 0; i < closes.length; i++) {
    if (i < minPeriod || rsi[i] === null) {
      stochRsi.push(null);
    } else {
      // Get RSI values for lookback period
      const rsiSlice: number[] = [];
      for (let j = i - period + 1; j <= i; j++) {
        if (rsi[j] !== null) {
          rsiSlice.push(rsi[j]!);
        }
      }

      if (rsiSlice.length < period) {
        stochRsi.push(null);
      } else {
        const minRsi = Math.min(...rsiSlice);
        const maxRsi = Math.max(...rsiSlice);
        const range = maxRsi - minRsi;

        if (range === 0) {
          stochRsi.push(50); // Middle value when no range
        } else {
          stochRsi.push(((rsi[i]! - minRsi) / range) * 100);
        }
      }
    }
  }

  // Calculate %K (SMA of stochRsi)
  const k: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < minPeriod + kSmooth - 1) {
      k.push(null);
    } else {
      const slice: number[] = [];
      for (let j = i - kSmooth + 1; j <= i; j++) {
        if (stochRsi[j] !== null) {
          slice.push(stochRsi[j]!);
        }
      }
      if (slice.length === kSmooth) {
        k.push(slice.reduce((a, b) => a + b, 0) / kSmooth);
      } else {
        k.push(null);
      }
    }
  }

  // Calculate %D (SMA of %K)
  const d: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < minPeriod + kSmooth + dSmooth - 2) {
      d.push(null);
    } else {
      const slice: number[] = [];
      for (let j = i - dSmooth + 1; j <= i; j++) {
        if (k[j] !== null) {
          slice.push(k[j]!);
        }
      }
      if (slice.length === dSmooth) {
        d.push(slice.reduce((a, b) => a + b, 0) / dSmooth);
      } else {
        d.push(null);
      }
    }
  }

  return { k, d };
}

export function CandlestickChart({
  title,
  timeframe,
  data,
  isLoading = false,
  showBollinger = false,
  showBollingerSignals = false,
  showMACD = false,
  showIchimoku = false,
  showMovingAverages = false,
  showRSI = false
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mainChartContainerRef = useRef<HTMLDivElement>(null);
  const macdChartContainerRef = useRef<HTMLDivElement>(null);
  const rsiChartContainerRef = useRef<HTMLDivElement>(null);
  const mainChartRef = useRef<IChartApi | null>(null);
  const macdChartRef = useRef<IChartApi | null>(null);
  const rsiChartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  // Bollinger refs
  const bbUpperRef = useRef<ISeriesApi<'Line'> | null>(null);
  const bbMiddleRef = useRef<ISeriesApi<'Line'> | null>(null);
  const bbLowerRef = useRef<ISeriesApi<'Line'> | null>(null);
  // MACD refs
  const macdLineRef = useRef<ISeriesApi<'Line'> | null>(null);
  const macdSignalRef = useRef<ISeriesApi<'Line'> | null>(null);
  const macdHistogramRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  // Ichimoku refs
  const ichimokuTenkanRef = useRef<ISeriesApi<'Line'> | null>(null);
  const ichimokuKijunRef = useRef<ISeriesApi<'Line'> | null>(null);
  const ichimokuSenkouARef = useRef<ISeriesApi<'Line'> | null>(null);
  const ichimokuSenkouBRef = useRef<ISeriesApi<'Line'> | null>(null);
  const ichimokuChikouRef = useRef<ISeriesApi<'Line'> | null>(null);
  // Moving Averages refs
  const maShortRef = useRef<ISeriesApi<'Line'> | null>(null);
  const maMediumRef = useRef<ISeriesApi<'Line'> | null>(null);
  const maLongRef = useRef<ISeriesApi<'Line'> | null>(null);
  // RSI refs
  const stochRsiKRef = useRef<ISeriesApi<'Line'> | null>(null);
  const stochRsiDRef = useRef<ISeriesApi<'Line'> | null>(null);
  const stochRsiOverboughtRef = useRef<ISeriesApi<'Line'> | null>(null);
  const stochRsiOversoldRef = useRef<ISeriesApi<'Line'> | null>(null);
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const isInitialLoadRef = useRef(true);

  // Resizable divider states (separate for MACD and RSI)
  const [macdHeightPercent, setMacdHeightPercent] = useState(20);
  const [rsiHeightPercent, setRsiHeightPercent] = useState(20);
  const [draggingDivider, setDraggingDivider] = useState<'macd' | 'rsi' | null>(null);

  const lastPrice = data.length > 0 ? data[data.length - 1].close : null;
  const prevPrice = data.length > 1 ? data[data.length - 2].close : null;
  const priceChange = lastPrice && prevPrice ? ((lastPrice - prevPrice) / prevPrice) * 100 : null;

  // Handle divider drag
  const handleMouseDown = useCallback((divider: 'macd' | 'rsi') => (e: React.MouseEvent) => {
    e.preventDefault();
    setDraggingDivider(divider);
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!draggingDivider || !containerRef.current) return;

    const containerRect = containerRef.current.getBoundingClientRect();
    const containerHeight = containerRect.height;
    const mouseY = e.clientY - containerRect.top;

    // Calculate heights based on which divider is being dragged
    if (draggingDivider === 'macd') {
      // MACD divider - calculate from current position
      const rsiHeight = showRSI ? rsiHeightPercent : 0;
      const availableHeight = containerHeight * (1 - rsiHeight / 100);
      const macdTop = mouseY;
      const macdHeight = availableHeight - macdTop;
      const newPercent = (macdHeight / containerHeight) * 100;
      setMacdHeightPercent(Math.min(40, Math.max(10, newPercent)));
    } else if (draggingDivider === 'rsi') {
      // RSI divider - calculate from bottom
      const rsiHeight = containerHeight - mouseY;
      const newPercent = (rsiHeight / containerHeight) * 100;
      setRsiHeightPercent(Math.min(40, Math.max(10, newPercent)));
    }
  }, [draggingDivider, showRSI, rsiHeightPercent]);

  const handleMouseUp = useCallback(() => {
    setDraggingDivider(null);
  }, []);

  // Add/remove mouse event listeners for dragging
  useEffect(() => {
    if (draggingDivider) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'row-resize';
      document.body.style.userSelect = 'none';
    } else {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [draggingDivider, handleMouseMove, handleMouseUp]);

  // Pre-compute times once with memoization
  const chartTimes = useMemo(() => {
    return data.map((candle) => {
      const hourKey = Math.floor(candle.time / 3600) * 3600;
      let offset = timezoneOffsetCache.get(hourKey);
      if (offset === undefined) {
        const date = new Date(candle.time * 1000);
        const parisTime = new Date(date.toLocaleString('en-US', { timeZone: 'Europe/Paris' }));
        const utcTime = new Date(date.toLocaleString('en-US', { timeZone: 'UTC' }));
        offset = (parisTime.getTime() - utcTime.getTime()) / 1000;
        timezoneOffsetCache.set(hourKey, offset);
      }
      const adjustedTime = candle.time + offset;

      if (timeframe === '1day') {
        const d = new Date(adjustedTime * 1000);
        return {
          year: d.getFullYear(),
          month: d.getMonth() + 1,
          day: d.getDate(),
        } as BusinessDay;
      }
      return adjustedTime as Time;
    });
  }, [data, timeframe]);

  // Calculate indicators ONLY when needed (conditional memoization)
  const bollingerData = useMemo(() => {
    if (!showBollinger || data.length === 0) return null;
    const closes = data.map(d => d.close);
    return calculateBollingerBands(closes);
  }, [data, showBollinger]);

  // Calculate Bollinger buy signals: when candle closes below lower band
  // Signal appears on the NEXT candle, and no consecutive signals until price goes back above lower band
  const bollingerBuySignals = useMemo(() => {
    if (!showBollingerSignals || !bollingerData || data.length < 2) return [];

    const signals: BuySignal[] = [];
    let waitingForRecovery = false; // Flag to prevent consecutive signals

    for (let i = 1; i < data.length; i++) {
      const prevCandle = data[i - 1];
      const prevLowerBand = bollingerData.lower[i - 1];
      const currentLowerBand = bollingerData.lower[i];

      if (prevLowerBand === null) continue;

      // Check if price recovered above lower band (reset the flag)
      if (waitingForRecovery && currentLowerBand !== null && data[i].close > currentLowerBand) {
        waitingForRecovery = false;
      }

      // If previous candle closed below lower band and we're not waiting for recovery
      if (!waitingForRecovery && prevCandle.close < prevLowerBand) {
        signals.push({
          time: data[i].time as Time,
          position: 'belowBar',
          color: '#eab308', // Yellow
          shape: 'arrowUp',
          text: 'Buy',
        });
        waitingForRecovery = true; // Wait for price to recover before next signal
      }
    }
    return signals;
  }, [data, bollingerData, showBollingerSignals]);

  const macdData = useMemo(() => {
    if (!showMACD || data.length === 0) return null;
    const closes = data.map(d => d.close);
    return calculateMACD(closes);
  }, [data, showMACD]);

  const ichimokuData = useMemo(() => {
    if (!showIchimoku || data.length === 0) return null;
    const highs = data.map(d => d.high);
    const lows = data.map(d => d.low);
    const closes = data.map(d => d.close);
    return calculateIchimoku(highs, lows, closes);
  }, [data, showIchimoku]);

  const stochRsiData = useMemo(() => {
    if (!showRSI || data.length === 0) return null;
    const closes = data.map(d => d.close);
    return calculateStochRSI(closes);
  }, [data, showRSI]);

  const movingAveragesData = useMemo(() => {
    if (!showMovingAverages || data.length === 0) return null;
    const closes = data.map(d => d.close);
    return {
      short: calculateSMA(closes, MA_SHORT),
      medium: calculateSMA(closes, MA_MEDIUM),
      long: calculateSMA(closes, MA_LONG),
    };
  }, [data, showMovingAverages]);

  // Initialize charts
  useEffect(() => {
    if (!mainChartContainerRef.current) return;
    if (showMACD && !macdChartContainerRef.current) return;
    if (showRSI && !rsiChartContainerRef.current) return;

    // Fixed price scale width to ensure alignment between charts
    const PRICE_SCALE_WIDTH = 85;

    // Determine if time axis should be visible on main chart
    const showTimeAxisOnMain = !showMACD && !showRSI;

    // Main chart with candlesticks and overlays
    const mainChart = createChart(mainChartContainerRef.current, {
      layout: {
        background: { color: '#0d0d0d' },
        textColor: '#6b7280',
        fontSize: 10,
      },
      grid: {
        vertLines: { color: '#1a1a1a' },
        horzLines: { color: '#1a1a1a' },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: '#4b5563', width: 1, style: 2, labelVisible: showTimeAxisOnMain, labelBackgroundColor: '#1f2937' },
        horzLine: { color: '#4b5563', width: 1, style: 2, labelBackgroundColor: '#1f2937' },
      },
      rightPriceScale: {
        borderColor: '#1a1a1a',
        scaleMargins: { top: 0.1, bottom: 0.1 },
        minimumWidth: PRICE_SCALE_WIDTH,
      },
      localization: { locale: 'fr-FR' },
      timeScale: {
        borderColor: '#1a1a1a',
        visible: showTimeAxisOnMain,
        timeVisible: timeframe !== '1day',
        secondsVisible: false,
        rightOffset: 5,
      },
    });

    // MACD chart - separate chart
    let macdChart: IChartApi | null = null;
    if (showMACD && macdChartContainerRef.current) {
      // Time axis visible only if RSI is not shown (MACD is the bottom chart)
      const showTimeAxisOnMacd = !showRSI;
      macdChart = createChart(macdChartContainerRef.current, {
        layout: {
          background: { color: '#141414' },
          textColor: '#6b7280',
          fontSize: 10,
        },
        grid: {
          vertLines: { color: '#1a1a1a' },
          horzLines: { color: '#1a1a1a' },
        },
        crosshair: {
          mode: 1,
          vertLine: { color: '#4b5563', width: 1, style: 2, labelVisible: showTimeAxisOnMacd, labelBackgroundColor: '#1f2937' },
          horzLine: { color: '#4b5563', width: 1, style: 2, labelBackgroundColor: '#1f2937' },
        },
        rightPriceScale: {
          borderColor: '#1a1a1a',
          scaleMargins: { top: 0.05, bottom: 0.05 },
          minimumWidth: PRICE_SCALE_WIDTH,
        },
        localization: { locale: 'fr-FR' },
        timeScale: {
          borderColor: '#1a1a1a',
          visible: showTimeAxisOnMacd,
          timeVisible: timeframe !== '1day',
          secondsVisible: false,
          rightOffset: 5,
        },
      });
    }

    // RSI chart - separate chart (always at bottom when visible)
    let rsiChart: IChartApi | null = null;
    if (showRSI && rsiChartContainerRef.current) {
      rsiChart = createChart(rsiChartContainerRef.current, {
        layout: {
          background: { color: '#141414' },
          textColor: '#6b7280',
          fontSize: 10,
        },
        grid: {
          vertLines: { color: '#1a1a1a' },
          horzLines: { color: '#1a1a1a' },
        },
        crosshair: {
          mode: 1,
          vertLine: { color: '#4b5563', width: 1, style: 2, labelBackgroundColor: '#1f2937' },
          horzLine: { color: '#4b5563', width: 1, style: 2, labelBackgroundColor: '#1f2937' },
        },
        rightPriceScale: {
          borderColor: '#1a1a1a',
          scaleMargins: { top: 0.05, bottom: 0.05 },
          minimumWidth: PRICE_SCALE_WIDTH,
        },
        localization: { locale: 'fr-FR' },
        timeScale: {
          borderColor: '#1a1a1a',
          visible: true, // RSI is always at bottom, so time axis is always visible
          timeVisible: timeframe !== '1day',
          secondsVisible: false,
          rightOffset: 5,
        },
      });
    }

    // Sync visible range between all charts
    let isSyncingRange = false;
    const syncRange = (range: { from: number; to: number } | null, source: 'main' | 'macd' | 'rsi') => {
      if (isSyncingRange || !range) return;
      isSyncingRange = true;
      if (source !== 'main' && mainChart) mainChart.timeScale().setVisibleLogicalRange(range);
      if (source !== 'macd' && macdChart) macdChart.timeScale().setVisibleLogicalRange(range);
      if (source !== 'rsi' && rsiChart) rsiChart.timeScale().setVisibleLogicalRange(range);
      isSyncingRange = false;
    };

    mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => syncRange(range, 'main'));
    if (macdChart) macdChart.timeScale().subscribeVisibleLogicalRangeChange(range => syncRange(range, 'macd'));
    if (rsiChart) rsiChart.timeScale().subscribeVisibleLogicalRangeChange(range => syncRange(range, 'rsi'));

    // Add candlestick series to main chart
    const candlestickSeries = mainChart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#ef4444',
      borderDownColor: '#ef4444',
      borderUpColor: '#10b981',
      wickDownColor: '#ef4444',
      wickUpColor: '#10b981',
    });

    // Bollinger Bands - only create if showBollinger
    let bbUpper: ISeriesApi<'Line'> | null = null;
    let bbMiddle: ISeriesApi<'Line'> | null = null;
    let bbLower: ISeriesApi<'Line'> | null = null;
    if (showBollinger) {
      bbUpper = mainChart.addSeries(LineSeries, {
        color: '#3b82f6',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      bbMiddle = mainChart.addSeries(LineSeries, {
        color: '#f97316',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      bbLower = mainChart.addSeries(LineSeries, {
        color: '#3b82f6',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }

    // Ichimoku Cloud - only create if showIchimoku
    let ichimokuTenkan: ISeriesApi<'Line'> | null = null;
    let ichimokuKijun: ISeriesApi<'Line'> | null = null;
    let ichimokuSenkouA: ISeriesApi<'Line'> | null = null;
    let ichimokuSenkouB: ISeriesApi<'Line'> | null = null;
    let ichimokuChikou: ISeriesApi<'Line'> | null = null;
    if (showIchimoku) {
      ichimokuTenkan = mainChart.addSeries(LineSeries, {
        color: '#2563eb',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      ichimokuKijun = mainChart.addSeries(LineSeries, {
        color: '#dc2626',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      ichimokuSenkouA = mainChart.addSeries(LineSeries, {
        color: '#10b981',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      ichimokuSenkouB = mainChart.addSeries(LineSeries, {
        color: '#f43f5e',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      ichimokuChikou = mainChart.addSeries(LineSeries, {
        color: '#8b5cf6',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }

    // Moving Averages - only create if showMovingAverages
    let maShort: ISeriesApi<'Line'> | null = null;
    let maMedium: ISeriesApi<'Line'> | null = null;
    let maLong: ISeriesApi<'Line'> | null = null;
    if (showMovingAverages) {
      maShort = mainChart.addSeries(LineSeries, {
        color: '#eab308',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      maMedium = mainChart.addSeries(LineSeries, {
        color: '#06b6d4',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      maLong = mainChart.addSeries(LineSeries, {
        color: '#d946ef',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }

    // MACD series
    let macdHistogram: ISeriesApi<'Histogram'> | null = null;
    let macdLine: ISeriesApi<'Line'> | null = null;
    let macdSignal: ISeriesApi<'Line'> | null = null;
    if (showMACD && macdChart) {
      macdHistogram = macdChart.addSeries(HistogramSeries, {
        priceLineVisible: false,
        lastValueVisible: false,
      });
      macdLine = macdChart.addSeries(LineSeries, {
        color: '#3b82f6',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      macdSignal = macdChart.addSeries(LineSeries, {
        color: '#f97316',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }

    // Stochastic RSI series
    let stochRsiK: ISeriesApi<'Line'> | null = null;
    let stochRsiD: ISeriesApi<'Line'> | null = null;
    let stochRsiOverbought: ISeriesApi<'Line'> | null = null;
    let stochRsiOversold: ISeriesApi<'Line'> | null = null;
    if (showRSI && rsiChart) {
      // %K line (fast)
      stochRsiK = rsiChart.addSeries(LineSeries, {
        color: '#8b5cf6',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      // %D line (signal/slow)
      stochRsiD = rsiChart.addSeries(LineSeries, {
        color: '#f97316',
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      // Overbought line (80 for Stoch RSI)
      stochRsiOverbought = rsiChart.addSeries(LineSeries, {
        color: '#ef4444',
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      // Oversold line (20 for Stoch RSI)
      stochRsiOversold = rsiChart.addSeries(LineSeries, {
        color: '#10b981',
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }

    // Sync crosshair between all charts
    let isSyncingCrosshair = false;
    const syncCrosshair = (time: Time | undefined, source: 'main' | 'macd' | 'rsi') => {
      if (isSyncingCrosshair) return;
      isSyncingCrosshair = true;
      if (time !== undefined) {
        if (source !== 'main') mainChart.setCrosshairPosition(0, time, candlestickSeries);
        if (source !== 'macd' && macdChart && macdHistogram) macdChart.setCrosshairPosition(0, time, macdHistogram);
        if (source !== 'rsi' && rsiChart && stochRsiK) rsiChart.setCrosshairPosition(0, time, stochRsiK);
      } else {
        if (source !== 'main') mainChart.clearCrosshairPosition();
        if (source !== 'macd' && macdChart) macdChart.clearCrosshairPosition();
        if (source !== 'rsi' && rsiChart) rsiChart.clearCrosshairPosition();
      }
      isSyncingCrosshair = false;
    };

    mainChart.subscribeCrosshairMove((param) => syncCrosshair(param.time, 'main'));
    if (macdChart) macdChart.subscribeCrosshairMove((param) => syncCrosshair(param.time, 'macd'));
    if (rsiChart) rsiChart.subscribeCrosshairMove((param) => syncCrosshair(param.time, 'rsi'));

    // Store refs
    mainChartRef.current = mainChart;
    macdChartRef.current = macdChart;
    rsiChartRef.current = rsiChart;
    candlestickSeriesRef.current = candlestickSeries;
    bbUpperRef.current = bbUpper;
    bbMiddleRef.current = bbMiddle;
    bbLowerRef.current = bbLower;
    ichimokuTenkanRef.current = ichimokuTenkan;
    ichimokuKijunRef.current = ichimokuKijun;
    ichimokuSenkouARef.current = ichimokuSenkouA;
    ichimokuSenkouBRef.current = ichimokuSenkouB;
    ichimokuChikouRef.current = ichimokuChikou;
    maShortRef.current = maShort;
    maMediumRef.current = maMedium;
    maLongRef.current = maLong;
    macdLineRef.current = macdLine;
    macdSignalRef.current = macdSignal;
    macdHistogramRef.current = macdHistogram;
    stochRsiKRef.current = stochRsiK;
    stochRsiDRef.current = stochRsiD;
    stochRsiOverboughtRef.current = stochRsiOverbought;
    stochRsiOversoldRef.current = stochRsiOversold;

    // Handle resize
    const handleResize = () => {
      if (mainChartContainerRef.current && mainChartRef.current) {
        mainChartRef.current.applyOptions({
          width: mainChartContainerRef.current.clientWidth,
          height: mainChartContainerRef.current.clientHeight,
        });
      }
      if (macdChartContainerRef.current && macdChartRef.current) {
        macdChartRef.current.applyOptions({
          width: macdChartContainerRef.current.clientWidth,
          height: macdChartContainerRef.current.clientHeight,
        });
      }
      if (rsiChartContainerRef.current && rsiChartRef.current) {
        rsiChartRef.current.applyOptions({
          width: rsiChartContainerRef.current.clientWidth,
          height: rsiChartContainerRef.current.clientHeight,
        });
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
      mainChart.remove();
      if (macdChart) macdChart.remove();
      if (rsiChart) rsiChart.remove();
    };
  }, [timeframe, showBollinger, showMACD, showIchimoku, showMovingAverages, showRSI]);

  // Resize charts when divider is moved
  useEffect(() => {
    requestAnimationFrame(() => {
      if (mainChartContainerRef.current && mainChartRef.current) {
        mainChartRef.current.applyOptions({
          width: mainChartContainerRef.current.clientWidth,
          height: mainChartContainerRef.current.clientHeight,
        });
      }
      if (macdChartContainerRef.current && macdChartRef.current) {
        macdChartRef.current.applyOptions({
          width: macdChartContainerRef.current.clientWidth,
          height: macdChartContainerRef.current.clientHeight,
        });
      }
      if (rsiChartContainerRef.current && rsiChartRef.current) {
        rsiChartRef.current.applyOptions({
          width: rsiChartContainerRef.current.clientWidth,
          height: rsiChartContainerRef.current.clientHeight,
        });
      }
    });
  }, [macdHeightPercent, rsiHeightPercent]);

  // Memoized chart data arrays - only recalculate when source data changes
  const chartDataArrays = useMemo(() => {
    if (data.length === 0 || chartTimes.length === 0) return null;

    const closes = data.map(d => d.close);

    // Candlestick data
    const candlestickData: CandlestickData<Time>[] = data.map((candle, i) => ({
      time: chartTimes[i],
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    }));

    // Bollinger Bands data
    let bbUpperData: LineData<Time>[] = [];
    let bbMiddleData: LineData<Time>[] = [];
    let bbLowerData: LineData<Time>[] = [];
    if (bollingerData) {
      for (let i = 0; i < data.length; i++) {
        if (bollingerData.upper[i] != null) {
          bbUpperData.push({ time: chartTimes[i], value: bollingerData.upper[i]! });
        }
        if (bollingerData.middle[i] != null) {
          bbMiddleData.push({ time: chartTimes[i], value: bollingerData.middle[i]! });
        }
        if (bollingerData.lower[i] != null) {
          bbLowerData.push({ time: chartTimes[i], value: bollingerData.lower[i]! });
        }
      }
    }

    // Ichimoku data
    // Note: Senkou spans are NOT displaced to future to avoid timeScale issues with lightweight-charts
    // Chikou span is NOT displaced to past for the same reason
    let ichimokuTenkanData: LineData<Time>[] = [];
    let ichimokuKijunData: LineData<Time>[] = [];
    let ichimokuSenkouAData: LineData<Time>[] = [];
    let ichimokuSenkouBData: LineData<Time>[] = [];
    let ichimokuChikouData: LineData<Time>[] = [];
    if (ichimokuData) {
      for (let i = 0; i < data.length; i++) {
        if (ichimokuData.tenkan[i] != null) {
          ichimokuTenkanData.push({ time: chartTimes[i], value: ichimokuData.tenkan[i]! });
        }
        if (ichimokuData.kijun[i] != null) {
          ichimokuKijunData.push({ time: chartTimes[i], value: ichimokuData.kijun[i]! });
        }
        // Senkou A & B displayed at current time (no future displacement)
        if (ichimokuData.senkouA[i] != null) {
          ichimokuSenkouAData.push({ time: chartTimes[i], value: ichimokuData.senkouA[i]! });
        }
        if (ichimokuData.senkouB[i] != null) {
          ichimokuSenkouBData.push({ time: chartTimes[i], value: ichimokuData.senkouB[i]! });
        }
        // Chikou displayed at current time (no past displacement)
        ichimokuChikouData.push({ time: chartTimes[i], value: closes[i] });
      }
    }

    // Moving Averages data
    let maShortData: LineData<Time>[] = [];
    let maMediumData: LineData<Time>[] = [];
    let maLongData: LineData<Time>[] = [];
    if (movingAveragesData) {
      for (let i = 0; i < data.length; i++) {
        if (movingAveragesData.short[i] != null) {
          maShortData.push({ time: chartTimes[i], value: movingAveragesData.short[i]! });
        }
        if (movingAveragesData.medium[i] != null) {
          maMediumData.push({ time: chartTimes[i], value: movingAveragesData.medium[i]! });
        }
        if (movingAveragesData.long[i] != null) {
          maLongData.push({ time: chartTimes[i], value: movingAveragesData.long[i]! });
        }
      }
    }

    // MACD data
    let macdLineData: (LineData<Time> | { time: Time })[] = [];
    let macdSignalData: (LineData<Time> | { time: Time })[] = [];
    let macdHistogramData: HistogramData<Time>[] = [];
    if (macdData) {
      for (let i = 0; i < data.length; i++) {
        if (macdData.macdLine[i] != null) {
          macdLineData.push({ time: chartTimes[i], value: macdData.macdLine[i]! });
        } else {
          macdLineData.push({ time: chartTimes[i] });
        }
        if (macdData.signal[i] != null) {
          macdSignalData.push({ time: chartTimes[i], value: macdData.signal[i]! });
        } else {
          macdSignalData.push({ time: chartTimes[i] });
        }
        if (macdData.histogram[i] != null) {
          const currentVal = macdData.histogram[i]!;
          const prevVal = i > 0 && macdData.histogram[i - 1] != null ? macdData.histogram[i - 1]! : 0;
          let color: string;
          if (currentVal >= 0) {
            color = currentVal >= prevVal ? '#10b981' : '#6ee7b7';
          } else {
            color = currentVal <= prevVal ? '#ef4444' : '#fca5a5';
          }
          macdHistogramData.push({ time: chartTimes[i], value: currentVal, color });
        } else {
          macdHistogramData.push({ time: chartTimes[i], value: 0, color: 'transparent' });
        }
      }
    }

    // Stochastic RSI data
    let stochRsiKData: (LineData<Time> | { time: Time })[] = [];
    let stochRsiDData: (LineData<Time> | { time: Time })[] = [];
    let stochRsiOverboughtData: LineData<Time>[] = [];
    let stochRsiOversoldData: LineData<Time>[] = [];
    if (stochRsiData) {
      for (let i = 0; i < data.length; i++) {
        // %K line
        if (stochRsiData.k[i] != null) {
          stochRsiKData.push({ time: chartTimes[i], value: stochRsiData.k[i]! });
        } else {
          stochRsiKData.push({ time: chartTimes[i] });
        }
        // %D line
        if (stochRsiData.d[i] != null) {
          stochRsiDData.push({ time: chartTimes[i], value: stochRsiData.d[i]! });
        } else {
          stochRsiDData.push({ time: chartTimes[i] });
        }
        // Overbought/Oversold at 80/20 for Stoch RSI
        stochRsiOverboughtData.push({ time: chartTimes[i], value: 80 });
        stochRsiOversoldData.push({ time: chartTimes[i], value: 20 });
      }
    }

    return {
      candlestickData,
      bbUpperData, bbMiddleData, bbLowerData,
      ichimokuTenkanData, ichimokuKijunData, ichimokuSenkouAData, ichimokuSenkouBData, ichimokuChikouData,
      maShortData, maMediumData, maLongData,
      macdLineData, macdSignalData, macdHistogramData,
      stochRsiKData, stochRsiDData, stochRsiOverboughtData, stochRsiOversoldData,
    };
  }, [data, chartTimes, bollingerData, ichimokuData, movingAveragesData, macdData, stochRsiData]);

  // Update data when it changes - now uses memoized arrays
  useEffect(() => {
    if (!candlestickSeriesRef.current || !chartDataArrays) return;

    // Set candlestick data
    candlestickSeriesRef.current.setData(chartDataArrays.candlestickData);

    // Set Bollinger data
    if (showBollinger && bollingerData) {
      bbUpperRef.current?.setData(chartDataArrays.bbUpperData);
      bbMiddleRef.current?.setData(chartDataArrays.bbMiddleData);
      bbLowerRef.current?.setData(chartDataArrays.bbLowerData);
    }

    // Set Bollinger buy signals as markers
    if (showBollingerSignals && candlestickSeriesRef.current) {
      // Create markers plugin if it doesn't exist
      if (!markersPluginRef.current) {
        markersPluginRef.current = createSeriesMarkers(candlestickSeriesRef.current, bollingerBuySignals);
      } else {
        markersPluginRef.current.setMarkers(bollingerBuySignals);
      }
    } else if (!showBollingerSignals && markersPluginRef.current) {
      markersPluginRef.current.setMarkers([]);
    }

    // Set Ichimoku data
    if (showIchimoku && ichimokuData) {
      ichimokuTenkanRef.current?.setData(chartDataArrays.ichimokuTenkanData);
      ichimokuKijunRef.current?.setData(chartDataArrays.ichimokuKijunData);
      ichimokuSenkouARef.current?.setData(chartDataArrays.ichimokuSenkouAData);
      ichimokuSenkouBRef.current?.setData(chartDataArrays.ichimokuSenkouBData);
      ichimokuChikouRef.current?.setData(chartDataArrays.ichimokuChikouData);
    }

    // Set Moving Averages data
    if (showMovingAverages && movingAveragesData) {
      maShortRef.current?.setData(chartDataArrays.maShortData);
      maMediumRef.current?.setData(chartDataArrays.maMediumData);
      maLongRef.current?.setData(chartDataArrays.maLongData);
    }

    // Set MACD data
    if (showMACD && macdData) {
      macdLineRef.current?.setData(chartDataArrays.macdLineData);
      macdSignalRef.current?.setData(chartDataArrays.macdSignalData);
      macdHistogramRef.current?.setData(chartDataArrays.macdHistogramData);
    }

    // Set Stochastic RSI data
    if (showRSI && stochRsiData) {
      stochRsiKRef.current?.setData(chartDataArrays.stochRsiKData);
      stochRsiDRef.current?.setData(chartDataArrays.stochRsiDData);
      stochRsiOverboughtRef.current?.setData(chartDataArrays.stochRsiOverboughtData);
      stochRsiOversoldRef.current?.setData(chartDataArrays.stochRsiOversoldData);
    }

    // Only set visible range on initial load
    if (isInitialLoadRef.current) {
      requestAnimationFrame(() => {
        if (mainChartRef.current) {
          const totalBars = data.length;
          if ((timeframe === '1day' || timeframe === '15min') && totalBars > 10) {
            const visibleRange = {
              from: Math.floor(totalBars / 2),
              to: totalBars + 5,
            };
            mainChartRef.current.timeScale().setVisibleLogicalRange(visibleRange);
            if (macdChartRef.current) {
              macdChartRef.current.timeScale().setVisibleLogicalRange(visibleRange);
            }
            if (rsiChartRef.current) {
              rsiChartRef.current.timeScale().setVisibleLogicalRange(visibleRange);
            }
          } else {
            mainChartRef.current.timeScale().fitContent();
            const range = mainChartRef.current.timeScale().getVisibleLogicalRange();
            if (range) {
              if (macdChartRef.current) {
                macdChartRef.current.timeScale().setVisibleLogicalRange(range);
              }
              if (rsiChartRef.current) {
                rsiChartRef.current.timeScale().setVisibleLogicalRange(range);
              }
            }
          }
          isInitialLoadRef.current = false;
        }
      });
    }

  }, [chartDataArrays, showBollinger, showBollingerSignals, bollingerBuySignals, showMACD, showIchimoku, showMovingAverages, showRSI, bollingerData, ichimokuData, movingAveragesData, macdData, stochRsiData, data.length, timeframe]);

  return (
    <div className="h-full w-full bg-[#0d0d0d] flex flex-col">
      {/* Compact Header */}
      <div className="flex items-center justify-between px-2 py-1 border-b border-[#1a1a1a]">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">{title}</span>
          {lastPrice !== null && (
            <span className="text-xs font-mono font-medium text-white">
              {lastPrice.toFixed(2)}
            </span>
          )}
          {priceChange !== null && (
            <span className={`text-[10px] font-mono ${priceChange >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
              {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}%
            </span>
          )}
          {showBollinger && <span className="text-[9px] text-gray-600 ml-2">BB(20,2)</span>}
          {showIchimoku && <span className="text-[9px] text-gray-600 ml-2">Ichimoku</span>}
          {showMovingAverages && <span className="text-[9px] text-gray-600 ml-2">SMA(20,50,200)</span>}
          {showMACD && <span className="text-[9px] text-gray-600">MACD(12,26,9)</span>}
          {showRSI && <span className="text-[9px] text-gray-600">Stoch RSI(14,14,3,3)</span>}
        </div>
      </div>

      {/* Charts Container */}
      <div ref={containerRef} className="flex-1 flex flex-col min-h-0">
        {/* Main Chart with Candlesticks and Overlays */}
        <div
          className="relative min-h-0 flex-1"
          style={{
            flexBasis: `${100 - (showMACD ? macdHeightPercent : 0) - (showRSI ? rsiHeightPercent : 0)}%`,
            minHeight: '30%'
          }}
        >
          {isLoading && data.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center bg-[#0d0d0d] z-10">
              <div className="text-[10px] text-gray-600 uppercase tracking-wider">Loading...</div>
            </div>
          )}
          <div ref={mainChartContainerRef} className="w-full h-full" />
        </div>

        {/* MACD Section */}
        {showMACD && (
          <>
            {/* MACD Divider */}
            <div
              className={`h-1 bg-[#1a1a1a] cursor-row-resize hover:bg-[#f97316] transition-colors flex items-center justify-center group ${draggingDivider === 'macd' ? 'bg-[#f97316]' : ''}`}
              onMouseDown={handleMouseDown('macd')}
            >
              <div className={`w-8 h-0.5 rounded bg-[#3a3a3a] group-hover:bg-white ${draggingDivider === 'macd' ? 'bg-white' : ''}`} />
            </div>
            {/* MACD Chart */}
            <div
              className="min-h-0"
              style={{ flexBasis: `${macdHeightPercent}%`, minHeight: '10%' }}
            >
              <div ref={macdChartContainerRef} className="w-full h-full" />
            </div>
          </>
        )}

        {/* RSI Section */}
        {showRSI && (
          <>
            {/* RSI Divider */}
            <div
              className={`h-1 bg-[#1a1a1a] cursor-row-resize hover:bg-[#8b5cf6] transition-colors flex items-center justify-center group ${draggingDivider === 'rsi' ? 'bg-[#8b5cf6]' : ''}`}
              onMouseDown={handleMouseDown('rsi')}
            >
              <div className={`w-8 h-0.5 rounded bg-[#3a3a3a] group-hover:bg-white ${draggingDivider === 'rsi' ? 'bg-white' : ''}`} />
            </div>
            {/* RSI Chart */}
            <div
              className="min-h-0"
              style={{ flexBasis: `${rsiHeightPercent}%`, minHeight: '10%' }}
            >
              <div ref={rsiChartContainerRef} className="w-full h-full" />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// Export memoized component to prevent unnecessary re-renders
export const MemoizedCandlestickChart = memo(CandlestickChart);
