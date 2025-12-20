from typing import List, Dict, Any, Optional
from .base import BaseStrategy, Signal, StrategyDisplayConfig

# Ichimoku parameters (standard)
TENKAN_PERIOD = 9
KIJUN_PERIOD = 26
SENKOU_B_PERIOD = 52
DISPLACEMENT = 26


class IchimokuTKCrossStrategy(BaseStrategy):
    """
    Ichimoku TK Cross Strategy

    Entry:
    - Buy when Tenkan crosses above Kijun (bullish cross)
    - AND price is above the cloud (confirmation)

    Exit:
    - Sell when Tenkan crosses below Kijun (bearish cross)
    - OR price enters/below cloud
    - No stop loss
    """

    @property
    def name(self) -> str:
        return "ichimoku-tk-cross"

    @property
    def display_config(self) -> StrategyDisplayConfig:
        return StrategyDisplayConfig(
            display_name="Ichimoku TK Cross",
            description="BUY: Tenkan crosses above Kijun + price above cloud. SELL: Tenkan crosses below Kijun or price in cloud.",
            show_ichimoku=True,
        )

    @property
    def required_lookback(self) -> int:
        return SENKOU_B_PERIOD + DISPLACEMENT + 1

    def _calc_high_low_avg(self, candles: List[Dict], index: int, period: int) -> Optional[float]:
        """Calculate (highest high + lowest low) / 2 for a period"""
        if index < period - 1:
            return None

        highs = [candles[i]['high'] for i in range(index - period + 1, index + 1)]
        lows = [candles[i]['low'] for i in range(index - period + 1, index + 1)]

        return (max(highs) + min(lows)) / 2

    def _calculate_ichimoku(self, candles: List[Dict]) -> tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        """Calculate Ichimoku components"""
        n = len(candles)

        tenkan = [None] * n
        kijun = [None] * n
        senkou_a = [None] * n
        senkou_b = [None] * n

        for i in range(n):
            tenkan[i] = self._calc_high_low_avg(candles, i, TENKAN_PERIOD)
            kijun[i] = self._calc_high_low_avg(candles, i, KIJUN_PERIOD)
            senkou_b[i] = self._calc_high_low_avg(candles, i, SENKOU_B_PERIOD)

            if tenkan[i] is not None and kijun[i] is not None:
                senkou_a[i] = (tenkan[i] + kijun[i]) / 2

        return tenkan, kijun, senkou_a, senkou_b

    def _is_above_cloud(self, price: float, senkou_a: Optional[float], senkou_b: Optional[float]) -> bool:
        """Check if price is above the cloud"""
        if senkou_a is None or senkou_b is None:
            return False

        cloud_top = max(senkou_a, senkou_b)
        return price > cloud_top

    def _is_in_or_below_cloud(self, price: float, senkou_a: Optional[float], senkou_b: Optional[float]) -> bool:
        """Check if price is inside or below the cloud"""
        if senkou_a is None or senkou_b is None:
            return False

        cloud_top = max(senkou_a, senkou_b)
        return price <= cloud_top

    def _is_tk_bullish_cross(self, tenkan: List[Optional[float]], kijun: List[Optional[float]], index: int) -> bool:
        """Check if Tenkan crosses above Kijun (bullish cross)"""
        if index < 1:
            return False

        curr_tenkan = tenkan[index]
        curr_kijun = kijun[index]
        prev_tenkan = tenkan[index - 1]
        prev_kijun = kijun[index - 1]

        if None in (curr_tenkan, curr_kijun, prev_tenkan, prev_kijun):
            return False

        # Bullish cross: Tenkan was below/equal Kijun, now above
        return prev_tenkan <= prev_kijun and curr_tenkan > curr_kijun

    def _is_tk_bearish_cross(self, tenkan: List[Optional[float]], kijun: List[Optional[float]], index: int) -> bool:
        """Check if Tenkan crosses below Kijun (bearish cross)"""
        if index < 1:
            return False

        curr_tenkan = tenkan[index]
        curr_kijun = kijun[index]
        prev_tenkan = tenkan[index - 1]
        prev_kijun = kijun[index - 1]

        if None in (curr_tenkan, curr_kijun, prev_tenkan, prev_kijun):
            return False

        # Bearish cross: Tenkan was above/equal Kijun, now below
        return prev_tenkan >= prev_kijun and curr_tenkan < curr_kijun

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

        # Calculate Ichimoku components
        tenkan, kijun, senkou_a, senkou_b = self._calculate_ichimoku(candles)

        signals: List[Signal] = []
        start_index = self.required_lookback

        for i in range(start_index, len(candles)):
            candle = candles[i]
            close = candle['close']

            # Use cloud values from DISPLACEMENT periods ago
            cloud_index = i - DISPLACEMENT
            if cloud_index < 0:
                continue

            span_a = senkou_a[cloud_index]
            span_b = senkou_b[cloud_index]

            # Check for buy signal: TK bullish cross + price above cloud
            if position is None:
                if self._is_tk_bullish_cross(tenkan, kijun, i) and self._is_above_cloud(close, span_a, span_b):
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='buy',
                        price=candle['close'],
                        label='Buy',
                        metadata={
                            'tenkan': tenkan[i],
                            'kijun': kijun[i],
                            'senkou_a': span_a,
                            'senkou_b': span_b,
                            'signal_type': 'tk_bullish_cross',
                        }
                    ))
                    position = {
                        'buy_price': candle['close'],
                        'buy_time': candle['time'],
                    }

            # Check for exit conditions
            elif position is not None:
                # Exit on TK bearish cross
                if self._is_tk_bearish_cross(tenkan, kijun, i):
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='sell',
                        price=candle['close'],
                        label='TK',
                        metadata={
                            'buy_price': position['buy_price'],
                            'buy_time': position['buy_time'],
                            'exit_reason': 'tk_bearish_cross',
                            'tenkan': tenkan[i],
                            'kijun': kijun[i],
                        }
                    ))
                    position = None
                    continue

                # Exit on price in/below cloud
                if self._is_in_or_below_cloud(close, span_a, span_b):
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='sell',
                        price=candle['close'],
                        label='Cloud',
                        metadata={
                            'buy_price': position['buy_price'],
                            'buy_time': position['buy_time'],
                            'exit_reason': 'price_in_cloud',
                        }
                    ))
                    position = None

        final_state = {
            'position': position,
        }

        return signals, final_state
