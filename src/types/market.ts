export interface CandleData {
  time: number; // Unix timestamp
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface TwelveDataCandle {
  datetime: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume?: string;
}

export interface TwelveDataResponse {
  meta: {
    symbol: string;
    interval: string;
    currency: string;
    exchange_timezone: string;
    exchange: string;
    type: string;
  };
  values: TwelveDataCandle[];
  status: string;
}

export type TimeFrame = '15min' | '1h' | '1day';

export interface ChartConfig {
  timeframe: TimeFrame;
  title: string;
  outputSize: number;
}
