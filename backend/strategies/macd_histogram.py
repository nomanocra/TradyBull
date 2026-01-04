from typing import List, Dict, Any, Optional
from .base import BaseStrategy, Signal, StrategyDisplayConfig

# MACD parameters (standard)
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9


class MACDHistogramStrategy(BaseStrategy):
    """
    MACD Histogram Reversal Strategy

    Entry:
    - Buy when histogram is negative AND starts rising (red bars turning pink)
    - This anticipates the MACD/Signal bullish crossover

    Exit:
    - Sell when histogram is positive AND starts falling (green bars turning light)
    - This anticipates the MACD/Signal bearish crossover
    - No stop loss
    """

    @property
    def name(self) -> str:
        return "macd-histogram"

    @property
    def display_config(self) -> StrategyDisplayConfig:
        return StrategyDisplayConfig(
            display_name="MACD Histogram",
            description="BUY: histogram negative + rising (red→pink). SELL: histogram positive + falling (green→light).",
            show_macd=True,
        )

    @property
    def required_lookback(self) -> int:
        return MACD_SLOW + MACD_SIGNAL + 2  # +2 for histogram comparison

    def _calculate_ema(self, values: List[float], period: int) -> List[Optional[float]]:
        """Calculate Exponential Moving Average"""
        n = len(values)
        ema = [None] * n

        if n < period:
            return ema

        # Initial SMA for first EMA value
        sma = sum(values[:period]) / period
        ema[period - 1] = sma

        # EMA multiplier
        multiplier = 2 / (period + 1)

        # Calculate EMA for remaining values
        for i in range(period, n):
            ema[i] = (values[i] - ema[i - 1]) * multiplier + ema[i - 1]

        return ema

    def _calculate_macd(self, candles: List[Dict]) -> tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        """Calculate MACD, Signal, and Histogram"""
        closes = [c['close'] for c in candles]
        n = len(closes)

        # Calculate EMAs
        ema_fast = self._calculate_ema(closes, MACD_FAST)
        ema_slow = self._calculate_ema(closes, MACD_SLOW)

        # Calculate MACD line
        macd_line = [None] * n
        for i in range(n):
            if ema_fast[i] is not None and ema_slow[i] is not None:
                macd_line[i] = ema_fast[i] - ema_slow[i]

        # Calculate Signal line (EMA of MACD)
        macd_values = [v if v is not None else 0 for v in macd_line]
        start_idx = MACD_SLOW - 1
        signal_line = [None] * n

        if n > start_idx + MACD_SIGNAL:
            # Initial SMA for signal line
            macd_subset = macd_values[start_idx:start_idx + MACD_SIGNAL]
            sma = sum(macd_subset) / MACD_SIGNAL
            signal_idx = start_idx + MACD_SIGNAL - 1
            signal_line[signal_idx] = sma

            multiplier = 2 / (MACD_SIGNAL + 1)
            for i in range(signal_idx + 1, n):
                if macd_line[i] is not None:
                    signal_line[i] = (macd_line[i] - signal_line[i - 1]) * multiplier + signal_line[i - 1]

        # Calculate Histogram
        histogram = [None] * n
        for i in range(n):
            if macd_line[i] is not None and signal_line[i] is not None:
                histogram[i] = macd_line[i] - signal_line[i]

        return macd_line, signal_line, histogram

    def _is_histogram_turning_up(self, histogram: List[Optional[float]], index: int) -> bool:
        """Check if histogram is negative and starting to rise (red turning pink)"""
        if index < 1:
            return False

        curr_hist = histogram[index]
        prev_hist = histogram[index - 1]

        if curr_hist is None or prev_hist is None:
            return False

        # Histogram is negative AND rising (current > previous)
        return curr_hist < 0 and curr_hist > prev_hist

    def _is_histogram_turning_down(self, histogram: List[Optional[float]], index: int) -> bool:
        """Check if histogram is positive and starting to fall (green turning light)"""
        if index < 1:
            return False

        curr_hist = histogram[index]
        prev_hist = histogram[index - 1]

        if curr_hist is None or prev_hist is None:
            return False

        # Histogram is positive AND falling (current < previous)
        return curr_hist > 0 and curr_hist < prev_hist

    def calculate_signals(
        self,
        candles: List[Dict],
        initial_state: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Signal], Dict[str, Any]]:
        if len(candles) < self.required_lookback:
            return [], initial_state or {}

        # Restore state
        if initial_state:
            position = initial_state.get('position', None)
        else:
            position = None

        # Calculate MACD components
        macd_line, signal_line, histogram = self._calculate_macd(candles)

        signals: List[Signal] = []
        start_index = self.required_lookback

        for i in range(start_index, len(candles) - 1):  # -1 to ensure next candle exists
            candle = candles[i]
            next_candle = candles[i + 1]

            # Check for buy signal: histogram negative and turning up
            # Condition checked on candle[i] close, entry on candle[i+1] open
            if position is None:
                if self._is_histogram_turning_up(histogram, i):
                    signals.append(Signal(
                        signal_timestamp=next_candle['time'],
                        trigger_timestamp=candle['time'],
                        type='buy',
                        price=next_candle['open'],
                        label='Buy',
                        metadata={
                            'macd': macd_line[i],
                            'signal': signal_line[i],
                            'histogram': histogram[i],
                            'prev_histogram': histogram[i - 1],
                            'signal_type': 'histogram_turning_up',
                        }
                    ))
                    position = {
                        'buy_price': next_candle['open'],
                        'buy_time': next_candle['time'],
                    }

            # Check for sell signal: histogram positive and turning down
            # Condition checked on candle[i] close, exit on candle[i+1] open
            elif position is not None:
                if self._is_histogram_turning_down(histogram, i):
                    signals.append(Signal(
                        signal_timestamp=next_candle['time'],
                        trigger_timestamp=candle['time'],
                        type='sell',
                        price=next_candle['open'],
                        label='Hist',
                        metadata={
                            'buy_price': position['buy_price'],
                            'buy_time': position['buy_time'],
                            'exit_reason': 'histogram_turning_down',
                            'macd': macd_line[i],
                            'signal': signal_line[i],
                            'histogram': histogram[i],
                            'prev_histogram': histogram[i - 1],
                        }
                    ))
                    position = None

        final_state = {
            'position': position,
        }

        return signals, final_state
