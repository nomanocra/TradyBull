from typing import List, Dict, Any, Optional
from datetime import datetime
import pytz
from .base import BaseStrategy, Signal, StrategyDisplayConfig
from market_hours import is_last_candle_of_day

PARIS_TZ = pytz.timezone('Europe/Paris')

MA_TREND_PERIOD = 200
MA_SLOPE_LOOKBACK = 5


class Trend22hStrategy(BaseStrategy):
    """
    Trend Following Strategy - 22h Entry Only

    Rules:
    - Buy at 22h Paris time when trend is bullish: price > MA200 AND MA200 is rising
    - Sell when trend becomes bearish: price < MA200 OR MA200 is falling
    - Hold position while trend remains bullish (no daily close)
    - No stop loss
    """

    @property
    def name(self) -> str:
        return "trend-22h"

    @property
    def display_config(self) -> StrategyDisplayConfig:
        return StrategyDisplayConfig(
            display_name="Trend200 22h",
            description="BUY: at 22h Paris AND price > MA200 AND MA200 rising. SELL: price < MA200 OR MA200 falling. Hold while bullish. No stop loss.",
            show_moving_averages=True,
        )

    @property
    def required_lookback(self) -> int:
        return MA_TREND_PERIOD + MA_SLOPE_LOOKBACK + 1

    def _calculate_sma(self, data: List[float], period: int) -> List[Optional[float]]:
        result: List[Optional[float]] = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(None)
            else:
                window = data[i - period + 1:i + 1]
                result.append(sum(window) / period)
        return result

    def _get_paris_hour(self, timestamp: int) -> int:
        dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
        return dt.hour

    def _check_trend_bullish(self, closes: List[float], ma200: List[Optional[float]], index: int) -> bool:
        """
        Check if trend is bullish:
        - Price > MA200
        - MA200 is rising (current > 5 candles ago)
        """
        if index < MA_SLOPE_LOOKBACK:
            return False

        current_ma = ma200[index]
        past_ma = ma200[index - MA_SLOPE_LOOKBACK]
        current_price = closes[index]

        if current_ma is None or past_ma is None:
            return False

        price_above_ma = current_price > current_ma
        ma_rising = current_ma > past_ma

        return price_above_ma and ma_rising

    def calculate_signals(
        self,
        candles: List[Dict],
        initial_state: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Signal], Dict[str, Any]]:
        if len(candles) < self.required_lookback:
            return [], initial_state or {}

        # Initialize or restore state
        if initial_state:
            position = initial_state.get('position', None)
            previous_trend_bullish = initial_state.get('previous_trend_bullish', False)
        else:
            position = None
            previous_trend_bullish = False

        closes = [c['close'] for c in candles]
        ma200 = self._calculate_sma(closes, MA_TREND_PERIOD)

        signals: List[Signal] = []
        start_index = MA_TREND_PERIOD + MA_SLOPE_LOOKBACK

        for i in range(start_index, len(candles) - 1):  # -1 to ensure next candle exists
            candle = candles[i]
            next_candle = candles[i + 1]
            current_trend_bullish = self._check_trend_bullish(closes, ma200, i)

            # Trend is bullish AND it's 22h - BUY
            # Condition checked on candle[i] close, entry on candle[i+1] open
            hour = self._get_paris_hour(candle['time'])
            is_entry_hour = hour == 22

            if current_trend_bullish and is_entry_hour and position is None:
                signals.append(Signal(
                    signal_timestamp=next_candle['time'],
                    trigger_timestamp=candle['time'],
                    type='buy',
                    price=next_candle['open'],
                    label='Buy',
                    metadata={
                        'ma200': ma200[i],
                        'reason': 'trend_bullish_at_22h',
                    }
                ))
                position = {
                    'buy_price': next_candle['open'],
                    'buy_time': next_candle['time'],
                }

            # Trend just turned bearish - SELL
            # Condition checked on candle[i] close, exit on candle[i+1] open
            elif not current_trend_bullish and previous_trend_bullish and position is not None:
                signals.append(Signal(
                    signal_timestamp=next_candle['time'],
                    trigger_timestamp=candle['time'],
                    type='sell',
                    price=next_candle['open'],
                    label='Sell',
                    metadata={
                        'buy_price': position['buy_price'],
                        'buy_time': position['buy_time'],
                        'ma200': ma200[i],
                        'reason': 'trend_turned_bearish',
                    }
                ))
                position = None

            previous_trend_bullish = current_trend_bullish

        final_state = {
            'position': position,
            'previous_trend_bullish': previous_trend_bullish,
        }

        return signals, final_state
