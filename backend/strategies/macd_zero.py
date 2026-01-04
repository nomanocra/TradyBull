from typing import List, Dict, Any, Optional
from .base import BaseStrategy, Signal, StrategyDisplayConfig

# MACD parameters (standard)
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9


class MACDZeroStrategy(BaseStrategy):
    """
    MACD Zero Line Strategy

    Entry:
    - Buy when MACD line crosses above zero (momentum shift to bullish)

    Exit:
    - Sell when MACD line crosses below zero (momentum shift to bearish)
    - No stop loss

    More conservative than MACD Cross - fewer signals but higher conviction.
    """

    @property
    def name(self) -> str:
        return "macd-zero"

    @property
    def display_config(self) -> StrategyDisplayConfig:
        return StrategyDisplayConfig(
            display_name="MACD Zero",
            description="BUY: MACD crosses above 0. SELL: MACD crosses below 0. More conservative.",
            show_macd=True,
        )

    @property
    def required_lookback(self) -> int:
        return MACD_SLOW + MACD_SIGNAL + 1

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

    def _crosses_above_zero(self, macd: List[Optional[float]], index: int) -> bool:
        """Check if MACD crosses above zero"""
        if index < 1:
            return False

        curr_macd = macd[index]
        prev_macd = macd[index - 1]

        if curr_macd is None or prev_macd is None:
            return False

        # Cross above zero: was below/equal 0, now above
        return prev_macd <= 0 and curr_macd > 0

    def _crosses_below_zero(self, macd: List[Optional[float]], index: int) -> bool:
        """Check if MACD crosses below zero"""
        if index < 1:
            return False

        curr_macd = macd[index]
        prev_macd = macd[index - 1]

        if curr_macd is None or prev_macd is None:
            return False

        # Cross below zero: was above/equal 0, now below
        return prev_macd >= 0 and curr_macd < 0

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

            # Check for buy signal: MACD crosses above zero
            # Condition checked on candle[i] close, entry on candle[i+1] open
            if position is None:
                if self._crosses_above_zero(macd_line, i):
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
                            'signal_type': 'macd_above_zero',
                        }
                    ))
                    position = {
                        'buy_price': next_candle['open'],
                        'buy_time': next_candle['time'],
                    }

            # Check for exit: MACD crosses below zero
            # Condition checked on candle[i] close, exit on candle[i+1] open
            elif position is not None:
                if self._crosses_below_zero(macd_line, i):
                    signals.append(Signal(
                        signal_timestamp=next_candle['time'],
                        trigger_timestamp=candle['time'],
                        type='sell',
                        price=next_candle['open'],
                        label='Zero',
                        metadata={
                            'buy_price': position['buy_price'],
                            'buy_time': position['buy_time'],
                            'exit_reason': 'macd_below_zero',
                            'macd': macd_line[i],
                            'signal': signal_line[i],
                        }
                    ))
                    position = None

        final_state = {
            'position': position,
        }

        return signals, final_state
