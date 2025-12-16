from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class Signal:
    """Represents a trading signal"""
    signal_timestamp: int      # Unix timestamp where marker appears (next candle)
    trigger_timestamp: int     # Unix timestamp of candle that triggered condition
    type: str                  # 'buy' or 'sell'
    price: float              # Entry/exit price
    label: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ProcessingState:
    """Represents the processing state for incremental updates"""
    last_processed_timestamp: int
    state_data: Dict[str, Any]  # Strategy-specific state


class BaseStrategy(ABC):
    """Abstract base class for trading strategies"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier (e.g., 'bollinger-nosl')"""
        pass

    @property
    @abstractmethod
    def required_lookback(self) -> int:
        """Number of candles needed before first signal is possible"""
        pass

    @abstractmethod
    def calculate_signals(
        self,
        candles: List[Dict],
        initial_state: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Signal], Dict[str, Any]]:
        """
        Calculate signals for given candles.

        Args:
            candles: List of candle dicts with time, open, high, low, close, volume
            initial_state: Previous processing state (for incremental updates)

        Returns:
            tuple: (list of new signals, final state dict)
        """
        pass
