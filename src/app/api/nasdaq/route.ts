import { NextRequest, NextResponse } from 'next/server';
import { fetchCandleData, getOutputSize } from '@/lib/twelve-data';
import { TimeFrame } from '@/types/market';

const SYMBOL = 'QQQ'; // Nasdaq 100 ETF (futures NQ1! require paid plan)

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const interval = searchParams.get('interval') as TimeFrame;

  if (!interval || !['15min', '1h', '1day'].includes(interval)) {
    return NextResponse.json(
      { error: 'Invalid interval. Use 15min, 1h, or 1day' },
      { status: 400 }
    );
  }

  try {
    const outputSize = getOutputSize(interval);
    const data = await fetchCandleData(SYMBOL, interval, outputSize);

    return NextResponse.json({
      symbol: SYMBOL,
      interval,
      data,
    });
  } catch (error) {
    console.error('Error fetching Nasdaq data:', error);
    return NextResponse.json(
      { error: 'Failed to fetch market data' },
      { status: 500 }
    );
  }
}
