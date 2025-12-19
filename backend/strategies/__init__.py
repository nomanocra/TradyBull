from .base import BaseStrategy, Signal, ProcessingState, StrategyDisplayConfig
from .bollinger_nosl import BollingerNoSLStrategy
from .bollinger_sl1 import BollingerSL1Strategy
from .bollinger_sl1_trend import BollingerSL1TrendStrategy
from .bollinger_sl1_crossing import BollingerSL1CrossingStrategy
from .bollinger_sl25 import BollingerSL25Strategy
from .bollinger_sl25_trend import BollingerSL25TrendStrategy
from .bollinger_sl25_crossing import BollingerSL25CrossingStrategy
from .dummy import DummyStrategy
from .dummy_sl1 import DummySL1Strategy
from .dummy_sl25 import DummySL25Strategy

# Registry of available strategies
STRATEGIES = {
    'bollinger-nosl': BollingerNoSLStrategy,
    'bollinger-sl1': BollingerSL1Strategy,
    'bollinger-sl1-trend': BollingerSL1TrendStrategy,
    'bollinger-sl1-crossing': BollingerSL1CrossingStrategy,
    'bollinger-sl25': BollingerSL25Strategy,
    'bollinger-sl25-trend': BollingerSL25TrendStrategy,
    'bollinger-sl25-crossing': BollingerSL25CrossingStrategy,
    'dummy': DummyStrategy,
    'dummy-sl1': DummySL1Strategy,
    'dummy-sl25': DummySL25Strategy,
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
    'DummyStrategy',
    'DummySL1Strategy',
    'DummySL25Strategy',
    'STRATEGIES',
]
