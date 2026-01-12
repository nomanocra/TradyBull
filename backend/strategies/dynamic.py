"""
Dynamic Strategy - Interprets JSON configuration to calculate signals.
Allows users to create strategies without writing Python code.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .base import BaseStrategy, Signal, StrategyDisplayConfig
from market_hours import is_last_candle_of_day, is_too_close_to_close, is_first_candle_of_session, get_paris_hour


@dataclass
class DynamicStrategyConfig:
    """Configuration for a dynamic strategy"""
    name: str
    display_name: str
    indicator: Optional[Dict[str, str]] = None  # {"type": "bollinger", "mode": "both"}
    stop_loss: Optional[float] = None  # Percentage (e.g., 1.0 for -1%)
    ma_trend: Optional[int] = None  # MA period for trend filter (e.g., 200)
    value_above_ma: Optional[int] = None  # Price must be above this MA
    ma_cross: Optional[Dict[str, int]] = None  # {"fast": 50, "slow": 200}
    intraday: str = "none"  # "none", "daily", "multi-daily"
    time_constraint: Optional[Dict[str, str]] = None  # {"open": "07:00", "close": "23:00"}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DynamicStrategyConfig':
        return cls(
            name=data.get('name', 'dynamic'),
            display_name=data.get('display_name', 'Dynamic Strategy'),
            indicator=data.get('indicator'),
            stop_loss=data.get('stop_loss'),
            ma_trend=data.get('ma_trend'),
            value_above_ma=data.get('value_above_ma'),
            ma_cross=data.get('ma_cross'),
            intraday=data.get('intraday', 'none'),
            time_constraint=data.get('time_constraint'),
        )


class DynamicStrategy(BaseStrategy):
    """
    A configurable strategy that interprets JSON parameters.
    Supports various indicators and conditions without hardcoded logic.
    """

    # Indicator constants
    BB_PERIOD = 20
    BB_STD_DEV = 2
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    ICHIMOKU_TENKAN = 9
    ICHIMOKU_KIJUN = 26
    ICHIMOKU_SENKOU_B = 52
    RSI_PERIOD = 14
    RSI_OVERSOLD = 20
    RSI_OVERBOUGHT = 80

    def __init__(self, config: DynamicStrategyConfig):
        self.config = config
        self._name = config.name
        self._display_name = config.display_name

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_config(self) -> StrategyDisplayConfig:
        indicator = self.config.indicator
        indicator_type = indicator.get('type') if indicator else None

        # Collect specific MA periods used by this strategy
        ma_periods_set = set()
        if self.config.ma_trend:
            ma_periods_set.add(self.config.ma_trend)
        if self.config.value_above_ma:
            ma_periods_set.add(self.config.value_above_ma)
        if self.config.ma_cross:
            ma_periods_set.add(self.config.ma_cross['fast'])
            ma_periods_set.add(self.config.ma_cross['slow'])
        ma_periods = sorted(ma_periods_set)

        return StrategyDisplayConfig(
            display_name=self._display_name,
            description=self._generate_description(),
            show_bollinger=indicator_type in ('bollinger', 'bollinger-rsi'),
            show_macd=indicator_type in ('macd-cross', 'macd-zero', 'macd-histogram'),
            show_ichimoku=indicator_type in ('ichimoku-kumo', 'ichimoku-tk'),
            show_moving_averages=len(ma_periods) > 0,
            show_rsi=indicator_type in ('rsi-trend', 'rsi-early', 'rsi-late', 'rsi-large', 'rsi-small', 'bollinger-rsi'),
            ma_periods=ma_periods,
        )

    @property
    def required_lookback(self) -> int:
        lookback = 50  # Base minimum

        # MA requirements
        if self.config.ma_trend:
            lookback = max(lookback, self.config.ma_trend + 10)
        if self.config.value_above_ma:
            lookback = max(lookback, self.config.value_above_ma + 10)
        if self.config.ma_cross:
            lookback = max(lookback, self.config.ma_cross.get('slow', 200) + 10)

        # Indicator requirements
        indicator = self.config.indicator
        if indicator:
            ind_type = indicator.get('type')
            if ind_type == 'bollinger':
                lookback = max(lookback, self.BB_PERIOD + 10)
            elif ind_type in ('macd-cross', 'macd-zero', 'macd-histogram'):
                lookback = max(lookback, self.MACD_SLOW + self.MACD_SIGNAL + 10)
            elif ind_type in ('ichimoku-kumo', 'ichimoku-tk'):
                lookback = max(lookback, self.ICHIMOKU_SENKOU_B + 30)
            elif ind_type in ('rsi-trend', 'rsi-early', 'rsi-late', 'rsi-large', 'rsi-small'):
                lookback = max(lookback, self.RSI_PERIOD + 10)
            elif ind_type == 'bollinger-rsi':
                # Combined: need both BB and RSI lookbacks
                lookback = max(lookback, self.BB_PERIOD + 10, self.RSI_PERIOD + 10)

        return lookback

    def _generate_description(self) -> str:
        """Generate a human-readable description from config"""
        parts_buy = []
        parts_sell = []

        # Indicator
        indicator = self.config.indicator
        if indicator:
            ind_type = indicator.get('type', '').upper().replace('-', ' ')
            mode = indicator.get('mode', 'both')
            if mode in ('buy', 'both'):
                parts_buy.append(ind_type)
            if mode in ('sell', 'both'):
                parts_sell.append(ind_type)

        # MA conditions (symmetric)
        if self.config.ma_trend:
            parts_buy.append(f"MA{self.config.ma_trend} rising")
            parts_sell.append(f"MA{self.config.ma_trend} falling")
        if self.config.value_above_ma:
            parts_buy.append(f"price > MA{self.config.value_above_ma}")
            parts_sell.append(f"price < MA{self.config.value_above_ma}")
        if self.config.ma_cross:
            fast = self.config.ma_cross.get('fast')
            slow = self.config.ma_cross.get('slow')
            parts_buy.append(f"MA{fast} > MA{slow}")
            parts_sell.append(f"MA{fast} < MA{slow}")

        # Stop loss (sell only)
        if self.config.stop_loss:
            parts_sell.append(f"SL -{self.config.stop_loss}%")

        # Intraday (sell only)
        if self.config.intraday in ('daily', 'multi-daily'):
            parts_sell.append("EOD close")

        # Time constraint (both)
        if self.config.time_constraint:
            tc = self.config.time_constraint
            time_str = f"{tc.get('open', '00:00')}-{tc.get('close', '23:59')}"
            parts_buy.append(f"hours {time_str}")
            parts_sell.append(f"hours {time_str}")

        buy_str = " + ".join(parts_buy) if parts_buy else "any"
        sell_str = " + ".join(parts_sell) if parts_sell else "any"

        return f"BUY: {buy_str}.\nSELL: {sell_str}."

    # ==================== Indicator Calculations ====================

    def _calculate_sma(self, data: List[float], period: int) -> List[Optional[float]]:
        """Simple Moving Average"""
        result: List[Optional[float]] = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(None)
            else:
                window = data[i - period + 1:i + 1]
                result.append(sum(window) / period)
        return result

    def _calculate_ema(self, values: List[float], period: int) -> List[Optional[float]]:
        """Exponential Moving Average"""
        n = len(values)
        ema: List[Optional[float]] = [None] * n
        if n < period:
            return ema

        # Initial SMA
        sma = sum(values[:period]) / period
        ema[period - 1] = sma

        multiplier = 2 / (period + 1)
        for i in range(period, n):
            ema[i] = (values[i] - ema[i - 1]) * multiplier + ema[i - 1]

        return ema

    def _calculate_std_dev(self, data: List[float], period: int, sma: List[Optional[float]]) -> List[Optional[float]]:
        """Standard Deviation"""
        result: List[Optional[float]] = []
        for i in range(len(data)):
            if i < period - 1 or sma[i] is None:
                result.append(None)
            else:
                window = data[i - period + 1:i + 1]
                mean = sma[i]
                variance = sum((x - mean) ** 2 for x in window) / period
                result.append(variance ** 0.5)
        return result

    def _calculate_bollinger(self, closes: List[float]) -> Dict[str, List[Optional[float]]]:
        """Bollinger Bands"""
        sma = self._calculate_sma(closes, self.BB_PERIOD)
        std = self._calculate_std_dev(closes, self.BB_PERIOD, sma)

        upper = [None] * len(closes)
        lower = [None] * len(closes)

        for i in range(len(closes)):
            if sma[i] is not None and std[i] is not None:
                upper[i] = sma[i] + self.BB_STD_DEV * std[i]
                lower[i] = sma[i] - self.BB_STD_DEV * std[i]

        return {'middle': sma, 'upper': upper, 'lower': lower}

    def _calculate_macd(self, closes: List[float]) -> Dict[str, List[Optional[float]]]:
        """MACD: Line, Signal, Histogram"""
        ema_fast = self._calculate_ema(closes, self.MACD_FAST)
        ema_slow = self._calculate_ema(closes, self.MACD_SLOW)
        n = len(closes)

        # MACD Line
        macd_line: List[Optional[float]] = [None] * n
        for i in range(n):
            if ema_fast[i] is not None and ema_slow[i] is not None:
                macd_line[i] = ema_fast[i] - ema_slow[i]

        # Signal Line (EMA of MACD)
        signal_line: List[Optional[float]] = [None] * n
        start_idx = self.MACD_SLOW - 1

        if n > start_idx + self.MACD_SIGNAL:
            macd_values = [v if v is not None else 0 for v in macd_line]
            macd_subset = macd_values[start_idx:start_idx + self.MACD_SIGNAL]
            sma = sum(macd_subset) / self.MACD_SIGNAL
            signal_idx = start_idx + self.MACD_SIGNAL - 1
            signal_line[signal_idx] = sma

            multiplier = 2 / (self.MACD_SIGNAL + 1)
            for i in range(signal_idx + 1, n):
                if macd_line[i] is not None:
                    signal_line[i] = (macd_line[i] - signal_line[i - 1]) * multiplier + signal_line[i - 1]

        # Histogram
        histogram: List[Optional[float]] = [None] * n
        for i in range(n):
            if macd_line[i] is not None and signal_line[i] is not None:
                histogram[i] = macd_line[i] - signal_line[i]

        return {'macd': macd_line, 'signal': signal_line, 'histogram': histogram}

    def _calculate_ichimoku(self, candles: List[Dict]) -> Dict[str, List[Optional[float]]]:
        """Ichimoku Cloud components"""
        n = len(candles)

        def period_high_low(start: int, end: int) -> tuple:
            highs = [candles[i]['high'] for i in range(start, end + 1)]
            lows = [candles[i]['low'] for i in range(start, end + 1)]
            return max(highs), min(lows)

        tenkan: List[Optional[float]] = [None] * n
        kijun: List[Optional[float]] = [None] * n
        senkou_a: List[Optional[float]] = [None] * n
        senkou_b: List[Optional[float]] = [None] * n

        for i in range(n):
            # Tenkan-sen (9 periods)
            if i >= self.ICHIMOKU_TENKAN - 1:
                h, l = period_high_low(i - self.ICHIMOKU_TENKAN + 1, i)
                tenkan[i] = (h + l) / 2

            # Kijun-sen (26 periods)
            if i >= self.ICHIMOKU_KIJUN - 1:
                h, l = period_high_low(i - self.ICHIMOKU_KIJUN + 1, i)
                kijun[i] = (h + l) / 2

            # Senkou Span A (shifted 26 periods ahead - we store at current for simplicity)
            if tenkan[i] is not None and kijun[i] is not None:
                senkou_a[i] = (tenkan[i] + kijun[i]) / 2

            # Senkou Span B (52 periods)
            if i >= self.ICHIMOKU_SENKOU_B - 1:
                h, l = period_high_low(i - self.ICHIMOKU_SENKOU_B + 1, i)
                senkou_b[i] = (h + l) / 2

        return {
            'tenkan': tenkan,
            'kijun': kijun,
            'senkou_a': senkou_a,
            'senkou_b': senkou_b,
        }

    def _calculate_rsi(self, closes: List[float]) -> List[Optional[float]]:
        """Relative Strength Index"""
        n = len(closes)
        rsi: List[Optional[float]] = [None] * n

        if n < self.RSI_PERIOD + 1:
            return rsi

        # Calculate price changes
        changes = [0.0] * n
        for i in range(1, n):
            changes[i] = closes[i] - closes[i - 1]

        # Initial average gain/loss
        gains = [max(0, c) for c in changes]
        losses = [abs(min(0, c)) for c in changes]

        avg_gain = sum(gains[1:self.RSI_PERIOD + 1]) / self.RSI_PERIOD
        avg_loss = sum(losses[1:self.RSI_PERIOD + 1]) / self.RSI_PERIOD

        # First RSI value
        if avg_loss == 0:
            rsi[self.RSI_PERIOD] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[self.RSI_PERIOD] = 100 - (100 / (1 + rs))

        # Subsequent values using smoothed averages
        for i in range(self.RSI_PERIOD + 1, n):
            avg_gain = (avg_gain * (self.RSI_PERIOD - 1) + gains[i]) / self.RSI_PERIOD
            avg_loss = (avg_loss * (self.RSI_PERIOD - 1) + losses[i]) / self.RSI_PERIOD

            if avg_loss == 0:
                rsi[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi[i] = 100 - (100 / (1 + rs))

        return rsi

    # ==================== Condition Checks ====================

    def _check_indicator_buy(self, candles: List[Dict], i: int, indicators: Dict) -> bool:
        """Check if indicator signals a BUY at index i"""
        ind_config = self.config.indicator
        if not ind_config:
            return True  # No indicator = always true

        ind_type = ind_config.get('type')
        mode = ind_config.get('mode', 'both')

        if mode == 'sell':
            return True  # Indicator only for sell, buy is always OK

        candle = candles[i]

        if ind_type == 'bollinger':
            bb = indicators.get('bollinger', {})
            lower = bb.get('lower', [None] * len(candles))[i]
            if lower is None:
                return False
            return candle['low'] < lower

        elif ind_type == 'macd-cross':
            macd = indicators.get('macd', {})
            macd_line = macd.get('macd', [None] * len(candles))
            signal_line = macd.get('signal', [None] * len(candles))
            if i < 1 or macd_line[i] is None or signal_line[i] is None:
                return False
            if macd_line[i - 1] is None or signal_line[i - 1] is None:
                return False
            # Bullish cross: MACD was below signal, now above
            return macd_line[i - 1] <= signal_line[i - 1] and macd_line[i] > signal_line[i]

        elif ind_type == 'macd-zero':
            macd = indicators.get('macd', {})
            macd_line = macd.get('macd', [None] * len(candles))
            if i < 1 or macd_line[i] is None or macd_line[i - 1] is None:
                return False
            # Cross above zero
            return macd_line[i - 1] <= 0 and macd_line[i] > 0

        elif ind_type == 'macd-histogram':
            macd = indicators.get('macd', {})
            histogram = macd.get('histogram', [None] * len(candles))
            if i < 1 or histogram[i] is None or histogram[i - 1] is None:
                return False
            # Histogram turning up (direction change)
            return histogram[i] > histogram[i - 1]

        elif ind_type == 'ichimoku-kumo':
            ich = indicators.get('ichimoku', {})
            senkou_a = ich.get('senkou_a', [None] * len(candles))[i]
            senkou_b = ich.get('senkou_b', [None] * len(candles))[i]
            if senkou_a is None or senkou_b is None:
                return False
            kumo_top = max(senkou_a, senkou_b)
            return candle['close'] > kumo_top

        elif ind_type == 'ichimoku-tk':
            ich = indicators.get('ichimoku', {})
            tenkan = ich.get('tenkan', [None] * len(candles))
            kijun = ich.get('kijun', [None] * len(candles))
            if i < 1 or tenkan[i] is None or kijun[i] is None:
                return False
            if tenkan[i - 1] is None or kijun[i - 1] is None:
                return False
            # Bullish TK cross
            return tenkan[i - 1] <= kijun[i - 1] and tenkan[i] > kijun[i]

        elif ind_type == 'rsi-trend':
            # Buy when RSI starts rising while below oversold (20)
            rsi = indicators.get('rsi', [None] * len(candles))
            if i < 1 or rsi[i] is None or rsi[i - 1] is None:
                return False
            return rsi[i] < self.RSI_OVERSOLD and rsi[i] > rsi[i - 1]

        elif ind_type == 'rsi-early':
            # Buy when entering oversold zone (crosses down into <20)
            rsi = indicators.get('rsi', [None] * len(candles))
            if i < 1 or rsi[i] is None or rsi[i - 1] is None:
                return False
            return rsi[i - 1] >= self.RSI_OVERSOLD and rsi[i] < self.RSI_OVERSOLD

        elif ind_type == 'rsi-late':
            # Buy when exiting oversold zone (crosses up out of <20)
            rsi = indicators.get('rsi', [None] * len(candles))
            if i < 1 or rsi[i] is None or rsi[i - 1] is None:
                return False
            return rsi[i - 1] < self.RSI_OVERSOLD and rsi[i] >= self.RSI_OVERSOLD

        elif ind_type == 'rsi-large':
            # Buy when entering oversold zone (same as early)
            rsi = indicators.get('rsi', [None] * len(candles))
            if i < 1 or rsi[i] is None or rsi[i - 1] is None:
                return False
            return rsi[i - 1] >= self.RSI_OVERSOLD and rsi[i] < self.RSI_OVERSOLD

        elif ind_type == 'rsi-small':
            # Buy when exiting oversold zone (same as late)
            rsi = indicators.get('rsi', [None] * len(candles))
            if i < 1 or rsi[i] is None or rsi[i - 1] is None:
                return False
            return rsi[i - 1] < self.RSI_OVERSOLD and rsi[i] >= self.RSI_OVERSOLD

        elif ind_type == 'bollinger-rsi':
            # Combined: price touches lower band AND RSI < 20 (double oversold confirmation)
            bb = indicators.get('bollinger', {})
            rsi = indicators.get('rsi', [None] * len(candles))
            lower = bb.get('lower', [None] * len(candles))[i]
            rsi_val = rsi[i] if rsi else None
            if lower is None or rsi_val is None:
                return False
            return candle['low'] < lower and rsi_val < self.RSI_OVERSOLD

        return True

    def _check_indicator_sell(self, candles: List[Dict], i: int, indicators: Dict) -> bool:
        """Check if indicator signals a SELL at index i"""
        ind_config = self.config.indicator
        if not ind_config:
            return False  # No indicator = no sell signal from indicator

        ind_type = ind_config.get('type')
        mode = ind_config.get('mode', 'both')

        if mode == 'buy':
            return False  # Indicator only for buy

        candle = candles[i]

        if ind_type == 'bollinger':
            bb = indicators.get('bollinger', {})
            upper = bb.get('upper', [None] * len(candles))[i]
            if upper is None:
                return False
            return candle['high'] > upper

        elif ind_type == 'macd-cross':
            macd = indicators.get('macd', {})
            macd_line = macd.get('macd', [None] * len(candles))
            signal_line = macd.get('signal', [None] * len(candles))
            if i < 1 or macd_line[i] is None or signal_line[i] is None:
                return False
            if macd_line[i - 1] is None or signal_line[i - 1] is None:
                return False
            # Bearish cross
            return macd_line[i - 1] >= signal_line[i - 1] and macd_line[i] < signal_line[i]

        elif ind_type == 'macd-zero':
            macd = indicators.get('macd', {})
            macd_line = macd.get('macd', [None] * len(candles))
            if i < 1 or macd_line[i] is None or macd_line[i - 1] is None:
                return False
            # Cross below zero
            return macd_line[i - 1] >= 0 and macd_line[i] < 0

        elif ind_type == 'macd-histogram':
            macd = indicators.get('macd', {})
            histogram = macd.get('histogram', [None] * len(candles))
            if i < 1 or histogram[i] is None or histogram[i - 1] is None:
                return False
            # Histogram turning down (direction change)
            return histogram[i] < histogram[i - 1]

        elif ind_type == 'ichimoku-kumo':
            ich = indicators.get('ichimoku', {})
            senkou_a = ich.get('senkou_a', [None] * len(candles))[i]
            senkou_b = ich.get('senkou_b', [None] * len(candles))[i]
            if senkou_a is None or senkou_b is None:
                return False
            kumo_bottom = min(senkou_a, senkou_b)
            return candle['close'] < kumo_bottom

        elif ind_type == 'ichimoku-tk':
            ich = indicators.get('ichimoku', {})
            tenkan = ich.get('tenkan', [None] * len(candles))
            kijun = ich.get('kijun', [None] * len(candles))
            if i < 1 or tenkan[i] is None or kijun[i] is None:
                return False
            if tenkan[i - 1] is None or kijun[i - 1] is None:
                return False
            # Bearish TK cross
            return tenkan[i - 1] >= kijun[i - 1] and tenkan[i] < kijun[i]

        elif ind_type == 'rsi-trend':
            # Sell when RSI starts falling while above overbought (80)
            rsi = indicators.get('rsi', [None] * len(candles))
            if i < 1 or rsi[i] is None or rsi[i - 1] is None:
                return False
            return rsi[i] > self.RSI_OVERBOUGHT and rsi[i] < rsi[i - 1]

        elif ind_type == 'rsi-early':
            # Sell when entering overbought zone (crosses up into >80)
            rsi = indicators.get('rsi', [None] * len(candles))
            if i < 1 or rsi[i] is None or rsi[i - 1] is None:
                return False
            return rsi[i - 1] <= self.RSI_OVERBOUGHT and rsi[i] > self.RSI_OVERBOUGHT

        elif ind_type == 'rsi-late':
            # Sell when exiting overbought zone (crosses down out of >80)
            rsi = indicators.get('rsi', [None] * len(candles))
            if i < 1 or rsi[i] is None or rsi[i - 1] is None:
                return False
            return rsi[i - 1] > self.RSI_OVERBOUGHT and rsi[i] <= self.RSI_OVERBOUGHT

        elif ind_type == 'rsi-large':
            # Sell when exiting overbought zone (crosses down out of >80)
            rsi = indicators.get('rsi', [None] * len(candles))
            if i < 1 or rsi[i] is None or rsi[i - 1] is None:
                return False
            return rsi[i - 1] > self.RSI_OVERBOUGHT and rsi[i] <= self.RSI_OVERBOUGHT

        elif ind_type == 'rsi-small':
            # Sell when entering overbought zone (crosses up into >80)
            rsi = indicators.get('rsi', [None] * len(candles))
            if i < 1 or rsi[i] is None or rsi[i - 1] is None:
                return False
            return rsi[i - 1] <= self.RSI_OVERBOUGHT and rsi[i] > self.RSI_OVERBOUGHT

        elif ind_type == 'bollinger-rsi':
            # Sell when RSI > 80 (overbought exit)
            rsi = indicators.get('rsi', [None] * len(candles))
            rsi_val = rsi[i] if rsi else None
            if rsi_val is None:
                return False
            return rsi_val > self.RSI_OVERBOUGHT

        return False

    def _check_ma_conditions_buy(self, candles: List[Dict], i: int, mas: Dict) -> bool:
        """Check MA-based conditions for BUY (all must be true)"""
        candle = candles[i]
        close = candle['close']

        # MA Trend: MA must be rising
        if self.config.ma_trend:
            ma = mas.get(f'ma{self.config.ma_trend}', [None] * len(candles))
            if i < 1 or ma[i] is None or ma[i - 1] is None:
                return False
            if ma[i] <= ma[i - 1]:  # Not rising
                return False

        # Value above MA: Price must be above MA
        if self.config.value_above_ma:
            ma = mas.get(f'ma{self.config.value_above_ma}', [None] * len(candles))
            if ma[i] is None:
                return False
            if close <= ma[i]:
                return False

        # MA Cross: Fast MA must be above Slow MA
        if self.config.ma_cross:
            fast = self.config.ma_cross.get('fast')
            slow = self.config.ma_cross.get('slow')
            ma_fast = mas.get(f'ma{fast}', [None] * len(candles))
            ma_slow = mas.get(f'ma{slow}', [None] * len(candles))
            if ma_fast[i] is None or ma_slow[i] is None:
                return False
            if ma_fast[i] <= ma_slow[i]:
                return False

        return True

    def _check_ma_conditions_sell(self, candles: List[Dict], i: int, mas: Dict) -> bool:
        """Check MA-based conditions for SELL (symmetric - any triggers sell)"""
        candle = candles[i]
        close = candle['close']

        # MA Trend: MA falling = sell
        if self.config.ma_trend:
            ma = mas.get(f'ma{self.config.ma_trend}', [None] * len(candles))
            if i >= 1 and ma[i] is not None and ma[i - 1] is not None:
                if ma[i] < ma[i - 1]:  # Falling
                    return True

        # Value above MA: Price below MA = sell
        if self.config.value_above_ma:
            ma = mas.get(f'ma{self.config.value_above_ma}', [None] * len(candles))
            if ma[i] is not None and close < ma[i]:
                return True

        # MA Cross: Fast below Slow = sell
        if self.config.ma_cross:
            fast = self.config.ma_cross.get('fast')
            slow = self.config.ma_cross.get('slow')
            ma_fast = mas.get(f'ma{fast}', [None] * len(candles))
            ma_slow = mas.get(f'ma{slow}', [None] * len(candles))
            if ma_fast[i] is not None and ma_slow[i] is not None:
                if ma_fast[i] < ma_slow[i]:
                    return True

        return False

    def _check_time_constraint(self, timestamp: int) -> bool:
        """Check if current time is within allowed trading hours"""
        if not self.config.time_constraint:
            return True

        tc = self.config.time_constraint
        open_hour = int(tc.get('open', '00:00').split(':')[0])
        close_hour = int(tc.get('close', '23:59').split(':')[0])

        current_hour = get_paris_hour(timestamp)

        if open_hour <= close_hour:
            return open_hour <= current_hour <= close_hour
        else:  # Overnight (e.g., 22:00 - 06:00)
            return current_hour >= open_hour or current_hour <= close_hour

    def _check_stop_loss(self, candle: Dict, buy_price: float) -> bool:
        """Check if stop loss is triggered"""
        if not self.config.stop_loss:
            return False
        sl_price = buy_price * (1 - self.config.stop_loss / 100)
        return candle['low'] < sl_price

    # ==================== Main Signal Calculation ====================

    def calculate_signals(
        self,
        candles: List[Dict],
        initial_state: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Signal], Dict[str, Any]]:
        if len(candles) < self.required_lookback:
            return [], initial_state or {}

        # Restore state
        if initial_state:
            position = initial_state.get('position')
            traded_dates = set(initial_state.get('traded_dates', []))
        else:
            position = None
            traded_dates = set()

        # Setup timezone for date calculations
        from datetime import datetime
        import pytz
        paris_tz = pytz.timezone('Europe/Paris')

        # Pre-calculate all indicators
        closes = [c['close'] for c in candles]
        indicators = {}
        mas = {}

        # Calculate required MAs
        ma_periods = set()
        if self.config.ma_trend:
            ma_periods.add(self.config.ma_trend)
        if self.config.value_above_ma:
            ma_periods.add(self.config.value_above_ma)
        if self.config.ma_cross:
            ma_periods.add(self.config.ma_cross.get('fast'))
            ma_periods.add(self.config.ma_cross.get('slow'))

        for period in ma_periods:
            if period:
                mas[f'ma{period}'] = self._calculate_sma(closes, period)

        # Calculate indicator if needed
        ind_config = self.config.indicator
        if ind_config:
            ind_type = ind_config.get('type')
            if ind_type == 'bollinger':
                indicators['bollinger'] = self._calculate_bollinger(closes)
            elif ind_type in ('macd-cross', 'macd-zero', 'macd-histogram'):
                indicators['macd'] = self._calculate_macd(closes)
            elif ind_type in ('ichimoku-kumo', 'ichimoku-tk'):
                indicators['ichimoku'] = self._calculate_ichimoku(candles)
            elif ind_type in ('rsi-trend', 'rsi-early', 'rsi-late', 'rsi-large', 'rsi-small'):
                indicators['rsi'] = self._calculate_rsi(closes)
            elif ind_type == 'bollinger-rsi':
                # Combined indicator: calculate both
                indicators['bollinger'] = self._calculate_bollinger(closes)
                indicators['rsi'] = self._calculate_rsi(closes)

        signals: List[Signal] = []
        start_index = self.required_lookback

        # Loop through all candles - check PREVIOUS candle for conditions, execute on CURRENT
        for i in range(start_index, len(candles)):
            candle = candles[i]  # Current candle - where we execute
            prev_candle = candles[i - 1]  # Previous candle - where we check conditions
            timestamp = candle['time']
            prev_timestamp = prev_candle['time']

            # Get date for daily tracking
            dt = datetime.fromtimestamp(timestamp, tz=paris_tz)
            date_str = dt.strftime('%Y-%m-%d')
            prev_dt = datetime.fromtimestamp(prev_timestamp, tz=paris_tz)
            prev_date_str = prev_dt.strftime('%Y-%m-%d')

            # Check time constraint on previous candle
            in_time_window = self._check_time_constraint(prev_timestamp)

            # ===== SELL LOGIC =====
            if position is not None:
                buy_price = position['buy_price']
                should_sell = False
                sell_label = 'Exit'
                sell_price = candle['open']
                sell_signal_ts = timestamp

                # 1. Intraday EOD - check CURRENT candle via registry (we know close hour ahead of time)
                if self.config.intraday in ('daily', 'multi-daily'):
                    if is_last_candle_of_day(timestamp):
                        should_sell = True
                        sell_price = candle['close']  # Close at this candle's close
                        sell_signal_ts = timestamp
                        sell_label = 'EOD'

                # 2. Stop Loss (check if previous candle hit SL)
                if not should_sell and self._check_stop_loss(prev_candle, buy_price):
                    should_sell = True
                    sell_price = buy_price * (1 - self.config.stop_loss / 100)
                    sell_label = 'SL'

                # 3. MA conditions (symmetric sell)
                elif not should_sell and self._check_ma_conditions_sell(candles, i - 1, mas):
                    should_sell = True
                    sell_label = 'MA'

                # 4. Indicator sell signal
                elif not should_sell and self._check_indicator_sell(candles, i - 1, indicators):
                    should_sell = True
                    ind_type = ind_config.get('type', '') if ind_config else ''
                    sell_label = ind_type.upper().split('-')[0]

                # 5. Time constraint exit
                elif not should_sell and not in_time_window:
                    should_sell = True
                    sell_label = 'Time'

                if should_sell:
                    signals.append(Signal(
                        signal_timestamp=sell_signal_ts,
                        trigger_timestamp=timestamp if sell_label == 'EOD' else prev_timestamp,
                        type='sell',
                        price=sell_price,
                        label=sell_label,
                        metadata={
                            'buy_price': buy_price,
                            'buy_time': position['buy_time'],
                        }
                    ))
                    position = None
                    continue  # After any sell, don't buy on same candle

            # ===== BUY LOGIC (check previous candle conditions) =====
            if position is None:
                can_buy = True
                is_intraday = self.config.intraday in ('daily', 'multi-daily')

                # Always check PREVIOUS candle for conditions (no look-ahead bias)
                check_index = i - 1
                check_timestamp = prev_timestamp

                # Time constraint - check at EXECUTION time (current candle)
                if not self._check_time_constraint(timestamp):
                    can_buy = False

                # Intraday: check if too close to close at EXECUTION time
                if can_buy and is_intraday:
                    if is_too_close_to_close(timestamp, min_hours_before_close=2):
                        can_buy = False
                    # Daily mode: only one position per day (use execution date)
                    if self.config.intraday == 'daily' and date_str in traded_dates:
                        can_buy = False

                # MA conditions
                if can_buy and not self._check_ma_conditions_buy(candles, check_index, mas):
                    can_buy = False

                # Indicator buy signal
                if can_buy and not self._check_indicator_buy(candles, check_index, indicators):
                    can_buy = False

                if can_buy:
                    buy_price = candle['open']  # Execute at current candle's open
                    signal_ts = timestamp

                    signals.append(Signal(
                        signal_timestamp=signal_ts,
                        trigger_timestamp=check_timestamp,
                        type='buy',
                        price=buy_price,
                        label='Buy',
                        metadata={}
                    ))
                    position = {
                        'buy_price': buy_price,
                        'buy_time': signal_ts,
                    }
                    traded_dates.add(date_str)  # Track by execution date

        final_state = {
            'position': position,
            'traded_dates': list(traded_dates),
        }

        return signals, final_state


def create_dynamic_strategy(config_dict: Dict[str, Any]) -> DynamicStrategy:
    """Factory function to create a DynamicStrategy from a config dict"""
    config = DynamicStrategyConfig.from_dict(config_dict)
    return DynamicStrategy(config)


def generate_strategy_name(config: Dict[str, Any]) -> str:
    """Generate a slug name from strategy configuration"""
    parts = []

    # Indicator
    indicator = config.get('indicator')
    if indicator:
        ind_type = indicator.get('type', 'none')
        mode = indicator.get('mode', 'both')
        mode_suffix = '' if mode == 'both' else f'-{mode[0].upper()}'  # -B or -S
        parts.append(f"{ind_type}{mode_suffix}")

    # Stop loss
    sl = config.get('stop_loss')
    if sl:
        parts.append(f"sl{sl}".replace('.', ''))

    # MA Trend
    ma_trend = config.get('ma_trend')
    if ma_trend:
        parts.append(f"trend{ma_trend}")

    # Value above MA
    value_ma = config.get('value_above_ma')
    if value_ma:
        parts.append(f"above{value_ma}")

    # MA Cross
    ma_cross = config.get('ma_cross')
    if ma_cross:
        fast = ma_cross.get('fast')
        slow = ma_cross.get('slow')
        parts.append(f"cross{fast}-{slow}")

    # Intraday
    intraday = config.get('intraday', 'none')
    if intraday == 'daily':
        parts.append('intrad-single')
    elif intraday == 'multi-daily':
        parts.append('intrad-multi')

    # Time constraint
    tc = config.get('time_constraint')
    if tc:
        open_h = tc.get('open', '00:00').split(':')[0]
        close_h = tc.get('close', '23:59').split(':')[0]
        parts.append(f"h{open_h}-{close_h}")

    if not parts:
        parts.append('default')

    return '-'.join(parts).lower()


def generate_display_name(config: Dict[str, Any]) -> str:
    """Generate a human-readable display name from config"""
    parts = []

    # Indicator
    indicator = config.get('indicator')
    if indicator:
        ind_type = indicator.get('type', '').replace('-', ' ').title()
        mode = indicator.get('mode', 'both')
        if mode == 'buy':
            ind_type += ' (B)'
        elif mode == 'sell':
            ind_type += ' (S)'
        if ind_type:
            parts.append(ind_type)

    # Stop loss
    sl = config.get('stop_loss')
    if sl:
        parts.append(f"SL{sl}%")

    # MA Trend
    ma_trend = config.get('ma_trend')
    if ma_trend:
        parts.append(f"Trend{ma_trend}")

    # Value above MA
    value_ma = config.get('value_above_ma')
    if value_ma:
        parts.append(f">MA{value_ma}")

    # MA Cross
    ma_cross = config.get('ma_cross')
    if ma_cross:
        fast = ma_cross.get('fast')
        slow = ma_cross.get('slow')
        parts.append(f"X{fast}/{slow}")

    # Intraday
    intraday = config.get('intraday', 'none')
    if intraday == 'daily':
        parts.append('IntraD-Single')
    elif intraday == 'multi-daily':
        parts.append('IntraD-Multi')

    # Time constraint
    tc = config.get('time_constraint')
    if tc:
        open_h = tc.get('open', '00:00')
        close_h = tc.get('close', '23:59')
        parts.append(f"{open_h}-{close_h}")

    if not parts:
        return 'Default Strategy'

    return ' '.join(parts)
