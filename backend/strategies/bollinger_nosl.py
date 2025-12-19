from typing import List, Dict, Any, Optional
from datetime import datetime
import pytz
from .base import BaseStrategy, Signal

PARIS_TZ = pytz.timezone('Europe/Paris')

# Constants matching TypeScript implementation in src/lib/strategies/bollinger-nosl.ts
BB_PERIOD = 20
BB_STD_DEV = 2


class BollingerNoSLStrategy(BaseStrategy):
    """
    Bollinger NoSL Strategy

    Rules:
    - Buy signal when candle LOW goes below Bollinger lower band
    - Signal is placed on the NEXT candle (buy at open of next candle)
    - Only between 7h and 21h (Paris time)
    - Only ONE position per day (no new position if one already opened)
    - Sell at 22h if a position is open
    - No stop loss (NoSL)
    """

    @property
    def name(self) -> str:
        return "bollinger-nosl"

    @property
    def required_lookback(self) -> int:
        return BB_PERIOD + 1  # Need BB_PERIOD candles + 1 for next candle

    def _calculate_sma(self, data: List[float], period: int) -> List[Optional[float]]:
        """Calculate Simple Moving Average"""
        result: List[Optional[float]] = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(None)
            else:
                window = data[i - period + 1:i + 1]
                result.append(sum(window) / period)
        return result

    def _calculate_std_dev(self, data: List[float], period: int, sma: List[Optional[float]]) -> List[Optional[float]]:
        """Calculate Standard Deviation (population formula, not sample)"""
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
        """Calculate Bollinger Bands (middle, upper, lower)"""
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
        """Get hour in Paris timezone from Unix timestamp"""
        dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
        return dt.hour

    def _get_paris_date_string(self, timestamp: int) -> str:
        """Get date string (YYYY-MM-DD) in Paris timezone"""
        dt = datetime.fromtimestamp(timestamp, tz=PARIS_TZ)
        return dt.strftime('%Y-%m-%d')

    def _is_last_candle_of_day(self, candles: List[Dict], index: int) -> bool:
        """Check if this candle is the last one of its day (in Paris time)"""
        if index >= len(candles) - 1:
            return True  # Last candle in dataset

        current_date = self._get_paris_date_string(candles[index]['time'])
        next_date = self._get_paris_date_string(candles[index + 1]['time'])

        return current_date != next_date

    def calculate_signals(
        self,
        candles: List[Dict],
        initial_state: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Signal], Dict[str, Any]]:
        """
        Calculate Bollinger NoSL signals.

        State includes:
        - last_signal_triggered: bool - Are we waiting for price to go back above band?
        - position_open_on_day: Dict[str, Dict] - Positions open per day
        """
        if len(candles) < self.required_lookback:
            return [], initial_state or {}

        # Initialize or restore state
        if initial_state:
            last_signal_triggered = initial_state.get('last_signal_triggered', False)
            position_open_on_day = initial_state.get('position_open_on_day', {})
        else:
            last_signal_triggered = False
            position_open_on_day = {}

        closes = [c['close'] for c in candles]
        bands = self._calculate_bollinger_bands(closes)
        lower = bands['lower']

        signals: List[Signal] = []

        for i in range(BB_PERIOD, len(candles)):
            candle = candles[i]
            lower_band = lower[i]
            hour = self._get_paris_hour(candle['time'])
            date_string = self._get_paris_date_string(candle['time'])

            # Check for sell signal at end of day (last candle of the day)
            if self._is_last_candle_of_day(candles, i):
                if date_string in position_open_on_day:
                    position = position_open_on_day[date_string]
                    signals.append(Signal(
                        signal_timestamp=candle['time'],
                        trigger_timestamp=candle['time'],
                        type='sell',
                        price=candle['close'],  # Use close price for end of day
                        label='Sell',
                        metadata={
                            'buy_price': position['buy_price'],
                            'buy_time': position['buy_time'],
                        }
                    ))
                    del position_open_on_day[date_string]

            if lower_band is None:
                continue
            if i >= len(candles) - 1:
                continue  # Need next candle for buy signal

            is_in_trading_hours = 7 <= hour <= 21
            has_position_today = date_string in position_open_on_day

            # Check if LOW went below lower Bollinger band
            low_below_band = candle['low'] < lower_band

            if low_below_band and is_in_trading_hours and not last_signal_triggered and not has_position_today:
                # Signal on NEXT candle
                next_candle = candles[i + 1]
                next_hour = self._get_paris_hour(next_candle['time'])
                next_date_string = self._get_paris_date_string(next_candle['time'])

                # Check if next candle is still in trading hours
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
                        }
                    ))

                    # Mark position as open for this day
                    position_open_on_day[next_date_string] = {
                        'buy_price': next_candle['open'],
                        'buy_time': next_candle['time'],
                    }

                    last_signal_triggered = True

            # Reset trigger when price goes back above the band
            if candle['low'] > lower_band:
                last_signal_triggered = False

        # Return signals and final state
        final_state = {
            'last_signal_triggered': last_signal_triggered,
            'position_open_on_day': position_open_on_day,
        }

        return signals, final_state
