import { CandleData, Signal } from '@/types/market';

// Bollinger Bands settings (same as candlestick-chart.tsx)
const BB_PERIOD = 20;
const BB_STD_DEV = 2;

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
export function calculateBollingerBands(closes: number[]) {
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

// Get hour in Paris timezone from Unix timestamp
function getParisHour(timestamp: number): number {
  const date = new Date(timestamp * 1000);
  const parisTime = new Date(date.toLocaleString('en-US', { timeZone: 'Europe/Paris' }));
  return parisTime.getHours();
}

/**
 * Bollinger NoSL Strategy
 *
 * Rules:
 * - Buy signal when candle LOW goes below Bollinger lower band
 * - Signal is placed on the NEXT candle (buy at open of next candle)
 * - Only between 7h and 21h (Paris time)
 * - No stop loss (NoSL)
 *
 * @param data Array of candle data (must be 1H timeframe)
 * @returns Array of buy signals
 */
export function calculateBollingerNoSLSignals(data: CandleData[]): Signal[] {
  if (data.length < BB_PERIOD + 1) return [];

  const closes = data.map(d => d.close);
  const { lower } = calculateBollingerBands(closes);

  const signals: Signal[] = [];
  let lastSignalTriggered = false; // Track if we're waiting for price to go back above band

  for (let i = BB_PERIOD; i < data.length - 1; i++) {
    const candle = data[i];
    const lowerBand = lower[i];

    if (lowerBand === null) continue;

    const hour = getParisHour(candle.time);
    const isInTradingHours = hour >= 7 && hour <= 21;

    // Check if LOW went below lower Bollinger band
    const lowBelowBand = candle.low < lowerBand;

    if (lowBelowBand && isInTradingHours && !lastSignalTriggered) {
      // Signal on NEXT candle
      const nextCandle = data[i + 1];
      const nextHour = getParisHour(nextCandle.time);

      // Determine if this is the first signal of the day (after 7h)
      const isFirstSignalOfDay = nextHour >= 7 && nextHour <= 8;

      signals.push({
        time: nextCandle.time,
        type: 'buy',
        price: nextCandle.open,
        label: isFirstSignalOfDay ? 'Buy' : undefined,
      });

      lastSignalTriggered = true;
    }

    // Reset trigger when price goes back above the band
    if (candle.low > lowerBand) {
      lastSignalTriggered = false;
    }
  }

  return signals;
}
