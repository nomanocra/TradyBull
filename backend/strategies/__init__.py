from .base import BaseStrategy, Signal, ProcessingState
from .bollinger_nosl import BollingerNoSLStrategy

# Registry of available strategies
STRATEGIES = {
    'bollinger-nosl': BollingerNoSLStrategy,
}

__all__ = [
    'BaseStrategy',
    'Signal',
    'ProcessingState',
    'BollingerNoSLStrategy',
    'STRATEGIES',
]
