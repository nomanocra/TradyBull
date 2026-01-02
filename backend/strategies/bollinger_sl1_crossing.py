from typing import List, Dict, Any, Optional
from datetime import datetime
import pytz
from .base import BaseStrategy, Signal, StrategyDisplayConfig
from market_hours import is_last_candle_of_day

PARIS_TZ = pytz.timezone('Europe/Paris')

BB_PERIOD = 20
BB_STD_DEV = 2
SL_PERCENT = 1.0  # -1%
MA_SHORT = 50
MA_LONG = 200


class BollingerSL1CrossingStrategy(BaseStrategy):
    """
    Bollinger SL-1% + Golden Cross Filter Strategy

    Rules:
    - Buy signal when candle LOW goes below Bollinger lower band
    - Signal is placed on the NEXT candle (buy at open of next candle)
    - Only between 7h and 21h (Paris time)
    - Only ONE position per day
    - Stop Loss at -1%: if LOW goes below buy_price * 0.99, close position
    - If SL not triggered, close at 22h

    Golden Cross Filter:
    - Only buy if MA50 > MA200
    """

    @property
    def name(self) -> str:
        return "bollinger-sl1-crossing"

    @property
    def display_config(self) -> StrategyDisplayConfig:
        return StrategyDisplayConfig(
            display_name="Bollinger SL-1% Crossing",
            description="Entry: 7h-21h, price touches lower BB, MA50 > MA200. Exit: SL -1% or 22h.",
            show_bollinger=True,
            show_moving_averages=True,
        )

    @property
    def required_lookback(self) -> int:
        return max(BB_PERIOD, MA_LONG) + 1

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
        ma50 = self._calculate_sma(closes, MA_SHORT)
        ma200 = self._calculate_sma(closes, MA_LONG)

        signals: List[Signal] = []
        start_index = MA_LONG

        for i in range(start_index, len(candles)):
            candle = candles[i]
            lower_band = lower[i]
            hour = self._get_paris_hour(candle['time'])
            date_string = self._get_paris_date_string(candle['time'])

            if date_string in position_open_on_day:
                position = position_open_on_day[date_string]
                buy_price = position['buy_price']

                if self._check_stop_loss(candle, buy_price):
                    sl_price = buy_price * (1 - SL_PERCENT / 100)
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='sell',
                        price=sl_price,
                        label='SL',
                        metadata={'buy_price': buy_price, 'buy_time': position['buy_time'], 'exit_reason': 'stop_loss'}
                    ))
                    del position_open_on_day[date_string]

                elif self._is_closing_hour(candle['time']) or self._is_last_candle_of_day(candles, i):
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='sell',
                        price=candle['close'],
                        label='Close',
                        metadata={'buy_price': buy_price, 'buy_time': position['buy_time'], 'exit_reason': 'end_of_day'}
                    ))
                    del position_open_on_day[date_string]

            if lower_band is None or i >= len(candles) - 1:
                continue

            is_in_trading_hours = 7 <= hour <= 21
            already_traded_today = date_string in traded_dates
            golden_cross_active = self._check_golden_cross(ma50, ma200, i)
            low_below_band = candle['low'] < lower_band

            if low_below_band and is_in_trading_hours and not last_signal_triggered and not already_traded_today and golden_cross_active:
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
                        metadata={'lower_band': lower_band, 'trigger_low': candle['low'], 'ma50': ma50[i], 'ma200': ma200[i], 'filter': 'golden_cross'}
                    ))
                    position_open_on_day[next_date_string] = {'buy_price': next_candle['open'], 'buy_time': next_candle['time']}
                    traded_dates.add(next_date_string)
                    last_signal_triggered = True

            if lower_band is not None and candle['low'] > lower_band:
                last_signal_triggered = False

        return signals, {'last_signal_triggered': last_signal_triggered, 'position_open_on_day': position_open_on_day, 'traded_dates': list(traded_dates)}
