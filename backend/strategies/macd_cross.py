from typing import List, Dict, Any, Optional
from .base import BaseStrategy, Signal, StrategyDisplayConfig

# MACD parameters (standard)
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9


class MACDCrossStrategy(BaseStrategy):
    """
    MACD Cross Strategy

    Entry:
    - Buy when MACD line crosses above Signal line (bullish crossover)

    Exit:
    - Sell when MACD line crosses below Signal line (bearish crossover)
    - No stop loss
    """

    @property
    def name(self) -> str:
        return "macd-cross"

    @property
    def display_config(self) -> StrategyDisplayConfig:
        return StrategyDisplayConfig(
            display_name="MACD Cross",
            description="BUY: MACD crosses above Signal. SELL: MACD crosses below Signal.",
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

    def _is_bullish_cross(self, macd: List[Optional[float]], signal: List[Optional[float]], index: int) -> bool:
        """Check if MACD crosses above Signal (bullish)"""
        if index < 1:
            return False

        curr_macd = macd[index]
        curr_signal = signal[index]
        prev_macd = macd[index - 1]
        prev_signal = signal[index - 1]

        if None in (curr_macd, curr_signal, prev_macd, prev_signal):
            return False

        # Bullish cross: MACD was below/equal Signal, now above
        return prev_macd <= prev_signal and curr_macd > curr_signal

    def _is_bearish_cross(self, macd: List[Optional[float]], signal: List[Optional[float]], index: int) -> bool:
        """Check if MACD crosses below Signal (bearish)"""
        if index < 1:
            return False

        curr_macd = macd[index]
        curr_signal = signal[index]
        prev_macd = macd[index - 1]
        prev_signal = signal[index - 1]

        if None in (curr_macd, curr_signal, prev_macd, prev_signal):
            return False

        # Bearish cross: MACD was above/equal Signal, now below
        return prev_macd >= prev_signal and curr_macd < curr_signal

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

        for i in range(start_index, len(candles)):
            candle = candles[i]

            # Check for buy signal: MACD bullish cross
            if position is None:
                if self._is_bullish_cross(macd_line, signal_line, i):
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='buy',
                        price=candle['close'],
                        label='Buy',
                        metadata={
                            'macd': macd_line[i],
                            'signal': signal_line[i],
                            'histogram': histogram[i],
                            'signal_type': 'macd_bullish_cross',
                        }
                    ))
                    position = {
                        'buy_price': candle['close'],
                        'buy_time': candle['time'],
                    }

            # Check for exit: MACD bearish cross
            elif position is not None:
                if self._is_bearish_cross(macd_line, signal_line, i):
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='sell',
                        price=candle['close'],
                        label='MACD',
                        metadata={
                            'buy_price': position['buy_price'],
                            'buy_time': position['buy_time'],
                            'exit_reason': 'macd_bearish_cross',
                            'macd': macd_line[i],
                            'signal': signal_line[i],
                        }
                    ))
                    position = None

        final_state = {
            'position': position,
        }

        return signals, final_state
