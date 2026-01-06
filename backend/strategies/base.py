from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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


@dataclass
class StrategyDisplayConfig:
    """Configuration for how the strategy is displayed in the frontend"""
    display_name: str           # Human-readable name (e.g., "Bollinger NoSL")
    description: str = ""       # Strategy description for tooltip
    show_bollinger: bool = False
    show_macd: bool = False
    show_ichimoku: bool = False
    show_moving_averages: bool = False
    show_rsi: bool = False
    ma_periods: List[int] = field(default_factory=list)  # Specific MA periods to display (e.g., [50, 200])


class BaseStrategy(ABC):
    """Abstract base class for trading strategies"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier (e.g., 'bollinger-nosl')"""
        pass

    @property
    @abstractmethod
    def display_config(self) -> StrategyDisplayConfig:
        """Display configuration for the frontend"""
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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize strategy metadata for API responses"""
        config = self.display_config
        return {
            'name': self.name,
            'display_name': config.display_name,
            'description': config.description,
            'show_bollinger': config.show_bollinger,
            'show_macd': config.show_macd,
            'show_ichimoku': config.show_ichimoku,
            'show_moving_averages': config.show_moving_averages,
            'show_rsi': config.show_rsi,
            'ma_periods': config.ma_periods,
        }
