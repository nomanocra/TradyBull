from typing import List, Dict, Any, Optional
from datetime import datetime
import pytz
from .base import BaseStrategy, Signal, StrategyDisplayConfig

PARIS_TZ = pytz.timezone('Europe/Paris')

# Stop Loss percentage
SL_PERCENT = 1.0  # -1%


class DailySL1Strategy(BaseStrategy):
    """
    Daily SL-1% Strategy

    Entry:
    - First candle of the day
    - One trade per day max

    Exit (first condition met):
    - Stop Loss -1%
    - 22h Paris
    """

    @property
    def name(self) -> str:
        return "daily-sl1"

    @property
    def display_config(self) -> StrategyDisplayConfig:
        return StrategyDisplayConfig(
            display_name="Multi-Daily SL-1%",
            description="Entry: first candle of the day. Exit: SL -1% or 22h.",
        )

    @property
    def required_lookback(self) -> int:
        return 1  # No lookback needed

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

        # Must not have already bought today
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
        """Check if stop loss is triggered (LOW below -1% of buy price)"""
        sl_price = buy_price * (1 - SL_PERCENT / 100)
        return candle['low'] < sl_price

    def calculate_signals(
        self,
        candles: List[Dict],
        initial_state: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Signal], Dict[str, Any]]:
        """
        Calculate Daily SL-1 signals.

        State includes:
        - position_open_on_day: Dict[str, Dict] - Positions open per day
        """
        if len(candles) < self.required_lookback:
            return [], initial_state or {}

        # Initialize or restore state
        if initial_state:
            position_open_on_day = initial_state.get('position_open_on_day', {})
        else:
            position_open_on_day = {}

        signals: List[Signal] = []
        bought_dates: set = set(position_open_on_day.keys())

        for i in range(len(candles)):
            candle = candles[i]
            date_string = self._get_paris_date_string(candle['time'])

            # Check for buy signal at first candle of the day
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
                        price=sl_price,  # Sell at SL price
                        label='SL',
                        metadata={
                            'buy_price': buy_price,
                            'buy_time': position['buy_time'],
                            'exit_reason': 'stop_loss',
                        }
                    ))
                    del position_open_on_day[date_string]

                # Check for closing hour (22h) or last candle of day - only if position still open
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

        # Return signals and final state
        final_state = {
            'position_open_on_day': position_open_on_day,
        }

        return signals, final_state
