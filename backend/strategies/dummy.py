from typing import List, Dict, Any, Optional
from datetime import datetime
import pytz
from .base import BaseStrategy, Signal, StrategyDisplayConfig

PARIS_TZ = pytz.timezone('Europe/Paris')


class DummyStrategy(BaseStrategy):
    """
    Dummy Strategy - Simple buy at open, sell at close

    Rules:
    - Buy at the first candle of the trading day (7h Paris time)
    - Sell at the last candle of the trading day
    - One trade per day
    """

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def display_config(self) -> StrategyDisplayConfig:
        return StrategyDisplayConfig(
            display_name="Dummy",
            description="Simple benchmark strategy. Buy at market open (7h Paris), sell at market close (22h Paris). No stop loss. One trade per day.",
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

    def calculate_signals(
        self,
        candles: List[Dict],
        initial_state: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Signal], Dict[str, Any]]:
        """
        Calculate Dummy signals.

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

            # Check for sell signal at closing hour (22h) or last candle of day
            if self._is_closing_hour(candle['time']) or self._is_last_candle_of_day(candles, i):
                if date_string in position_open_on_day:
                    position = position_open_on_day[date_string]
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='sell',
                        price=candle['close'],
                        label='Sell',
                        metadata={
                            'buy_price': position['buy_price'],
                            'buy_time': position['buy_time'],
                        }
                    ))
                    del position_open_on_day[date_string]

        # Return signals and final state
        final_state = {
            'position_open_on_day': position_open_on_day,
        }

        return signals, final_state
