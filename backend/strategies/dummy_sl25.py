from typing import List, Dict, Any, Optional
from datetime import datetime
import pytz
from .base import BaseStrategy, Signal, StrategyDisplayConfig

PARIS_TZ = pytz.timezone('Europe/Paris')

# Stop Loss percentage
SL_PERCENT = 2.5  # -2.5%


class DummySL25Strategy(BaseStrategy):
    """
    Dummy SL-2.5 Strategy - Buy at open with -2.5% Stop Loss

    Rules:
    - Buy at the first candle of the trading day (7h Paris time)
    - Stop Loss at -2.5%: if LOW goes below buy_price * 0.975, close position
    - If SL not triggered, close at 22h
    - One trade per day
    """

    @property
    def name(self) -> str:
        return "dummy-sl25"

    @property
    def display_config(self) -> StrategyDisplayConfig:
        return StrategyDisplayConfig(
            display_name="Dummy SL-2.5%",
            description="Benchmark strategy with stop loss. Buy at market open (7h Paris). Stop loss at -2.5%. Closes at 22h if SL not triggered. One trade per day.",
        )

    @property
    def required_lookback(self) -> int:
        return 1

    def _get_paris_hour(self, timestamp: int) -> int:
        """Get hour in Paris timezone from Unix timestamp"""
        dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
        return dt.hour

    def _get_paris_date_string(self, timestamp: int) -> str:
        """Get date string (YYYY-MM-DD) in Paris timezone"""
        dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
        return dt.strftime('%Y-%m-%d')

    def _is_first_candle_of_day(self, candles: List[Dict], index: int, bought_dates: set) -> bool:
        """Check if this is the first candle of the day that we haven't bought yet"""
        date_string = self._get_paris_date_string(candles[index]['time'])

        if date_string in bought_dates:
            return False

        return True

    def _is_closing_hour(self, timestamp: int) -> bool:
        """Check if this candle is at the closing hour (22h Paris time)"""
        return self._get_paris_hour(timestamp) == 22

    def _is_last_candle_of_day(self, candles: List[Dict], index: int) -> bool:
        """Check if this candle is the last one of its day (fallback for missing 22h candles)"""
        if index >= len(candles) - 1:
            return True
        current_date = self._get_paris_date_string(candles[index]['time'])
        next_date = self._get_paris_date_string(candles[index + 1]['time'])
        return current_date != next_date

    def _check_stop_loss(self, candle: Dict, buy_price: float) -> bool:
        """Check if stop loss is triggered (LOW below -2.5% of buy price)"""
        sl_price = buy_price * (1 - SL_PERCENT / 100)
        return candle['low'] < sl_price

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

        signals: List[Signal] = []
        bought_dates: set = set(position_open_on_day.keys())

        for i in range(len(candles)):
            candle = candles[i]
            date_string = self._get_paris_date_string(candle['time'])

            # Buy at first candle of the day
            if self._is_first_candle_of_day(candles, i, bought_dates):
                signals.append(Signal(
                    signal_timestamp=candle['time'],
                    trigger_timestamp=candle['time'],
                    type='buy',
                    price=candle['open'],
                    label='Buy',
                    metadata={}
                ))
                position_open_on_day[date_string] = {
                    'buy_price': candle['open'],
                    'buy_time': candle['time'],
                }
                bought_dates.add(date_string)

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

                # Close at 22h or last candle of day if position still open
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
