from typing import List, Dict, Any, Optional
from datetime import datetime
import pytz
from .base import BaseStrategy, Signal, StrategyDisplayConfig
from market_hours import is_last_candle_of_day, is_too_close_to_close

PARIS_TZ = pytz.timezone('Europe/Paris')

BB_PERIOD = 20
BB_STD_DEV = 2
SL_PERCENT = 2.5  # -2.5%
MA_TREND_PERIOD = 200  # MA200 for trend filter
MA_SLOPE_LOOKBACK = 5  # Check if MA200 is rising over last 5 candles


class BollingerSL25TrendStrategy(BaseStrategy):
    """
    Bollinger SL-2.5% + Trend Filter Strategy

    Rules:
    - Buy signal when candle LOW goes below Bollinger lower band
    - Signal is placed on the NEXT candle (buy at open of next candle)
    - Only between 7h and 21h (Paris time)
    - Only ONE position per day
    - Stop Loss at -2.5%: if LOW goes below buy_price * 0.975, close position
    - If SL not triggered, close at 22h

    Trend Filter (NEW):
    - Only buy if price > MA200
    - Only buy if MA200 is rising (MA200[t] > MA200[t-5])
    """

    @property
    def name(self) -> str:
        return "bollinger-sl25-trend"

    @property
    def display_config(self) -> StrategyDisplayConfig:
        return StrategyDisplayConfig(
            display_name="Bollinger SL-2.5% Trend200 IntraD",
            description="Entry: 7h-21h, price touches lower BB, price > MA200 and MA200 rising. Exit: SL -2.5% or 22h.",
            show_bollinger=True,
            show_moving_averages=True,
        )

    @property
    def required_lookback(self) -> int:
        return max(BB_PERIOD, MA_TREND_PERIOD + MA_SLOPE_LOOKBACK) + 1

    def _calculate_sma(self, data: List[float], period: int) -> List[Optional[float]]:
        result: List[Optional[float]] = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(None)
            else:
                window = data[i - period + 1:i + 1]
                result.append(sum(window) / period)
        return result

    def _calculate_std_dev(self, data: List[float], period: int, sma: List[Optional[float]]) -> List[Optional[float]]:
        result: List[Optional[float]] = []
        for i in range(len(data)):
            if i < period - 1 or sma[i] is None:
                result.append(None)
            else:
                window = data[i - period + 1:i + 1]
                mean = sma[i]
                squared_diffs = [(val - mean) ** 2 for val in window]
                variance = sum(squared_diffs) / period
                result.append(variance ** 0.5)
        return result

    def _calculate_bollinger_bands(self, closes: List[float]) -> Dict[str, List[Optional[float]]]:
        sma = self._calculate_sma(closes, BB_PERIOD)
        std_dev = self._calculate_std_dev(closes, BB_PERIOD, sma)

        upper: List[Optional[float]] = []
        lower: List[Optional[float]] = []

        for i in range(len(closes)):
            if sma[i] is not None and std_dev[i] is not None:
                upper.append(sma[i] + BB_STD_DEV * std_dev[i])
                lower.append(sma[i] - BB_STD_DEV * std_dev[i])
            else:
                upper.append(None)
                lower.append(None)

        return {'middle': sma, 'upper': upper, 'lower': lower}

    def _get_paris_hour(self, timestamp: int) -> int:
        dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
        return dt.hour

    def _get_paris_date_string(self, timestamp: int) -> str:
        dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
        return dt.strftime('%Y-%m-%d')

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

    def _check_trend_filter(self, closes: List[float], ma200: List[Optional[float]], index: int) -> bool:
        """
        Check if trend conditions are met:
        1. Price > MA200
        2. MA200 is rising (current > lookback periods ago)
        """
        if index < MA_SLOPE_LOOKBACK:
            return False

        current_ma = ma200[index]
        past_ma = ma200[index - MA_SLOPE_LOOKBACK]
        current_price = closes[index]

        if current_ma is None or past_ma is None:
            return False

        # Price must be above MA200
        price_above_ma = current_price > current_ma

        # MA200 must be rising
        ma_rising = current_ma > past_ma

        return price_above_ma and ma_rising

    def calculate_signals(
        self,
        candles: List[Dict],
        initial_state: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Signal], Dict[str, Any]]:
        if len(candles) < self.required_lookback:
            return [], initial_state or {}

        if initial_state:
            last_signal_triggered = initial_state.get('last_signal_triggered', False)
            position_open_on_day = initial_state.get('position_open_on_day', {})
            traded_dates = set(initial_state.get('traded_dates', []))
        else:
            last_signal_triggered = False
            position_open_on_day = {}
            traded_dates: set = set()

        closes = [c['close'] for c in candles]
        bands = self._calculate_bollinger_bands(closes)
        lower = bands['lower']

        # Calculate MA200 for trend filter
        ma200 = self._calculate_sma(closes, MA_TREND_PERIOD)

        signals: List[Signal] = []

        start_index = max(BB_PERIOD, MA_TREND_PERIOD + MA_SLOPE_LOOKBACK)

        for i in range(start_index, len(candles)):
            candle = candles[i]
            lower_band = lower[i]
            hour = self._get_paris_hour(candle['time'])
            date_string = self._get_paris_date_string(candle['time'])

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

            if lower_band is None:
                continue
            if i >= len(candles) - 1:
                continue

            is_in_trading_hours = 7 <= hour <= 21
            already_traded_today = date_string in traded_dates

            # NEW: Check trend filter
            trend_ok = self._check_trend_filter(closes, ma200, i)

            # Check if LOW went below lower Bollinger band
            low_below_band = candle['low'] < lower_band

            if low_below_band and is_in_trading_hours and not last_signal_triggered and not already_traded_today and trend_ok and not is_too_close_to_close(candle['time']):
                next_candle = candles[i + 1]
                next_hour = self._get_paris_hour(next_candle['time'])
                next_date_string = self._get_paris_date_string(next_candle['time'])

                if 7 <= next_hour <= 21:
                    signals.append(Signal(
                        signal_timestamp=next_candle['time'],
                        trigger_timestamp=candle['time'],
                        type='buy',
                        price=next_candle['open'],
                        label='Buy',
                        metadata={
                            'lower_band': lower_band,
                            'trigger_low': candle['low'],
                            'ma200': ma200[i],
                            'trend_filter': 'passed',
                        }
                    ))

                    position_open_on_day[next_date_string] = {
                        'buy_price': next_candle['open'],
                        'buy_time': next_candle['time'],
                    }
                    traded_dates.add(next_date_string)

                    last_signal_triggered = True

            # Reset trigger when price goes back above the band
            if lower_band is not None and candle['low'] > lower_band:
                last_signal_triggered = False

        return signals, {'last_signal_triggered': last_signal_triggered, 'position_open_on_day': position_open_on_day, 'traded_dates': list(traded_dates)}
