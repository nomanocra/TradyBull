from typing import List, Dict, Any, Optional
from datetime import datetime
import pytz
from .base import BaseStrategy, Signal, StrategyDisplayConfig
from market_hours import is_last_candle_of_day, is_too_close_to_close

PARIS_TZ = pytz.timezone('Europe/Paris')

SL_PERCENT = 1.0  # -1%
MA_TREND_PERIOD = 200
MA_SLOPE_LOOKBACK = 20  # 20 hours for slope calculation
MIN_SLOPE_PCT = 0.02  # MA200 must have risen by at least 0.02%


class DailySL1TrendSlope02Strategy(BaseStrategy):
    """
    Daily SL-1% + Trend Filter Strategy with Minimum Slope 0.2%

    Entry:
    - First candle where price > MA200 AND MA200 rising by at least 0.2% over 20h
    - One trade per day max

    Exit (first condition met):
    - Stop Loss -1%
    - Price < MA200
    - MA200 falling
    - 22h Paris
    """

    @property
    def name(self) -> str:
        return "daily-sl1-trend-slope02"

    @property
    def display_config(self) -> StrategyDisplayConfig:
        return StrategyDisplayConfig(
            display_name="Multi-Daily SL-1% Trend200 Slope 0.02% IntraD",
            description="Entry: price > MA200 and MA200 rising >= 0.02% over 20h. Exit: SL -1%, trend break, or 22h.",
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

    def _is_closing_hour(self, timestamp: int) -> bool:
        return is_last_candle_of_day(timestamp)

    def _is_new_day(self, candles: List[Dict], index: int) -> bool:
        """Check if current candle is first of a new day (previous candle was different day)"""
        if index <= 0:
            return False
        prev_date = self._get_paris_date_string(candles[index - 1]['time'])
        curr_date = self._get_paris_date_string(candles[index]['time'])
        return prev_date != curr_date

    def _check_stop_loss(self, candle: Dict, buy_price: float) -> bool:
        sl_price = buy_price * (1 - SL_PERCENT / 100)
        return candle['low'] < sl_price

    def _check_trend_bullish(self, closes: List[float], ma200: List[Optional[float]], index: int) -> bool:
        """Check if trend is bullish: price > MA200 AND MA200 rising by at least MIN_SLOPE_PCT%"""
        if index < MA_SLOPE_LOOKBACK:
            return False

        current_ma = ma200[index]
        past_ma = ma200[index - MA_SLOPE_LOOKBACK]
        current_price = closes[index]

        if current_ma is None or past_ma is None:
            return False

        price_above_ma = current_price > current_ma

        # Calculate slope percentage
        slope_pct = ((current_ma - past_ma) / past_ma) * 100
        ma_rising_enough = slope_pct >= MIN_SLOPE_PCT

        return price_above_ma and ma_rising_enough

    def _check_trend_exit(self, candle: Dict, ma200: List[Optional[float]], index: int) -> tuple[bool, str]:
        """Check if trend exit conditions are met: LOW < MA200 OR MA200 falling"""
        if index < MA_SLOPE_LOOKBACK:
            return False, ''

        current_ma = ma200[index]
        past_ma = ma200[index - MA_SLOPE_LOOKBACK]

        if current_ma is None or past_ma is None:
            return False, ''

        # Exit if LOW goes below MA200 (price breached the trend line)
        if candle['low'] < current_ma:
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

        # Track single open position (not per day)
        if initial_state:
            open_position = initial_state.get('open_position', None)
        else:
            open_position = None

        closes = [c['close'] for c in candles]
        ma200 = self._calculate_sma(closes, MA_TREND_PERIOD)

        signals: List[Signal] = []
        start_index = MA_TREND_PERIOD + MA_SLOPE_LOOKBACK

        for i in range(start_index, len(candles) - 1):  # -1 to ensure next candle exists
            candle = candles[i]
            next_candle = candles[i + 1]
            date_string = self._get_paris_date_string(candle['time'])
            next_date_string = self._get_paris_date_string(next_candle['time'])

            # If new day and position open from previous day, close at PREVIOUS candle's close
            if open_position and self._is_new_day(candles, i):
                if open_position['date'] != date_string:
                    prev_candle = candles[i - 1]
                    signals.append(Signal(
                        signal_timestamp=prev_candle['time'],
                        trigger_timestamp=prev_candle['time'],
                        type='sell',
                        price=prev_candle['close'],
                        label='Close',
                        metadata={
                            'buy_price': open_position['buy_price'],
                            'buy_time': open_position['buy_time'],
                            'exit_reason': 'end_of_day',
                        }
                    ))
                    open_position = None

            # Check for buy signal (only if no open position and not too close to close)
            # Condition checked on candle[i] close, entry on candle[i+1] open
            if open_position is None:
                if self._check_trend_bullish(closes, ma200, i) and not is_too_close_to_close(candle['time']):
                    signals.append(Signal(
                        signal_timestamp=next_candle['time'],
                        trigger_timestamp=candle['time'],
                        type='buy',
                        price=next_candle['open'],
                        label='Buy',
                        metadata={'ma200': ma200[i], 'trend_filter': 'slope_0.02%'}
                    ))
                    open_position = {
                        'buy_price': next_candle['open'],
                        'buy_time': next_candle['time'],
                        'date': next_date_string,
                    }
                    continue  # Skip exit checks on entry candle

            # Check exit conditions if we have an open position
            if open_position:
                buy_price = open_position['buy_price']

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
                            'buy_time': open_position['buy_time'],
                            'exit_reason': 'stop_loss',
                        }
                    ))
                    open_position = None
                    continue

                # Check for trend exit (LOW < MA200 OR MA200 falling)
                trend_exit, exit_reason = self._check_trend_exit(candle, ma200, i)
                if trend_exit:
                    # If price breached MA200, exit at MA200; if MA falling, exit at close
                    exit_price = ma200[i] if exit_reason == 'price_below_ma200' else candle['close']
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='sell',
                        price=exit_price,
                        label='Trend',
                        metadata={
                            'buy_price': buy_price,
                            'buy_time': open_position['buy_time'],
                            'exit_reason': exit_reason,
                            'ma200': ma200[i],
                        }
                    ))
                    open_position = None
                    continue

                # Check for closing hour (22h)
                if self._is_closing_hour(candle['time']):
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='sell',
                        price=candle['close'],
                        label='Close',
                        metadata={
                            'buy_price': buy_price,
                            'buy_time': open_position['buy_time'],
                            'exit_reason': 'end_of_day',
                        }
                    ))
                    open_position = None

        final_state = {
            'open_position': open_position,
        }

        return signals, final_state
