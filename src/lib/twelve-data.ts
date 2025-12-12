import { TwelveDataResponse, CandleData, TimeFrame } from '@/types/market';

const TWELVE_DATA_BASE_URL = 'https://api.twelvedata.com';

export async function fetchCandleData(
  symbol: string,
  interval: TimeFrame,
  outputSize: number
): Promise<CandleData[]> {
  const apiKey = process.env.TWELVE_DATA_API_KEY;

  if (!apiKey) {
    throw new Error('TWELVE_DATA_API_KEY is not configured');
  }

  const url = new URL(`${TWELVE_DATA_BASE_URL}/time_series`);
  url.searchParams.set('symbol', symbol);
  url.searchParams.set('interval', interval);
  url.searchParams.set('outputsize', outputSize.toString());
  url.searchParams.set('timezone', 'Europe/Paris');
  url.searchParams.set('apikey', apiKey);

  const response = await fetch(url.toString(), {
    next: { revalidate: 60 }, // Cache for 60 seconds
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch data: ${response.statusText}`);
  }

  const data = await response.json();

  if (data.status === 'error' || data.code) {
    console.error('Twelve Data API error:', data);
    throw new Error(data.message || 'API returned an error');
  }

  // Convert Twelve Data format to lightweight-charts format
  // Twelve Data returns newest first, we need oldest first
  // Data is already in Europe/Paris timezone
  return data.values
    .map((candle: { datetime: string; open: string; high: string; low: string; close: string; volume?: string }) => ({
      time: Math.floor(new Date(candle.datetime.replace(' ', 'T')).getTime() / 1000),
      open: parseFloat(candle.open),
      high: parseFloat(candle.high),
      low: parseFloat(candle.low),
      close: parseFloat(candle.close),
      volume: candle.volume ? parseFloat(candle.volume) : undefined,
    }))
    .reverse();
}

// Calculate output size based on timeframe
export function getOutputSize(timeframe: TimeFrame): number {
  switch (timeframe) {
    case '15min':
      // 2 days * 24 hours * 4 (15min intervals per hour) = 192
      // Futures trade ~23h/day so roughly 184 candles for 2 days
      return 200;
    case '1h':
      // 7 days * 24 hours = 168 candles
      return 170;
    case '1day':
      // 30 trading days
      return 30;
    default:
      return 100;
  }
}
