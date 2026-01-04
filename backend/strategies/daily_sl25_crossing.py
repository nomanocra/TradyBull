from typing import List, Dict, Any, Optional
from datetime import datetime
import pytz
from .base import BaseStrategy, Signal, StrategyDisplayConfig
from market_hours import is_last_candle_of_day

PARIS_TZ = pytz.timezone('Europe/Paris')

SL_PERCENT = 2.5  # -2.5%
MA_SHORT = 50
MA_LONG = 200


class DailySL25CrossingStrategy(BaseStrategy):
    """
    Daily SL-2.5% + Golden Cross Filter Strategy

    Entry:
    - First candle of the day, only if MA50 > MA200
    - One trade per day max

    Exit (first condition met):
    - Stop Loss -2.5%
    - 22h Paris
    """

    @property
    def name(self) -> str:
        return "daily-sl25-crossing"

    @property
    def display_config(self) -> StrategyDisplayConfig:
        return StrategyDisplayConfig(
            display_name="Multi-Daily SL-2.5% Crossing IntraD",
            description="Entry: first candle if MA50 > MA200. Exit: SL -2.5% or 22h.",
            show_moving_averages=True,
        )

    @property
    def required_lookback(self) -> int:
        return MA_LONG + 1

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

    def _is_first_candle_of_day(self, candles: List[Dict], index: int, bought_dates: set) -> bool:
        date_string = self._get_paris_date_string(candles[index]['time'])
        if date_string in bought_dates:
            return False
        return True

    def _is_closing_hour(self, timestamp: int) -> bool:
        return is_last_candle_of_day(timestamp)

    def _is_last_candle_of_day(self, candles: List[Dict], index: int) -> bool:
        if index >= len(candles) - 1:
            return True
        current_date = self._get_paris_date_string(candles[index]['time'])
        next_date = self._get_paris_date_string(candles[index + 1]['time'])
        return current_date != next_date

    def _check_stop_loss(self, candle: Dict, buy_price: float) -> bool:
        sl_price = buy_price * (1 - SL_PERCENT / 100)
        return candle['low'] < sl_price

    def _check_golden_cross(self, ma50: List[Optional[float]], ma200: List[Optional[float]], index: int) -> bool:
        if ma50[index] is None or ma200[index] is None:
            return False
        return ma50[index] > ma200[index]

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
        ma50 = self._calculate_sma(closes, MA_SHORT)
        ma200 = self._calculate_sma(closes, MA_LONG)

        signals: List[Signal] = []
        bought_dates: set = set(position_open_on_day.keys())
        start_index = MA_LONG

        for i in range(start_index, len(candles) - 1):  # -1 to ensure next candle exists
            candle = candles[i]
            next_candle = candles[i + 1]
            date_string = self._get_paris_date_string(candle['time'])
            next_date_string = self._get_paris_date_string(next_candle['time'])

            # Check for buy signal at first candle of the day with golden cross filter
            # Condition checked on candle[i] close, entry on candle[i+1] open
            if self._is_first_candle_of_day(candles, i, bought_dates):
                if self._check_golden_cross(ma50, ma200, i):
                    signals.append(Signal(
                        signal_timestamp=next_candle['time'],
                        trigger_timestamp=candle['time'],
                        type='buy',
                        price=next_candle['open'],
                        label='Buy',
                        metadata={'ma50': ma50[i], 'ma200': ma200[i], 'filter': 'golden_cross'}
                    ))
                    position_open_on_day[next_date_string] = {
                        'buy_price': next_candle['open'],
                        'buy_time': next_candle['time'],
                    }
                    bought_dates.add(next_date_string)

            # Check if we have an open position today
            if date_string in position_open_on_day:
                position = position_open_on_day[date_string]
                buy_price = position['buy_price']

                # Check for Stop Loss trigger
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

                # Check for closing hour (22h) or last candle of day
                elif self._is_closing_hour(candle['time']) or self._is_last_candle_of_day(candles, i):
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
