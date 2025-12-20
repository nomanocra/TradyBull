from .base import BaseStrategy, Signal, ProcessingState, StrategyDisplayConfig
from .bollinger_nosl import BollingerNoSLStrategy
from .bollinger_sl1 import BollingerSL1Strategy
from .bollinger_sl1_trend import BollingerSL1TrendStrategy
from .bollinger_sl1_crossing import BollingerSL1CrossingStrategy
from .bollinger_sl25 import BollingerSL25Strategy
from .bollinger_sl25_trend import BollingerSL25TrendStrategy
from .bollinger_sl25_crossing import BollingerSL25CrossingStrategy
from .daily import DailyStrategy
from .daily_sl1 import DailySL1Strategy
from .daily_sl1_trend import DailySL1TrendStrategy
from .daily_sl1_trend_v2 import DailySL1TrendV2Strategy
from .daily_sl1_crossing import DailySL1CrossingStrategy
from .daily_sl25 import DailySL25Strategy
from .daily_sl25_trend import DailySL25TrendStrategy
from .daily_sl25_crossing import DailySL25CrossingStrategy
from .trend import TrendStrategy
from .trend_22h import Trend22hStrategy
from .ichimoku_kumo import IchimokuKumoStrategy
from .ichimoku_kumo_sl1 import IchimokuKumoSL1Strategy

# Registry of available strategies
STRATEGIES = {
    'bollinger-nosl': BollingerNoSLStrategy,
    'bollinger-sl1': BollingerSL1Strategy,
    'bollinger-sl1-trend': BollingerSL1TrendStrategy,
    'bollinger-sl1-crossing': BollingerSL1CrossingStrategy,
    'bollinger-sl25': BollingerSL25Strategy,
    'bollinger-sl25-trend': BollingerSL25TrendStrategy,
    'bollinger-sl25-crossing': BollingerSL25CrossingStrategy,
    'daily': DailyStrategy,
    'daily-sl1': DailySL1Strategy,
    'daily-sl1-trend': DailySL1TrendStrategy,
    'daily-sl1-trend-v2': DailySL1TrendV2Strategy,
    'daily-sl1-crossing': DailySL1CrossingStrategy,
    'daily-sl25': DailySL25Strategy,
    'daily-sl25-trend': DailySL25TrendStrategy,
    'daily-sl25-crossing': DailySL25CrossingStrategy,
    'trend': TrendStrategy,
    'trend-22h': Trend22hStrategy,
    'ichimoku-kumo': IchimokuKumoStrategy,
    'ichimoku-kumo-sl1': IchimokuKumoSL1Strategy,
}

__all__ = [
    'BaseStrategy',
    'Signal',
    'ProcessingState',
    'StrategyDisplayConfig',
    'BollingerNoSLStrategy',
    'BollingerSL1Strategy',
    'BollingerSL1TrendStrategy',
    'BollingerSL1CrossingStrategy',
    'BollingerSL25Strategy',
    'BollingerSL25TrendStrategy',
    'BollingerSL25CrossingStrategy',
    'DailyStrategy',
    'DailySL1Strategy',
    'DailySL1TrendStrategy',
    'DailySL1TrendV2Strategy',
    'DailySL1CrossingStrategy',
    'DailySL25Strategy',
    'DailySL25TrendStrategy',
    'DailySL25CrossingStrategy',
    'TrendStrategy',
    'Trend22hStrategy',
    'IchimokuKumoStrategy',
    'IchimokuKumoSL1Strategy',
    'STRATEGIES',
]
