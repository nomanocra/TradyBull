export interface CandleData {
  time: number; // Unix timestamp
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export type TimeFrame = '15min' | '1h' | '1day';

export interface Signal {
  time: number;           // Unix timestamp of the candle where signal appears
  type: 'buy' | 'sell';
  price: number;          // Suggested entry price
  label?: string;         // Optional label (e.g., "Buy", "Sell")
}
