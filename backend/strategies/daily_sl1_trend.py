from typing import List, Dict, Any, Optional
from datetime import datetime
import pytz
from .base import BaseStrategy, Signal, StrategyDisplayConfig

PARIS_TZ = pytz.timezone('Europe/Paris')

SL_PERCENT = 1.0  # -1%
MA_TREND_PERIOD = 200
MA_SLOPE_LOOKBACK = 5


class DailySL1TrendStrategy(BaseStrategy):
    """
    Daily SL-1% + Trend Filter Strategy

    Entry:
    - First candle where price > MA200 AND MA200 rising
    - One trade per day max

    Exit (first condition met):
    - Stop Loss -1%
    - Price < MA200
    - MA200 falling
    - 22h Paris
    """

    @property
    def name(self) -> str:
        return "daily-sl1-trend"

    @property
    def display_config(self) -> StrategyDisplayConfig:
        return StrategyDisplayConfig(
            display_name="Multi-Daily SL-1% Trend MA200",
            description="Entry: when price > MA200 and MA200 rising (1x/day). Exit: SL -1%, price < MA200, MA200 falling, or 22h.",
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

    def _get_paris_date_string(self, timestamp: int) -> str:
        dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
        return dt.strftime('%Y-%m-%d')

    def _can_open_position_today(self, candles: List[Dict], index: int, position_open_on_day: dict) -> bool:
        """Check if we can open a position today (no position yet opened today)"""
        date_string = self._get_paris_date_string(candles[index]['time'])
        return date_string not in position_open_on_day

    def _is_closing_hour(self, timestamp: int) -> bool:
        return self._get_paris_hour(timestamp) == 22

    def _is_last_candle_of_day(self, candles: List[Dict], index: int) -> bool:
        if index >= len(candles) - 1:
            return True
        current_date = self._get_paris_date_string(candles[index]['time'])
        next_date = self._get_paris_date_string(candles[index + 1]['time'])
        return current_date != next_date

    def _check_stop_loss(self, candle: Dict, buy_price: float) -> bool:
        sl_price = buy_price * (1 - SL_PERCENT / 100)
        return candle['low'] < sl_price

    def _check_trend_bullish(self, closes: List[float], ma200: List[Optional[float]], index: int) -> bool:
        """Check if trend is bullish: price > MA200 AND MA200 rising"""
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

    def _check_trend_exit(self, closes: List[float], ma200: List[Optional[float]], index: int) -> tuple[bool, str]:
        """Check if trend exit conditions are met: price < MA200 OR MA200 falling"""
        if index < MA_SLOPE_LOOKBACK:
            return False, ''

        current_ma = ma200[index]
        past_ma = ma200[index - MA_SLOPE_LOOKBACK]
        current_price = closes[index]

        if current_ma is None or past_ma is None:
            return False, ''

        # Exit if price below MA200
        if current_price < current_ma:
            return True, 'price_below_ma200'

        # Exit if MA200 is falling
        if current_ma < past_ma:
            return True, 'ma200_falling'

        return False, ''

    def calculate_signals(
        self,
        candles: List[Dict],
        initial_state: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Signal], Dict[str, Any]]:
        if len(candles) < self.required_lookback:
            return [], initial_state or {}

        if initial_state:
            position_open_on_day = initial_state.get('position_open_on_day', {})
        else:
            position_open_on_day = {}

        closes = [c['close'] for c in candles]
        ma200 = self._calculate_sma(closes, MA_TREND_PERIOD)

        signals: List[Signal] = []
        start_index = MA_TREND_PERIOD + MA_SLOPE_LOOKBACK

        for i in range(start_index, len(candles)):
            candle = candles[i]
            date_string = self._get_paris_date_string(candle['time'])

            # Check for buy signal: first candle that meets conditions (max 1 per day)
            if self._can_open_position_today(candles, i, position_open_on_day):
                if self._check_trend_bullish(closes, ma200, i):
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='buy',
                        price=candle['open'],
                        label='Buy',
                        metadata={'ma200': ma200[i], 'trend_filter': 'passed'}
                    ))
                    position_open_on_day[date_string] = {
                        'buy_price': candle['open'],
                        'buy_time': candle['time'],
                    }

            # Check if we have an open position today
            if date_string in position_open_on_day:
                position = position_open_on_day[date_string]
                buy_price = position['buy_price']

                # Check for Stop Loss trigger (-1%)
                if self._check_stop_loss(candle, buy_price):
                    sl_price = buy_price * (1 - SL_PERCENT / 100)
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='sell',
                        price=sl_price,
                        label='SL',
                        metadata={
                            'buy_price': buy_price,
                            'buy_time': position['buy_time'],
                            'exit_reason': 'stop_loss',
                        }
                    ))
                    del position_open_on_day[date_string]
                    continue

                # Check for trend exit (price < MA200 OR MA200 falling)
                trend_exit, exit_reason = self._check_trend_exit(closes, ma200, i)
                if trend_exit:
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='sell',
                        price=candle['close'],
                        label='Trend',
                        metadata={
                            'buy_price': buy_price,
                            'buy_time': position['buy_time'],
                            'exit_reason': exit_reason,
                            'ma200': ma200[i],
                        }
                    ))
                    del position_open_on_day[date_string]
                    continue

                # Check for closing hour (22h) or last candle of day
                if self._is_closing_hour(candle['time']) or self._is_last_candle_of_day(candles, i):
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='sell',
                        price=candle['close'],
                        label='Close',
                        metadata={
                            'buy_price': buy_price,
                            'buy_time': position['buy_time'],
                            'exit_reason': 'end_of_day',
                        }
                    ))
                    del position_open_on_day[date_string]

        final_state = {
            'position_open_on_day': position_open_on_day,
        }

        return signals, final_state
